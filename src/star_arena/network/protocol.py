"""Protocole JSON strict. Aucun objet Python reçu n'est exécuté."""
import json
from star_arena.persistence import _unique_keys, _invalid_constant

PROTOCOL=1
BUILD='0.4.0'


def dumps(value):
    return json.dumps(value,ensure_ascii=False,allow_nan=False,separators=(',',':'))


def loads(text):
    value=json.loads(text,object_pairs_hook=_unique_keys,parse_constant=_invalid_constant)
    if not isinstance(value,dict) or len(value)>24: raise ValueError('Message JSON invalide.')
    return value


def integer(value,minimum=0,maximum=1_000_000):
    if type(value) is not int or not minimum<=value<=maximum: raise ValueError('Entier réseau invalide.')
    return value


def text(value,maximum=64):
    if not isinstance(value,str) or not 1<=len(value)<=maximum or not value.isprintable():
        raise ValueError('Texte réseau invalide.')
    return value


def keys(data,required,optional=()):
    if not isinstance(data,dict) or not set(required)<=data.keys() or not data.keys()<=set(required)|set(optional):
        raise ValueError('Champs réseau inconnus ou manquants.')


def validate_state(value,session):
    keys(value,('type','protocol','session','name','revision','started','size','seed','host','paused','speed','participants','campaign','battle_mode'))
    if value['type']!='state' or type(value['protocol']) is not int or value['protocol']!=PROTOCOL or value['session']!=session:
        raise ValueError('État de session incompatible.')
    text(value['name'],40); integer(value['revision'],0,2**53-1); integer(value['seed'],0,2**31-1)
    if type(value['started']) is not bool or type(value['paused']) is not bool:
        raise ValueError('Indicateur de session invalide.')
    if integer(value['size'],15,100) not in (15,30,60,100) or integer(value['speed'],1,4) not in (1,2,4):
        raise ValueError('Réglage de session invalide.')
    people=value['participants']
    if not isinstance(people,list) or not 1<=len(people)<=3: raise ValueError('Participants invalides.')
    ids=set(); factions=set()
    for p in people:
        keys(p,('id','name','faction','online'))
        uid=text(p['id'],32); faction=integer(p['faction'],0,2); text(p['name'],24)
        if uid in ids or faction in factions or type(p['online']) is not bool: raise ValueError('Attribution invalide.')
        ids.add(uid); factions.add(faction)
    if value['host'] not in ids or (value['started'] and not isinstance(value['campaign'],dict)):
        raise ValueError('Hôte ou campagne invalide.')
    if value['campaign'] is not None and not isinstance(value['campaign'],dict): raise ValueError('Campagne invalide.')
    text(value['battle_mode'],128)
    return value
