"""Create small original procedural WAV cues for the online lobby.

No sampled game audio is used. The generated files are short chip-style tones
that remain safe to redistribute with the project.
"""
from array import array
from math import pi, sin
from pathlib import Path
import wave

RATE=22050
ROOT=Path(__file__).resolve().parents[1]/'assets/audio'

def tone(path, notes, seconds, volume=.22):
    samples=array('h')
    total=round(RATE*seconds)
    for index in range(total):
        t=index/RATE;position=(t/seconds)*len(notes)
        note=notes[min(len(notes)-1,int(position))]
        local=position%1
        envelope=min(1,local*30,max(0,(1-local)*8))
        wave_a=sin(2*pi*note*t)
        wave_b=sin(2*pi*note*2*t)*.22
        samples.append(round(32767*volume*envelope*(wave_a+wave_b)))
    path.parent.mkdir(parents=True,exist_ok=True)
    with wave.open(str(path),'wb') as output:
        output.setparams((1,2,RATE,len(samples),'NONE','not compressed'))
        output.writeframes(samples.tobytes())

def loop(path):
    notes=(220,277.18,329.63,415.3,329.63,277.18,246.94,329.63)
    tone(path,notes*4,12,.12)

def main():
    loop(ROOT/'music'/'online_lobby.wav')
    tone(ROOT/'sfx'/'actions'/'portal-online.wav',(329.63,493.88,659.25),.42,.28)
    tone(ROOT/'sfx'/'actions'/'server-created.wav',(261.63,329.63,392,523.25),.55,.3)
    tone(ROOT/'sfx'/'actions'/'server-started.wav',(392,493.88,587.33,783.99),.65,.32)

if __name__=='__main__':main()
