"""Création hors ligne de six compositions synthétiques originales ; aucune lecture audio."""
from array import array
from math import pi, sin
from pathlib import Path
import sys
import wave

SCORES={
 'main_menu':(8.,(48,53,55,48),(72,76,79,74,77,79,83,79)),
 'galaxy':(8.,(45,50,48,52),(69,72,76,71,74,76,79,76)),
 'planetary':(8.,(43,46,48,43),(67,74,70,77,72,79,74,70)),
 'battle':(8.,(40,43,45,47),(64,67,71,66,69,73,71,66)),
 'victory':(3.2,(48,53,55,48),(72,76,79,84,79,83,86,84)),
 'defeat':(3.2,(45,43,41,40),(76,72,71,67,69,65,64,57)),
}
RATE=11025

def compose(name):
    duration,roots,melody=SCORES[name]
    frames=round(duration*RATE); result=array('h')
    for i in range(frames):
        t=i/RATE; step=min(7,int(t/(duration/8))); root=roots[step//2]
        note=melody[step]
        bass=440*2**((root-69)/12); lead=440*2**((note-69)/12)
        beat=t%(duration/8); attack=min(1.,beat/.035)
        envelope=attack*(.6+.4*(1-beat/(duration/8)))
        sound=.35*sin(2*pi*bass*t)+.22*sin(2*pi*bass*1.5*t)
        sound+=envelope*(.30*sin(2*pi*lead*t)+.08*sin(2*pi*lead*2*t))
        if name=='battle':
            pulse=t%.25
            sound+=.18*sin(2*pi*(75*t))*max(0.,1-pulse/.10)**3
        edge=min(1.,t/.06,(duration-t)/.08)
        result.append(round(max(-1.,min(1.,sound))*edge*14000))
    if sys.byteorder!='little': result.byteswap()
    return result.tobytes()


def main():
    directory=Path(__file__).resolve().parents[1]/'assets'/'audio'/'music'
    directory.mkdir(parents=True,exist_ok=True)
    for name in SCORES:
        path=directory/(name+'.wav')
        if path.exists():
            print('Conservé :',path.name); continue
        with wave.open(str(path),'wb') as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(RATE)
            stream.writeframes(compose(name))
        print('Créé :',path.name,path.stat().st_size,'octets')

if __name__=='__main__':
    main()
