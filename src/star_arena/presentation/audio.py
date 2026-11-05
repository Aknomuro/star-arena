"""Effets synthétiques originaux, synthétisés en mémoire au lancement manuel uniquement."""
from array import array
from math import pi, sin
from random import Random
import sys

SAMPLE_RATE=22050
# durée, fréquence initiale, fréquence finale, proportion de bruit
TONES={'click':(.045,650,850,0.), 'order':(.10,320,640,0.),
       'laser':(.12,1500,260,.04), 'impact':(.10,150,65,.65),
       'shield':(.16,780,380,.12), 'explosion':(.28,95,25,.85),
       'complete':(.23,440,880,0.)}


def make_pcm(name: str, sample_rate: int = SAMPLE_RATE, channels: int = 1) -> bytes:
    duration,start,end,noise=TONES[name]
    count=round(duration*sample_rate)
    rng=Random(76)
    samples=array('h')
    phase=0.
    for i in range(count):
        t=i/count
        phase+=2*pi*(start+(end-start)*t)/sample_rate
        envelope=min(1.,i/(sample_rate*.006))*(1-t)**2
        value=((1-noise)*sin(phase)+noise*rng.uniform(-1,1))*envelope
        samples.extend([round(value*16000)]*channels)
    if sys.byteorder!='little':
        samples.byteswap()
    return samples.tobytes()


class SoundEffects:
    def __init__(self, backend=None):
        self.backend=backend
        self.enabled=False
        self.volume=.22
        self.error=''
        self.sounds={}
        self.last_played={}
        self.format=None
        self.dropped=0
        self.last_started=None
        self.devices=[]
        self.devices_error=""

    def set_enabled(self, enabled: bool) -> bool:
        if not enabled:
            self.enabled=False
            self.stop()
            return False
        if self.backend is None:
            return False
        try:
            if not self.backend.mixer.get_init():
                self.backend.mixer.init(frequency=SAMPLE_RATE,size=-16,channels=1,buffer=512)
                self.backend.mixer.set_num_channels(8)
            actual=self.backend.mixer.get_init()
            if not actual or actual[1]!=-16 or actual[2] not in (1,2) or not 8000<=actual[0]<=96000:
                self.error='Format audio non pris en charge (PCM 16 bits mono/stéréo requis).'
                self.enabled=False
                return False
            if actual!=self.format:
                self.sounds.clear(); self.format=actual
            if hasattr(self.backend.mixer,'set_reserved'):
                self.backend.mixer.set_reserved(2)
            if getattr(self.backend,'__name__','')=='pygame' and not self.devices:
                try:
                    from pygame._sdl2.audio import get_audio_device_names
                    self.devices=list(get_audio_device_names(False))
                except (ImportError,RuntimeError,self.backend.error) as error:
                    self.devices_error=str(error)
            self.enabled=True
            self.error=''
        except self.backend.error as error:
            self.error=str(error)
            self.enabled=False
        return self.enabled

    def set_volume(self, value: float) -> None:
        self.volume=max(0.,min(1.,value))
        try:
            for sound in self.sounds.values():
                sound.set_volume(self.volume)
        except self.backend.error as error:
            self.error=str(error)
            self.enabled=False

    def stop(self):
        if self.backend is None:
            return
        try:
            if self.backend.mixer.get_init():
                self.backend.mixer.stop()
        except self.backend.error:
            self.enabled=False

    def play(self, name: str):
        if not self.enabled or self.volume<=0 or name not in TONES:
            return
        now=self.backend.time.get_ticks()
        delay=100 if name in ('laser','impact','shield') else 180 if name=='explosion' else 45
        if now-self.last_played.get(name,-10000)<delay:
            return
        try:
            if name not in self.sounds:
                sound=self.backend.mixer.Sound(buffer=make_pcm(name,self.format[0],self.format[2]))
                sound.set_volume(self.volume)
                self.sounds[name]=sound
            if hasattr(self.backend.mixer,'find_channel'):
                if name in ('click','order','complete'):
                    channel=self.backend.mixer.Channel(0 if name=='click' else 1)
                else:
                    channel=self.backend.mixer.find_channel()
                if channel is None:
                    self.dropped+=1
                    return
                channel.play(self.sounds[name])
            else:
                self.sounds[name].play()
            self.last_played[name]=now
            self.last_started=now
        except self.backend.error as error:
            self.error=str(error)
            self.enabled=False
