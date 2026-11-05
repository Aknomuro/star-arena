"""Musique en streaming via mixer.music ; fondus non bloquants et absence silencieuse."""
from math import isfinite
from pathlib import Path
import wave

TRACKS={'menu':'main_menu.ogg','galaxy':'galaxy.ogg','system':'planetary.ogg',
        'battle':'battle.ogg','victory':'victory.ogg','defeat':'defeat.ogg'}
FADE_SECONDS=.75


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
                        with wave.open(str(path),'rb') as stream:
                            wav=(stream.getnchannels() in (1,2) and stream.getsampwidth()==2
                                 and stream.getframerate()>0 and stream.getnframes()>0
                                 and size>=44+stream.getnframes()*stream.getnchannels()*2)
                candidate={'file':path.name,'present':exists,'bytes':size,'ogg_header':ogg,'wav_header':wav,'valid_header':ogg or wav}
                if exists and not row['present']: row=candidate
                if ogg or wav:
                    row=candidate; break
            except (OSError,wave.Error,EOFError):
                continue
        result[category]=row
    return result


class MusicManager:
    def __init__(self, backend=None, root: Path | None=None):
        self.backend=backend
        self.root=root if root is not None else Path(__file__).resolve().parents[3]/'assets'/'audio'/'music'
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
