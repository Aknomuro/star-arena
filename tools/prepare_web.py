"""Préparer un dossier Web minimal, sans installer ni exécuter d'exportateur."""
import argparse
import json
from pathlib import Path
import hashlib
from datetime import datetime, timezone
from uuid import uuid4


def files_for_web(root: Path):
    files=[root/'main.py']
    # Les serveurs et clients LAN Python sont conservés sur PC, exclus du paquet Web.
    files+=sorted(p for p in (root/'src'/'star_arena').rglob('*.py')
                  if 'network' not in p.parts or p.name in ('__init__.py','replica.py'))
    files.append(root/'web'/'browser.js')
    files.append(root/'web'/'boot.js')
    ships=root/'assets'/'ships'
    files+=sorted(ships.rglob('*.png'))
    if (ships/'manifest.json').is_file(): files.append(ships/'manifest.json')
    audio=root/'assets'/'audio'/'music'
    files+=sorted(p for p in audio.iterdir() if p.suffix.lower() in ('.wav','.ogg'))
    return files


def web_path(root: Path, source: Path):
    relative = source.relative_to(root)
    # Visible dès le préchargement Pygbag, avant l'exécution de main.py.
    return Path(*relative.parts[1:]) if relative.parts[0] == 'src' else relative


def web_bytes(root: Path, source: Path):
    if source == root/'assets/ships/manifest.json':
        original=json.loads(source.read_text(encoding='utf-8'))
        public={'schema_version':original['schema_version'],
                'entries':[{key:entry[key] for key in ('faction','class','file','forward','sha256')}
                           for entry in original['entries']]}
        return (json.dumps(public,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    return source.read_bytes()


def stage(root: Path, destination: Path):
    root=root.resolve(); destination=destination.resolve()
    if destination==root or destination in root.parents:
        raise ValueError('Choisir un dossier de préparation distinct du projet.')
    files=files_for_web(root)
    permitted={web_path(root,p).as_posix() for p in files}
    if destination.exists():
        extras=[p.relative_to(destination).as_posix() for p in destination.rglob('*')
                if p.is_file() and p.relative_to(destination).as_posix() not in permitted]
        if extras:
            raise ValueError('Dossier non isolé : choisir un nouveau dossier vide ; fichiers conservés : '+', '.join(extras[:5]))
    # Examiner tous les conflits avant la première copie.
    for source in files:
        target=destination/web_path(root,source)
        if target.exists() and target.read_bytes()!=web_bytes(root,source):
            raise ValueError('Fichier existant différent, conservé : '+str(target))
    for source in files:
        target=destination/web_path(root,source)
        target.parent.mkdir(parents=True,exist_ok=True)
        if not target.exists(): target.write_bytes(web_bytes(root,source))
    return len(files)


def verify_stage(root: Path, destination: Path):
    """Refuser tout fichier périmé, manquant ou supplémentaire avant de compiler."""
    root=root.resolve(); destination=destination.resolve()
    expected={web_path(root,p).as_posix():web_bytes(root,p) for p in files_for_web(root)}
    actual={p.relative_to(destination).as_posix() for p in destination.rglob('*') if p.is_file()}
    if actual!=set(expected):
        raise ValueError('Staging incomplet ou non isolé ; régénérer avec --refresh. '
                         +'Manquants : '+', '.join(sorted(set(expected)-actual)[:4])
                         +' ; supplémentaires : '+', '.join(sorted(actual-set(expected))[:4]))
    for name,data in expected.items():
        if (destination/name).read_bytes()!=data:
            raise ValueError('Ancienne copie détectée : '+name+' ; régénérer avec --refresh.')
    return {name:hashlib.sha256(data).hexdigest() for name,data in sorted(expected.items())}


def refresh_stage(root: Path, destination: Path):
    """Archiver arena en entier puis le recréer ; aucun fichier utilisateur supprimé."""
    root=root.resolve()
    build=root/'web_build'; expected=build/'arena'
    destination=destination.absolute()
    def linked(path):
        return path.is_symlink() or getattr(path,'is_junction',lambda:False)()
    if destination!=expected or linked(build) or linked(destination) or not destination.resolve().is_relative_to(build.resolve()) or not build.resolve().is_relative_to(root):
        raise ValueError('--refresh est réservé au vrai dossier web_build/arena dans ce projet, sans lien externe.')
    inventory(root)  # Examiner les sources avant de toucher à l'ancienne copie.
    backup=None
    if destination.exists():
        history=build/'stage_history'
        if linked(history) or not history.resolve().is_relative_to(build.resolve()):
            raise ValueError('Dossier de conservation non sûr ; ancienne copie conservée en place.')
        history.mkdir(parents=True,exist_ok=True)
        stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        backup=history/('arena-'+stamp+'-'+uuid4().hex[:8])
        # Source et cible résolues explicitement dans web_build avant ce déplacement de dossier.
        if not backup.resolve().is_relative_to(build.resolve()):
            raise ValueError('Chemin de conservation hors du projet.')
        destination.rename(backup)
    count=stage(root,destination)
    hashes=verify_stage(root,destination)
    return {'staged_files':count,'verified_files':len(hashes),
            'previous_stage_preserved':backup.relative_to(root).as_posix() if backup else None}


def inventory(root: Path):
    files=files_for_web(root)
    missing=[str(p.relative_to(root)) for p in files if not p.is_file()]
    if missing:
        raise ValueError('Fichiers Web manquants : '+', '.join(missing))
    # Les chemins sont vérifiés exactement, y compris sur un Windows insensible à la casse.
    for source in files:
        current=root
        for part in source.relative_to(root).parts:
            if part not in {p.name for p in current.iterdir()}:
                raise ValueError('Casse de chemin incorrecte : '+str(source))
            current=current/part
        if source.is_symlink() or not source.resolve().is_relative_to(root.resolve()):
            raise ValueError('Lien externe non autorisé dans le paquet : '+str(source))
    ships=json.loads((root/'assets/ships/manifest.json').read_text(encoding='utf-8'))
    # Le catalogue réel est également validé par les tests de sprites.
    pngs=[p for p in files if p.suffix=='.png']
    if len(pngs)!=9 or not ships:
        raise ValueError('Les neuf sprites et leur manifeste sont requis.')
    tracks=('main_menu','galaxy','planetary','battle','victory','defeat')
    music=root/'assets/audio/music'
    if any(not any((music/(name+suffix)).is_file() for suffix in ('.ogg','.wav')) for name in tracks):
        raise ValueError('Une des six musiques est absente ; paquet incomplet.')
    return {'files':[{'path':web_path(root,p).as_posix(),'bytes':len(web_bytes(root,p)),
                     'sha256':hashlib.sha256(web_bytes(root,p)).hexdigest()} for p in files],
            'count':len(files),'bytes':sum(len(web_bytes(root,p)) for p in files),
            'sprites':len(pngs),'music_tracks':len(tracks),'effects':'7 effets synthétisés par presentation/audio.py',
            'browser_tested':False,'export_executed':False,
            'excluded':['.venv','Godot et archives','saves','settings','tests','__pycache__','serveur et client LAN']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',type=Path)
    parser.add_argument('--refresh',action='store_true',help='Conserver puis régénérer web_build/arena.')
    parser.add_argument('--verify-stage',type=Path,help='Refuser toute copie différente des sources actuelles.')
    parser.add_argument('--report',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    result=inventory(root)
    if args.refresh and not args.stage:
        parser.error('--refresh nécessite --stage web_build/arena')
    if args.stage:
        if args.refresh: result.update(refresh_stage(root,args.stage))
        else: result['staged_files']=stage(root,args.stage)
    if args.verify_stage:
        result['verified_stage_files']=len(verify_stage(root,args.verify_stage))
    if args.report:
        (root/'docs/WEB_PACKAGE_0_4_1.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':
    main()
