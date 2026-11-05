"""Sauvegardes JSON explicites ; aucun objet Python exécutable n'est désérialisé."""
from dataclasses import asdict
import json
from math import isfinite
import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile

from star_arena.systems.economy import income, SHIP_COSTS
from star_arena.systems.planets import ensure_planets, build_spec
from star_arena.domain.planet_stats import PLANET_TYPES, GROUND, DEFENSES
from star_arena.config import FACTION_CAPITALS, MAX_SAVE_BYTES, SAVE_VERSION, SIMULATION_STEP
from star_arena.domain.models import BattleReport, Campaign, EngagedShip, Engagement, Fleet, SHIP_TYPES, Ship, StarSystem, Travel, Production, Resources, Planet, Building, BuildJob


def _integer(value: object, low: int, high: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and low <= value <= high


def _number(value: object, low: float, high: float) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return low <= value <= high and isfinite(value)


def _text(value: object, maximum: int) -> bool:
    return isinstance(value, str) and 1 <= len(value) <= maximum and value.isprintable()


def decode(data: object) -> Campaign:
    try:
        if not isinstance(data, dict) or not _integer(data.get("version"), 1, SAVE_VERSION):
            raise ValueError("Version de sauvegarde incompatible.")
        if not _integer(data["player"], 0, 2) or not _integer(data["seed"], 0, 2**31 - 1):
            raise ValueError("Faction ou graine invalide.")
        systems: dict[int, StarSystem] = {}
        if not isinstance(data["systems"], list) or len(data["systems"]) not in (15, 30, 60, 100):
            raise ValueError("Taille de carte invalide.")
        count = len(data["systems"])
        for entry in data["systems"]:
            i, p = entry["id"], entry["position"]
            if (not _integer(i, 0, count - 1) or i in systems or not isinstance(p, list) or len(p) != 2
                    or not all(_number(n, -1e6, 1e6) for n in p)
                    or not _text(entry["name"], 60)
                    or (entry["owner"] is not None and not _integer(entry["owner"], 0, 2))
                    or type(entry["capital"]) is not bool):
                raise ValueError("Système invalide.")
            systems[i] = StarSystem(i, entry["name"], tuple(p), entry["owner"], entry["capital"])
        capitals = FACTION_CAPITALS if count == 15 else (0, (6 if count == 30 else 10)-1, count-(6 if count == 30 else 10)//2)
        if any(s.capital != (s.id in capitals) or (s.capital and s.owner is None)
               for s in systems.values()):
            raise ValueError("Capitales absentes ou invalides.")
        routes: set[tuple[int, int]] = set()
        if not isinstance(data["routes"], list) or len(data["routes"]) > count * 5:
            raise ValueError("Routes invalides.")
        for edge in data["routes"]:
            if not isinstance(edge, list) or len(edge) != 2 or not all(_integer(i, 0, count - 1) for i in edge) or edge[0] == edge[1]:
                raise ValueError("Route invalide.")
            route = tuple(sorted(edge))
            if route in routes:
                raise ValueError("Route dupliquée.")
            routes.add(route)
        reached = {0}
        for _ in range(count):
            for a, b in routes:
                if a in reached or b in reached:
                    reached.update((a, b))
        if len(reached) != count and data["version"] < 5:
            raise ValueError("Carte non connexe.")
        fleets = {}
        ship_ids: set[int] = set()
        if not isinstance(data["fleets"], list) or not 1 <= len(data["fleets"]) <= 10000:
            raise ValueError("Flottes invalides.")
        for entry in data["fleets"]:
            if (not _integer(entry["id"], 1, 1_000_000) or entry["id"] in fleets
                    or not _integer(entry["owner"], 0, 2) or not _integer(entry["system_id"], 0, count - 1)
                    or not isinstance(entry["ships"], list) or not 0 <= len(entry["ships"]) <= 10000):
                raise ValueError("Flotte invalide.")
            ships = []
            for ship in entry["ships"]:
                if not _integer(ship["id"], 1, 1_000_000) or ship["id"] in ship_ids or ship["model"] not in SHIP_TYPES:
                    raise ValueError("Vaisseau inconnu ou dupliqué.")
                _, hull, shield = SHIP_TYPES[ship["model"]]
                if not _number(ship["hull"], 0.001, hull) or not _number(ship["shield"], 0, shield):
                    raise ValueError("État de vaisseau invalide.")
                status=ship.get("status", "permanent")
                if status not in ("permanent", "militia", "orbital") or (status=="orbital") != (ship["model"] not in ("fighter","corvette","cruiser")):
                    raise ValueError("Statut d'unité invalide.")
                ships.append(Ship(ship["id"], ship["model"], float(ship["hull"]), float(ship["shield"]), status))
                ship_ids.add(ship["id"])
            travel = None
            t = entry["travel"]
            if not ships and t is not None:
                raise ValueError("Une flotte détruite ne peut pas voyager.")
            if t is not None:
                if (not _integer(t["origin"], 0, count - 1) or not _integer(t["destination"], 0, count - 1)
                        or (tuple(sorted((t["origin"], t["destination"]))) not in routes and not entry.get("itinerary"))
                        or t["origin"] != entry["system_id"]
                        or not _number(t["duration"], 0.01, 10_000)
                        or not _number(t["elapsed"], 0, t["duration"])):
                    raise ValueError("Trajet invalide.")
                travel = Travel(t["origin"], t["destination"], float(t["elapsed"]), float(t["duration"]))
            fleet = Fleet(entry["id"], entry["owner"], entry["system_id"], ships, travel)
            _decode_navigation(entry,fleet,count)
            fleet.status=entry.get("status", "permanent")
            if fleet.status=="garrison" and fleet.itinerary:
                raise ValueError("Une garnison ne possède pas d’itinéraire.")
            if fleet.status not in ("permanent", "garrison") or (fleet.status=="garrison" and travel is not None):
                raise ValueError("Statut de flotte invalide.")
            if any((u.status=="permanent") != (fleet.status=="permanent") for u in ships):
                raise ValueError("Une garnison ne peut pas être une flotte permanente.")
            fleets[fleet.id] = fleet
        if not _number(data["time"], 0, 1e10) or not _number(data["next_ai_at"], 0, 1e10):
            raise ValueError("Horloge invalide.")
        remainder = data.get("step_remainder", 0.0)
        if not _number(remainder, 0, SIMULATION_STEP) or remainder >= SIMULATION_STEP:
            raise ValueError("Fraction de simulation invalide.")
        events = data["events"]
        if not isinstance(events, list) or len(events) > 12 or not all(_text(e, 300) for e in events):
            raise ValueError("Journal invalide.")
        campaign = Campaign(data["player"], data["seed"], systems, routes, fleets,
                            float(data["time"]), float(data["next_ai_at"]), list(events), float(remainder))
        if data["version"] >= 2:
            campaign.next_engagement_id = data["next_engagement_id"]
            if not _integer(campaign.next_engagement_id, 1, 1_000_000_000):
                raise ValueError("Compteur d'engagement invalide.")
            campaign.pending = _decode_pending(data["pending"], campaign)
            campaign.reports = _decode_reports(data["reports"], campaign)
        _decode_planets(data, campaign)
        if data["version"] >= 3:
            _decode_economy(data, campaign)
        else:
            for entry in data["systems"]:
                system = systems[entry["id"]]
                system.richness = entry.get("richness", 4 if system.capital else 1 + system.id % 4)
                system.yard_owner = entry.get("yard_owner")
            historical_ids = [u.id for report in campaign.reports for u in report.cruisers]
            campaign.next_ship_id = max(25, max(ship_ids | set(historical_ids), default=0) + 1)
            campaign.next_fleet_id = max(4, max(fleets, default=0) + 1)
        if data["version"] >= 4:
            ids = [u.id for s in systems.values() for p in s.planets
                   for u in ([b.unit for b in p.orbitals if b.unit]+p.militia)]
            if ids and campaign.next_ship_id <= max(ids):
                raise ValueError("Compteur planétaire réutilisant une identité.")
        for fleet in fleets.values():
            if fleet.status=="garrison" and (campaign.pending is None or
                    fleet.system_id!=campaign.pending.system_id or not fleet.ships):
                raise ValueError("Garnison matérialisée hors engagement.")
            if fleet.ships and fleet.travel is None and systems[fleet.system_id].owner != fleet.owner:
                pending = campaign.pending
                if pending is None or not any(s.fleet_id == fleet.id for s in pending.initial):
                    if fleet.navigation_state!="blocked" or fleet.final_destination is None:
                        raise ValueError("Flotte hostile sans engagement.")
        return campaign
    except (KeyError, TypeError, OverflowError) as error:
        raise ValueError("Sauvegarde incomplète ou corrompue.") from error


def _record(value: dict, *, allow_destroyed: bool = False) -> EngagedShip:
    if (not _integer(value["id"], 1, 1_000_000) or not _integer(value["fleet_id"], 1, 1_000_000)
            or not _integer(value["owner"], 0, 2) or value["model"] not in SHIP_TYPES):
        raise ValueError("Identité de combat invalide.")
    _, hull, shield = SHIP_TYPES[value["model"]]
    if not _number(value["hull"], 0 if allow_destroyed else 0.001, hull) or not _number(value["shield"], 0, shield):
        raise ValueError("État de combat invalide.")
    return EngagedShip(value["id"], value["fleet_id"], value["owner"], value["model"], float(value["hull"]), float(value["shield"]))


def _decode_pending(value, campaign: Campaign) -> Engagement | None:
    count = len(campaign.systems)
    if value is None:
        return None
    if (not _integer(value["id"], 1, campaign.next_engagement_id - 1)
            or not _integer(value["system_id"], 0, count - 1) or not _integer(value["origin"], 0, count - 1)
            or not _integer(value["attacker"], 0, 2) or not _integer(value["defender"], 0, 2)
            or value["attacker"] == value["defender"]
            or not isinstance(value["initial"], list) or not 2 <= len(value["initial"]) <= 10_000
            or (value["system_id"] not in campaign.neighbors(value["origin"]) and not any(
                f.navigation_state=='engaged' and f.segment_index>0 and
                f.itinerary[f.segment_index-1:f.segment_index+1]==[value['origin'],value['system_id']]
                for f in campaign.fleets.values()))):
        raise ValueError("Engagement invalide.")
    records = [_record(item) for item in value["initial"]]
    if len({s.id for s in records}) != len(records) or {s.owner for s in records} != {value["attacker"], value["defender"]}:
        raise ValueError("Participants de bataille invalides ou dupliqués.")
    expected = {s.id for s in records}
    actual = set()
    for fleet_id in {s.fleet_id for s in records}:
        fleet = campaign.fleets.get(fleet_id)
        if fleet is None or fleet.system_id != value["system_id"] or fleet.travel is not None:
            raise ValueError("Flotte de bataille absente.")
        actual.update(s.id for s in fleet.ships)
        for record in (s for s in records if s.fleet_id == fleet_id):
            ship = next((s for s in fleet.ships if s.id == record.id), None)
            if (ship is None or fleet.owner != record.owner or ship.model != record.model
                    or abs(ship.hull - record.hull) > 1e-7 or abs(ship.shield - record.shield) > 1e-7):
                raise ValueError("Composition incohérente ou bataille tactique déjà en cours : terminez-la avant de sauvegarder.")
    if actual != expected:
        raise ValueError("Composition de bataille incomplète.")
    return Engagement(value["id"], value["system_id"], value["origin"], value["attacker"], value["defender"], records)


def _decode_reports(values, campaign: Campaign) -> list[BattleReport]:
    count = len(campaign.systems)
    if not isinstance(values, list) or len(values) > 20:
        raise ValueError("Historique de bataille invalide.")
    reports = []
    ids = set()
    for value in values:
        if (not _integer(value["id"], 1, campaign.next_engagement_id - 1) or value["id"] in ids
                or not _integer(value["system_id"], 0, count - 1) or not _integer(value["attacker"], 0, 2)
                or not _integer(value["defender"], 0, 2) or value["attacker"] == value["defender"]
                or (value["winner"] is not None and (not _integer(value["winner"], 0, 2) or value["winner"] not in (value["attacker"], value["defender"])))
                or type(value["automatic"]) is not bool or type(value["retreat"]) is not bool):
            raise ValueError("Rapport de bataille invalide.")
        if campaign.pending is not None and campaign.pending.id == value["id"]:
            raise ValueError("Bataille déjà résolue et encore en attente.")
        for key in ("previous_owner", "new_owner"):
            if value[key] is not None and not _integer(value[key], 0, 2):
                raise ValueError("Territoire du rapport invalide.")
        counters = {}
        owners = (value["attacker"], value["defender"])
        for key in ("engaged", "destroyed", "survivors", "captured"):
            counts = value[key]
            if not isinstance(counts, dict) or set(counts) != {str(o) for o in owners} or not all(_integer(n, 0, 10_000) for n in counts.values()):
                raise ValueError("Bilan de bataille invalide.")
            counters[key] = {o: counts[str(o)] for o in owners}
        if any(counters["engaged"][o] != sum(counters[k][o] for k in ("destroyed", "survivors", "captured")) for o in owners):
            raise ValueError("Bilan des pertes incohérent.")
        if not isinstance(value["cruisers"], list) or len(value["cruisers"]) > 10_000:
            raise ValueError("État des croiseurs invalide.")
        cruisers = [_record(item, allow_destroyed=True) for item in value["cruisers"]]
        if any(s.model != "cruiser" or s.owner not in owners for s in cruisers) or len({s.id for s in cruisers}) != len(cruisers):
            raise ValueError("Croiseurs du rapport dupliqués ou invalides.")
        reports.append(BattleReport(value["id"], value["system_id"], *owners, value["winner"],
                                    value["previous_owner"], value["new_owner"], counters["engaged"],
                                    counters["destroyed"], counters["survivors"], counters["captured"], cruisers,
                                    value["automatic"], value["retreat"]))
        ids.add(value["id"])
    return reports


def _unique_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Clé JSON dupliquée : {key[:60]}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Valeur numérique JSON interdite : {value}")


def load_campaign(path: Path) -> Campaign:
    with path.open("rb") as stream:
        contents = stream.read(MAX_SAVE_BYTES + 1)
    if len(contents) > MAX_SAVE_BYTES:
        raise ValueError("Sauvegarde trop volumineuse.")
    data = json.loads(contents.decode("utf-8"), object_pairs_hook=_unique_keys, parse_constant=_invalid_constant)
    return decode(data)


def save_campaign(campaign: Campaign, path: Path) -> None:
    if path.exists():
        # Conserver un fichier inconnu ou incompatible, même sur un ordre F5.
        load_campaign(path)
        old = json.loads(path.read_text(encoding="utf-8"))
        if old["version"] < SAVE_VERSION:
            backup = path.with_name(path.name + f".v{old['version']}.bak")
            index = 1
            while backup.exists():
                backup = path.with_name(path.name + f".v{old['version']}.{index}.bak")
                index += 1
            shutil.copy2(path, backup)
    payload = campaign_payload(campaign)
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    decode(json.loads(text))
    encoded = text.encode("utf-8")
    if len(encoded) > MAX_SAVE_BYTES:
        raise ValueError("Sauvegarde trop volumineuse.")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(mode="wb", prefix=f".{path.name}.", suffix=".tmp",
                                dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(encoded)
            stream.flush()
            sync=getattr(os,"fsync",None)
            if sync is not None:
                sync(stream.fileno())
        temporary.replace(path)
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # Ne pas masquer l'erreur initiale d'écriture/remplacement.


def _decode_economy(data: dict, c: Campaign) -> None:
    if data["galaxy_size"] != len(c.systems):
        raise ValueError("Dimensions de galaxie incohérentes.")
    if not _number(data["economy_remainder"], 0, 0.9999999999):
        raise ValueError("Horloge économique invalide.")
    c.economy_remainder = float(data["economy_remainder"])
    for i in range(3):
        r = data["resources"][str(i)]
        if not all(_number(r[k], 0, 1e15) for k in ("credits", "minerals")):
            raise ValueError("Ressources invalides.")
        if not _number(r.get("energy",0), 0, 1e15):
            raise ValueError("Énergie invalide.")
        c.resources[i] = Resources(float(r["credits"]), float(r["minerals"]), float(r.get("energy",0)))
    for entry in data["systems"]:
        s = c.systems[entry["id"]]
        if not _integer(entry["richness"], 1, 4) or not _integer(entry["shipyard"], 0, 3):
            raise ValueError("Richesse ou chantier invalide.")
        s.richness, s.shipyard = entry["richness"], entry["shipyard"]
        s.yard_owner = entry["yard_owner"]
        if s.yard_owner is not None and not _integer(s.yard_owner, 0, 2):
            raise ValueError("Propriétaire du chantier invalide.")
        if not isinstance(entry["queue"], list) or len(entry["queue"]) > 20:
            raise ValueError("File invalide.")
        for job in entry["queue"]:
            spec = SHIP_COSTS.get(job["model"])
            if spec is None or s.shipyard < spec[3] or not _number(job["remaining"], 0.001, spec[2]):
                raise ValueError("Production invalide.")
            s.queue.append(Production(job["model"], float(job["remaining"])))
    for key, maximum in (("next_ship_id", max((u.id for f in c.fleets.values() for u in f.ships), default=0)),
                         ("next_fleet_id", max(c.fleets, default=0))):
        if not _integer(data[key], maximum + 1, 1_000_000):
            raise ValueError("Compteur d'identifiants invalide.")
        setattr(c, key, data[key])
    for i in range(3):
        if data["incomes"][str(i)] != list(income(c, i)):
            raise ValueError("Revenus incohérents.")


def _decode_planets(data: dict, c: Campaign) -> None:
    registry: dict[int, Ship] = {}
    fleet_units={u.id:u for f in c.fleets.values() for u in f.ships}
    planet_ids=set()
    for entry in data["systems"]:
        system=c.systems[entry["id"]]
        raw=entry.get("planets")
        if raw is None and data["version"] < 4:
            continue
        if not isinstance(raw,list) or not 1<=len(raw)<=5:
            raise ValueError("Un système nécessite une à cinq planètes.")
        for v in raw:
            if (not _integer(v["id"],system.id*10+1,system.id*10+5) or v["id"] in planet_ids
                    or not _text(v["name"],80) or v["kind"] not in PLANET_TYPES
                    or (v["owner"] is not None and not _integer(v["owner"],0,2))
                    or not _number(v["population"],0,1e6) or not _integer(v["richness"],1,4)
                    or not _integer(v["capacity"],2,6)):
                raise ValueError("Planète invalide.")
            planet_ids.add(v["id"])
            p=Planet(v["id"],v["name"],v["kind"],v["owner"],float(v["population"]),v["richness"],v["capacity"])
            if not isinstance(v["ground"],dict) or len(v["ground"])>p.capacity:
                raise ValueError("Emplacements au sol invalides.")
            for kind,level in v["ground"].items():
                if kind not in GROUND or not _integer(level,1,3):
                    raise ValueError("Bâtiment invalide.")
            p.ground=dict(v["ground"])
            def unit(value, status, model):
                if (not isinstance(value,dict) or value["status"]!=status or value["model"]!=model
                        or model not in SHIP_TYPES or not _integer(value["id"],1,1_000_000)):
                    raise ValueError("Unité planétaire invalide.")
                _,h,sh=SHIP_TYPES[model]
                if not _number(value["hull"],0 if status=="orbital" else .001,h) or not _number(value["shield"],0,sh):
                    raise ValueError("Dégâts planétaires invalides.")
                u=Ship(value["id"],model,float(value["hull"]),float(value["shield"]),status)
                if u.id in registry:
                    raise ValueError("Identité planétaire dupliquée.")
                existing=fleet_units.get(u.id)
                if existing is not None:
                    if existing!=u or not any(f.status=="garrison" and f.system_id==system.id and
                                               f.owner==p.owner and u.id in {s.id for s in f.ships} for f in c.fleets.values()):
                        raise ValueError("Unité planétaire détournée dans une flotte.")
                    u=existing
                registry[u.id]=u
                return u
            if not isinstance(v["orbitals"],list) or len(v["orbitals"])>5:
                raise ValueError("Emplacements orbitaux invalides.")
            kinds=set()
            for b in v["orbitals"]:
                kind=b["kind"]; level=b["level"]
                if kind in kinds or (kind!="station" and kind not in DEFENSES) or not _integer(level,1,4 if kind=="station" else 1):
                    raise ValueError("Installation orbitale invalide.")
                kinds.add(kind)
                model=f"station{level}" if kind=="station" else kind
                p.orbitals.append(Building(kind,level,unit(b["unit"],"orbital",model)))
            if not isinstance(v["militia"],list) or len(v["militia"])>12:
                raise ValueError("Milice invalide.")
            for u in v["militia"]:
                if u["model"] not in ("fighter","corvette"):
                    raise ValueError("Classe de milice invalide.")
                p.militia.append(unit(u,"militia",u["model"]))
            if not isinstance(v["jobs"],list) or len(v["jobs"])>14:
                raise ValueError("File planétaire invalide.")
            job_kinds=set()
            for j in v["jobs"]:
                kind=j["kind"]; level=j["level"]
                if kind in job_kinds or kind not in set(GROUND)|set(DEFENSES)|{"station"} or not _integer(level,1,4 if kind=="station" else 3 if kind in GROUND else 1) or not _number(j["remaining"],.001,1000):
                    raise ValueError("Commande planétaire invalide.")
                job_kinds.add(kind)
                expected, _, _, duration = build_spec(p,kind)
                if level != expected or j["remaining"] > duration:
                    raise ValueError("Progression ou niveau de construction incohérent.")
                p.jobs.append(BuildJob(kind,level,float(j["remaining"])))
            if len(set(p.ground)|{j.kind for j in p.jobs if j.kind in GROUND})>p.capacity:
                raise ValueError("Emplacements au sol surchargés.")
            if len({b.kind for b in p.orbitals if b.kind!="station"}|{j.kind for j in p.jobs if j.kind in DEFENSES})>4:
                raise ValueError("Emplacements orbitaux surchargés.")
            if not _number(v["militia_clock"],0,1e10) or not _number(v["occupation"],0,1e6):
                raise ValueError("Horloge planétaire invalide.")
            p.militia_clock=float(v["militia_clock"])
            p.occupier=v["occupier"]; p.occupation=float(v["occupation"])
            if (p.occupier is not None and (not _integer(p.occupier,0,2) or p.occupier!=system.owner or p.occupier==p.owner)) or (p.occupier is None and p.occupation!=0):
                raise ValueError("Occupation incohérente.")
            system.planets.append(p)
    ensure_planets(c)
    for f in c.fleets.values():
        if f.status=="garrison" and any(u.id not in registry for u in f.ships):
            raise ValueError("Garnison sans origine planétaire.")


def _decode_navigation(entry: dict, f: Fleet, count: int) -> None:
    if 'itinerary' not in entry:
        if f.travel:
            f.itinerary=[f.travel.origin,f.travel.destination]
            f.final_destination=f.travel.destination
            f.navigation_state='transit'
        return
    path=entry['itinerary']; final=entry['final_destination']; index=entry['segment_index']; state=entry['navigation_state']
    if (not isinstance(path,list) or len(path)>1000 or not all(_integer(i,0,count-1) for i in path)
            or not _integer(index,0,max(0,len(path)-1)) or state not in
            ('idle','ordered','transit','engaged','arrived','blocked','cancelled','destroyed','merged')):
        raise ValueError('Itinéraire invalide.')
    if final is not None:
        if not _integer(final,0,count-1) or not path or path[-1]!=final or path[index]!=f.system_id:
            raise ValueError('Destination ou segment incohérent.')
        if f.travel and (index+1>=len(path) or path[index:index+2]!=[f.travel.origin,f.travel.destination]):
            raise ValueError('Progression de navigation incohérente.')
    elif path or index:
        raise ValueError('Itinéraire sans destination.')
    if f.status!='permanent' and path:
        raise ValueError('Une garnison ne voyage pas.')
    mode=entry.get('arrival_mode','move'); target=entry.get('merge_target')
    if mode not in ('move','reinforce','merge') or (target is not None and not _integer(target,1,1_000_000)) or (mode=='merge' and target is None):
        raise ValueError('Ordre d’arrivée invalide.')
    f.arrival_mode=mode; f.merge_target=target
    f.itinerary=list(path); f.final_destination=final; f.segment_index=index; f.navigation_state=state


def campaign_payload(campaign: Campaign) -> dict:
    """Instantané JSON pur, réutilisé par le réseau sans écriture de fichier."""
    return {
        "version": SAVE_VERSION, "player": campaign.player, "seed": campaign.seed,
        "systems": [asdict(s) for s in campaign.systems.values()],
        "routes": sorted(campaign.routes), "fleets": [asdict(f) for f in campaign.fleets.values()],
        "time": campaign.time, "next_ai_at": campaign.next_ai_at, "events": campaign.events,
        "step_remainder": campaign.step_remainder,
        "pending": asdict(campaign.pending) if campaign.pending is not None else None,
        "reports": [asdict(report) for report in campaign.reports],
        "next_engagement_id": campaign.next_engagement_id,
        "resources": {str(i): asdict(r) for i, r in campaign.resources.items()},
        "incomes": {str(i): list(income(campaign, i)) for i in range(3)},
        "economy_remainder": campaign.economy_remainder,
        "next_ship_id": campaign.next_ship_id, "next_fleet_id": campaign.next_fleet_id,
        "galaxy_size": len(campaign.systems),
    }
