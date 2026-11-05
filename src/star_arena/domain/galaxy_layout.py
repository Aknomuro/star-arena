"""Carte arrondie déterministe ; arbre de connexion et raccourcis sans croisements."""
from math import cos, sin, pi, sqrt, hypot


def round_layout(systems, capitals, rng):
    count=len(systems); radius=1300.*sqrt(count/60)
    for index,uid in enumerate(capitals):
        a=index*2*pi/3-.5
        systems[uid].position=(radius*cos(a),radius*.92*sin(a))
    placed=[systems[i].position for i in capitals]
    for uid in systems:
        if uid in capitals: continue
        candidates=[]
        for _ in range(24):
            angle=rng.random()*2*pi
            r=radius*(rng.random()**.6)*.98
            candidates.append((r*cos(angle),r*.92*sin(angle)))
        point=max(candidates,key=lambda p:min(hypot(p[0]-q[0],p[1]-q[1]) for q in placed))
        systems[uid].position=point; placed.append(point)
    def distance(a,b):
        p,q=systems[a].position,systems[b].position
        return hypot(p[0]-q[0],p[1]-q[1])
    edges=sorted((distance(a,b),a,b) for a in systems for b in systems if a<b)
    parent=list(range(count))
    def root(i):
        while parent[i]!=i:
            parent[i]=parent[parent[i]]; i=parent[i]
        return i
    routes=set()
    for _,a,b in edges:
        x,y=root(a),root(b)
        if x!=y:
            parent[x]=y; routes.add((a,b))
    def cross(a,b,c,d):
        if len({a,b,c,d})<4: return False
        p,q,r,s=[systems[i].position for i in (a,b,c,d)]
        def orient(u,v,w): return (v[0]-u[0])*(w[1]-u[1])-(v[1]-u[1])*(w[0]-u[0])
        return orient(p,q,r)*orient(p,q,s)<0 and orient(r,s,p)*orient(r,s,q)<0
    degree={i:sum(i in edge for edge in routes) for i in systems}
    limit=radius/sqrt(count)*3.2
    extra=0
    for length,a,b in edges:
        if extra>=count//3: break
        if (a,b) in routes or length>limit or degree[a]>=4 or degree[b]>=4: continue
        if any(cross(a,b,c,d) for c,d in routes): continue
        routes.add((a,b)); degree[a]+=1; degree[b]+=1; extra+=1
    return routes
