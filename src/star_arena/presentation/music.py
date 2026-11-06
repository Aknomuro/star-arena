"""Musique en streaming via mixer.music ; fondus non bloquants et absence silencieuse."""
from math import isfinite
from pathlib import Path
import struct
from star_arena.config import project_root

TRACKS={'menu':'main_menu.ogg','galaxy':'galaxy.ogg','system':'planetary.ogg',
        'battle':'battle.ogg','victory':'victory.ogg','defeat':'defeat.ogg'}
FADE_SECONDS=.75


def valid_pcm_wav(path: Path) -> bool:
    """Inspecter le conteneur PCM 16 bits sans wave (absent du runtime WASM)."""
    size=path.stat().st_size
    with path.open('rb') as stream:
        header=stream.read(12)
        if len(header)!=12 or header[:4]!=b'RIFF' or header[8:]!=b'WAVE':
            return False
        end=struct.unpack('<I',header[4:8])[0]+8
        if end>size or end<36:
            return False
        alignment=None; data_size=0
        for _ in range(128):
            if stream.tell()+8>end:
                break
            chunk=stream.read(8)
            kind,length=chunk[:4],struct.unpack('<I',chunk[4:])[0]
            start=stream.tell()
            if start+length>end:
                return False
            if kind==b'fmt ':
                if length<16: return False
                encoding,channels,rate,byte_rate,block,bits=struct.unpack('<HHIIHH',stream.read(16))
                if encoding!=1 or channels not in (1,2) or rate<=0 or bits!=16 or block!=channels*2 or byte_rate!=rate*block:
                    return False
                alignment=block
            elif kind==b'data':
                data_size=length
            stream.seek(start+length+(length%2))
        return alignment is not None and data_size>0 and data_size%alignment==0


def inventory(root: Path) -> dict[str,dict]:
    result={}
    for category,filename in TRACKS.items():
        candidates=(root/filename,root/Path(filename).with_suffix('.wav'))
        row={'file':filename,'present':False,'bytes':0,'ogg_header':False,'wav_header':False,'valid_header':False}
        for path in candidates:
            try:
                exists=path.is_file(); size=path.stat().st_size if exists else 0
                ogg=False; wav=False
                if exists and 4<=size<=100_000_000:
                    if path.suffix=='.ogg':
                        with path.open('rb') as stream: ogg=stream.read(4)==b'OggS'
                    else:
                        wav=valid_pcm_wav(path)
                candidate={'file':path.name,'present':exists,'bytes':size,'ogg_header':ogg,'wav_header':wav,'valid_header':ogg or wav}
                if exists and not row['present']: row=candidate
                if ogg or wav:
                    row=candidate; break
            except (OSError,ValueError,struct.error,EOFError):
                continue
        result[category]=row
    return result


class MusicManager:
    def __init__(self, backend=None, root: Path | None=None):
        self.backend=backend
        self.root=root if root is not None else project_root()/'assets'/'audio'/'music'
        self.available=inventory(self.root)
        self.desired=None
        self.current=None
        self.level=0.
        self.volume=.28
        self.enabled=True
        self.suspended=False
        self.errors={}
        self.failed=False
        self.last_gain=None
        self.ducking=False
        self.duck_gain=1.

    def request(self, category: str, token=None) -> None:
        if category not in TRACKS:
            category='menu'
        key=(category,token)
        if key!=self.desired:
            self.desired=key

    def configure(self, enabled: bool, volume: float) -> None:
        if not isinstance(volume,(int,float)) or not isfinite(volume):
            volume=0.
        self.enabled=bool(enabled)
        self.volume=max(0.,min(1.,volume))
        # Le mute ne recharge pas la piste ; son enveloppe reste conservée.

    def suspend(self, value: bool) -> None:
        if self.suspended==value:
            return
        self.suspended=value
        if self.backend is None or self.failed:
            return
        try:
            if self.backend.mixer.get_init() and self.current is not None:
                if value: self.backend.mixer.music.pause()
                else: self.backend.mixer.music.unpause()
        except self.backend.error as error:
            self.errors['device']=str(error); self.failed=True

    def update(self, dt: float) -> None:
        if self.backend is None or self.failed or self.suspended:
            return
        if not isinstance(dt,(int,float)) or not isfinite(dt) or dt<0:
            return
        try:
            if not self.backend.mixer.get_init():
                return
            music=self.backend.mixer.music
            step=min(dt,.2)/FADE_SECONDS
            if self.current!=self.desired:
                self.level=max(0.,self.level-step)
                if self.level<=1e-9:
                    music.stop()
                    self.current=self.desired
                    self.last_gain=None
                    if self.current is not None:
                        category=self.current[0]
                        row=self.available[category]
                        if row['present'] and row['valid_header']:
                            try:
                                music.load(str(self.root/row['file']))
                                music.set_volume(0.)
                                music.play(loops=0 if category in ('victory','defeat') else -1)
                            except (self.backend.error,OSError) as error:
                                self.errors[category]=str(error)
                                music.stop()
            else:
                self.level=min(1.,self.level+step)
            target=.3 if self.ducking else 1.
            change=min(dt,.2)*4
            self.duck_gain+=max(-change,min(change,target-self.duck_gain))
            gain=self.level*self.volume*self.duck_gain if self.enabled else 0.
            if gain!=self.last_gain:
                music.set_volume(gain)
                self.last_gain=gain
        except self.backend.error as error:
            self.errors['device']=str(error)
            self.failed=True

    def retry_device(self) -> None:
        self.failed=False
        self.current=None
        self.level=0.
        self.last_gain=None
