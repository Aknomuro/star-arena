"""Préférences utilisateur indépendantes des campagnes, sans initialisation audio."""
from dataclasses import asdict, dataclass
import json
from math import isfinite
from pathlib import Path
from tempfile import NamedTemporaryFile


@dataclass
class AudioSettings:
    master_volume: float = .8
    music_volume: float = .35
    effects_volume: float = .7
    music_enabled: bool = True
    effects_enabled: bool = True
    muted: bool = False

    def gain(self, channel: str) -> float:
        if self.muted or not getattr(self,channel+'_enabled'):
            return 0.
        return self.master_volume*getattr(self,channel+'_volume')


def decode_settings(value: object) -> AudioSettings:
    if not isinstance(value,dict) or value.get('version')!=1:
        raise ValueError('Configuration audio incompatible.')
    data=value.get('audio')
    if not isinstance(data,dict):
        raise ValueError('Configuration audio incomplète.')
    settings=AudioSettings()
    for key in ('master_volume','music_volume','effects_volume'):
        v=data.get(key)
        if isinstance(v,bool) or not isinstance(v,(int,float)) or not isfinite(v) or not 0<=v<=1:
            raise ValueError('Volume audio invalide.')
        setattr(settings,key,float(v))
    for key in ('music_enabled','effects_enabled','muted'):
        if type(data.get(key)) is not bool:
            raise ValueError('Option audio invalide.')
        setattr(settings,key,data[key])
    return settings


def load_settings(path: Path) -> AudioSettings:
    with path.open('rb') as stream:
        raw=stream.read(8193)
    if len(raw)>8192:
        raise ValueError('Configuration audio trop volumineuse.')
    return decode_settings(json.loads(raw.decode('utf-8')))


def save_settings(settings: AudioSettings, path: Path) -> None:
    value={'version':1,'audio':asdict(settings)}
    decode_settings(value)
    # Préserver un fichier incompatible ou corrompu au lieu de le remplacer.
    if path.exists():
        load_settings(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=None
    try:
        with NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,prefix='.audio-',suffix='.tmp',delete=False) as stream:
            temporary=Path(stream.name)
            json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
            stream.write('\n')
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
