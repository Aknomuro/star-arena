"""Navigation pondérée par le temps de vol ; aucun saut hors des routes."""
from heapq import heappop, heappush
from star_arena.config import TRAVEL_SPEED
from star_arena.domain.models import Campaign, Fleet, Travel


def duration(c: Campaign, a: int, b: int) -> float:
    return max(2.,c.distance(a,b)/TRAVEL_SPEED)


def find_path(c: Campaign, origin: int, destination: int) -> list[int]:
    if origin not in c.systems or destination not in c.systems:
        return []
    adjacency={i:[] for i in c.systems}
    for a,b in sorted(c.routes):
        adjacency[a].append(b); adjacency[b].append(a)
    costs={origin:0.}; previous={}; queue=[(0.,origin)]
    while queue:
        cost,node=heappop(queue)
        if cost!=costs[node]: continue
        if node==destination:
            path=[node]
            while node!=origin:
                node=previous[node]; path.append(node)
            return path[::-1]
        for other in adjacency[node]:
            candidate=cost+duration(c,node,other)
            if candidate<costs.get(other,float('inf')):
                costs[other]=candidate; previous[other]=node
                heappush(queue,(candidate,other))
    return []


def clear_order(f: Fleet, state: str='arrived') -> None:
    f.final_destination=None; f.itinerary.clear(); f.segment_index=0; f.navigation_state=state
    f.arrival_mode="move"; f.merge_target=None


def set_order(c: Campaign, f: Fleet, destination: int) -> str:
    origin=f.travel.destination if f.travel else f.system_id
    tail=find_path(c,origin,destination)
    if not tail: return 'Aucune route valide vers ce système.'
    f.arrival_mode="move"; f.merge_target=None
    f.final_destination=destination
    f.itinerary=([f.travel.origin]+tail) if f.travel else tail
    f.segment_index=0
    if f.travel:
        f.navigation_state='transit'
    else:
        f.navigation_state="ordered"
        continue_order(c,f)
    return ''


def continue_order(c: Campaign, f: Fleet, planner=None) -> None:
    if f.final_destination is None or f.travel or f.destroyed or c.pending:
        return
    if f.system_id==f.final_destination:
        f.navigation_state="arrived"
        return
    if any(other.owner!=f.owner and not other.destroyed and other.travel and
           other.travel.destination==f.system_id and other.travel.elapsed>=other.travel.duration
           for other in c.fleets.values()):
        return
    if f.system_id==f.final_destination:
        f.navigation_state='arrived'
        return
    index=f.segment_index
    next_node=f.itinerary[index+1] if index+1<len(f.itinerary) and f.itinerary[index]==f.system_id else None
    if next_node not in c.neighbors(f.system_id):
        replacement=planner.find(f.system_id,f.final_destination) if planner else find_path(c,f.system_id,f.final_destination)
        if not replacement:
            if f.navigation_state!='blocked': c.log(f'Flotte {f.id} bloquée : route indisponible.')
            f.navigation_state='blocked'; return
        past=f.itinerary[:f.segment_index]
        f.itinerary=past+replacement; f.segment_index=len(past); next_node=replacement[1]
    f.travel=Travel(f.system_id,next_node,0.,duration(c,f.system_id,next_node))
    f.navigation_state='transit'


def arrived(f: Fleet, system_id: int) -> None:
    if f.itinerary and f.segment_index+1<len(f.itinerary) and f.itinerary[f.segment_index+1]==system_id:
        f.segment_index+=1
    if f.final_destination==system_id:
        f.navigation_state='arrived'


def remaining_time(c: Campaign, f: Fleet) -> float:
    if f.navigation_state=='blocked': return float('inf')
    value=max(0.,f.travel.duration-f.travel.elapsed) if f.travel else 0.
    start=f.segment_index+1 if f.travel else f.segment_index
    return value+sum(duration(c,a,b) for a,b in zip(f.itinerary[start:],f.itinerary[start+1:]))


class RoutePlanner:
    """Cache borné ; invalidation automatique sur changement des routes ou positions."""
    def __init__(self,campaign):
        self.campaign=campaign; self.signature=None; self.cache={}; self.searches=0

    def find(self,origin,destination):
        c=self.campaign
        signature=(frozenset(c.routes),tuple((i,s.position) for i,s in c.systems.items()))
        if signature!=self.signature:
            self.signature=signature; self.cache.clear()
        key=(origin,destination)
        if key not in self.cache:
            if len(self.cache)>=128: self.cache.pop(next(iter(self.cache)))
            self.cache[key]=tuple(find_path(c,origin,destination)); self.searches+=1
        return list(self.cache[key])
