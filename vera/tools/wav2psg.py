"""Experimental polyphonic audio -> VERA PSG, analyzed OFFLINE, not on 6502.

Requires numpy and ffmpeg. Emits veramusic 60Hz register-event format and a
16-bit WAV preview using the AppleWin PSG volume table. This is an approximate
transcription, NOT lossless audio conversion or an original instrumental score.
Usage: python vera/tools/wav2psg.py [input.ogg|input.wav] [output.psg]
"""
from pathlib import Path
import argparse
import json
import subprocess
import wave
import numpy as np

VERA=Path(__file__).resolve().parents[1]
CLOCK=25000000/512
VOLUME=np.array([0,4,8,12,16,17,18,20,21,22,23,25,26,28,30,31,
    33,35,37,40,42,45,47,50,53,56,60,63,67,71,75,80,
    85,90,95,101,107,113,120,127,135,143,151,160,170,180,191,202,
    214,227,241,255,270,286,303,321,341,361,382,405,429,455,482,511],dtype=float)/4

def decode(file):
    result=subprocess.run(['ffmpeg','-v','error','-i',str(file),'-ac','1',
        '-ar','16000','-f','f32le','pipe:1'],check=True,stdout=subprocess.PIPE)
    return np.frombuffer(result.stdout,dtype='<f4').astype(float)

def analyze(audio):
    size=4096;frames=int(np.ceil(len(audio)/16000*60));window=np.hanning(size)
    padded=np.pad(audio,(size//2,size//2))
    spectra=np.empty((frames,size//2+1),dtype=np.float32)
    for frame in range(frames):
        at=round(frame*16000/60)
        spectra[frame]=np.abs(np.fft.rfft(padded[at:at+size]*window))
    # Time-median separates sustained pitched energy from short drum transients.
    views=np.lib.stride_tricks.sliding_window_view(
        np.pad(spectra,((7,7),(0,0)),mode='edge'),15,axis=0)
    harmonic=np.median(views,axis=-1)
    notes=np.arange(33,97);freq=440*2**((notes-69)/12)
    bins=np.round(freq*size/16000).astype(int)
    offsets=np.arange(-1,2)
    harmonics=np.arange(1,7)
    lookup=np.clip(np.round(freq[:,None]*harmonics*size/16000).astype(int),0,size//2)
    amplitudes=np.zeros((frames,len(notes)))
    drums=np.zeros((frames,2))
    for frame in range(frames):
        residual=harmonic[frame].copy()
        threshold=float(np.max(residual))*0.06
        for voice in range(8):
            magnitudes=np.max(residual[np.clip(lookup[:,:,None]+offsets,0,size//2)],axis=2)
            # Require a fundamental, not just harmonics of lower notes.
            score=magnitudes[:,0]+np.sum(magnitudes[:,1:]/harmonics[1:]**1.4,axis=1)*0.4
            score[magnitudes[:,0]<threshold]=0
            candidate=int(np.argmax(score))
            if score[candidate]<=threshold:break
            amplitudes[frame,candidate]=magnitudes[candidate,0]
            # Remove partials to avoid turning every harmonic into a fake note.
            for center in lookup[candidate]:
                lo=max(0,center-2);hi=min(len(residual),center+3)
                residual[lo:hi]*=0.08
        transient=np.maximum(spectra[frame]-harmonic[frame],0)
        drums[frame]=[np.mean(transient[8:64]),np.mean(transient[512:1536])]
    # Three-frame median removes isolated octave/chord detection glitches.
    amplitudes=np.median(np.stack([np.roll(amplitudes,-1,axis=0),amplitudes,
        np.roll(amplitudes,1,axis=0)]),axis=0)
    amplitudes[[0,-1]]=0
    return notes,amplitudes,drums

def route_short_transients(notes,amplitudes,drums):
    """Route short bass smears and coincident treble blips to struck sounds.
    No timestamp-specific muting: apply the same detector to the whole song.
    Sustained bass and unrelated short melodic notes are left intact.
    """
    levels=amplitudes.copy();hits=drums.copy()
    peak=np.percentile(levels[levels>0],99) if np.any(levels) else 1
    baseline=np.maximum(np.percentile(drums,98,axis=0),0.001)
    for column,note in enumerate(notes):
        if 52<=note<72:continue
        active=levels[:,column]>peak*0.045
        bounds=np.flatnonzero(np.diff(np.r_[False,active,False]))
        for start,end in zip(bounds[::2],bounds[1::2]):
            maximum=6 if note<52 else 4
            if end-start>maximum:continue
            lo=max(0,start-3);hi=min(len(drums),end+3)
            if np.max(drums[lo:hi,0]/baseline[0])<0.2:continue
            # Bass clusters are one tom hit, not a flurry of pitched voices.
            kind=0 if note<52 else 1
            onset=start+int(np.argmax(levels[start:end,column]))
            hits[onset,kind]=max(hits[onset,kind],baseline[kind]*0.65)
            levels[start:end,column]=0
    return levels,hits

def percussion(drums):
    """Two alternating taiko strikes; overlapping low bodies, no woodblock."""
    result=np.zeros((len(drums),4,4),dtype=np.uint8)
    peaks=np.maximum(np.percentile(drums,98,axis=0),0.001)
    ages=[99,99];strength=[0.0,0.0];cooldown=0;next_voice=0
    for frame in range(len(drums)):
        ages=[age+1 for age in ages];cooldown=max(0,cooldown-1)
        value=drums[frame,0]/peaks[0]
        previous=drums[frame-1,0]/peaks[0] if frame else 0
        following=drums[frame+1,0]/peaks[0] if frame+1<len(drums) else 0
        if not cooldown and value>0.38 and value>previous and value>=following:
            ages[next_voice]=0;strength[next_voice]=min(1.0,value)
            next_voice^=1;cooldown=9
        for voice in range(4):
            strike=voice//2;partial=voice%2;age=ages[strike]
            length=18 if partial==0 else 11
            # Large membrane, not a high pitched wooden click. Alternating
            # strike pairs preserve the tail of the first "dong" under the next.
            hz=72 if partial==0 else 128
            frequency=int(round(hz*131072/CLOCK))
            attack=0.65 if age==0 else 1.0
            amplitude=(112 if partial==0 else 74)*strength[strike]*attack*np.exp(-max(0,age-1)/(4.2 if partial==0 else 2.1)) if age<length else 0
            volume=int(np.argmin(np.abs(VOLUME-amplitude))) if amplitude else 0
            result[frame,voice]=[frequency&255,frequency>>8,0xC0|volume if volume else 0,0x80]
    return result

def encode(notes,amplitudes,drums):
    amplitudes,drums=route_short_transients(notes,amplitudes,drums)
    frames=len(amplitudes);registers=np.zeros((frames,64),dtype=np.uint8)
    slots=[None]*12;release=[0]*12
    peak=np.percentile(amplitudes[amplitudes>0],99) if np.any(amplitudes) else 1
    hits=percussion(drums)
    for frame in range(frames):
        levels=amplitudes[frame]
        chosen=list(np.flatnonzero(levels>peak*0.045))
        chosen=sorted(chosen,key=lambda n:levels[n],reverse=True)[:8]
        # Keep stable channel ownership; don't scramble oscillator phases.
        for channel,note in enumerate(slots):
            if note not in chosen:
                release[channel]+=1
                if release[channel]>=3:slots[channel]=None
            else:release[channel]=0
        for note in chosen:
            if note not in slots:
                try:channel=slots.index(None)
                except ValueError:continue
                slots[channel]=note;release[channel]=0
        for channel,note in enumerate(slots):
            if note is None:
                registers[frame,channel*4+3]=0x80
                continue
            frequency=int(round(440*2**((int(notes[note])-69)/12)*131072/CLOCK))
            amplitude=min(1.0,(levels[note]/peak)**0.65)*108
            volume=int(np.argmin(np.abs(VOLUME-amplitude)))
            volume=(volume//3)*3 # coarser dynamics reduce event traffic
            registers[frame,channel*4:channel*4+4]=[
                frequency&255,frequency>>8,0xC0|volume if volume else 0,0x80]
        registers[frame,48:64]=hits[frame].reshape(16)
        # Envelope updates at 20Hz; pitch changes still use the full 60Hz clock.
        if frame%3 and frame:
            for channel in range(12): # Never smear a percussion attack/decay.
                i=channel*4
                if np.array_equal(registers[frame,i:i+2],registers[frame-1,i:i+2]):
                    registers[frame,i+2]=registers[frame-1,i+2]
    stream=bytearray();previous=np.zeros(64,dtype=np.uint8);counts=[]
    for frame,regs in enumerate(registers):
        changed=np.arange(64) if frame==0 else np.flatnonzero(regs!=previous)
        counts.append(len(changed));stream.append(len(changed))
        for reg in changed:stream.extend((int(reg),int(regs[reg])))
        previous=regs
    # Silence all channels before looping to the complete first-frame state.
    stream.append(16)
    for channel in range(16):stream.extend((channel*4+2,0))
    stream.extend((255,0,0))
    return stream,registers,counts

def preview(registers,file):
    # Hardware-level gain (no peak normalization). Triangle PSG voices are
    # approximated with continuous phase; noise is deterministic white noise.
    rate=48000;step=np.arange(800);phase=np.zeros(16);rng=np.random.default_rng(1)
    with wave.open(str(file),'wb') as wav:
        wav.setnchannels(2);wav.setsampwidth(2);wav.setframerate(rate)
        for regs in registers:
            block=np.zeros((800,2))
            for channel in range(16):
                i=channel*4;frequency=(int(regs[i])+(int(regs[i+1])<<8))*CLOCK/131072
                position=(phase[channel]+step*frequency/rate)%1
                phase[channel]=(phase[channel]+800*frequency/rate)%1
                control=int(regs[i+2]);amplitude=VOLUME[control&63]*16
                signal=(1-4*np.abs(position-0.5)) if regs[i+3]>>6==2 else rng.uniform(-1,1,800)
                if control&64:block[:,0]+=signal*amplitude
                if control&128:block[:,1]+=signal*amplitude
            wav.writeframes(np.clip(block,-32768,32767).astype('<i2').tobytes())

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',nargs='?',type=Path,default=VERA.parent/'media/music.ogg')
    parser.add_argument('output',nargs='?',type=Path,default=VERA/'generated/music_trial.psg')
    args=parser.parse_args()
    audio=decode(args.input)
    # Preserve the intermediate WAV as an audition/reference artifact.
    subprocess.run(['ffmpeg','-v','error','-y','-i',str(args.input),'-c:a','pcm_s16le',
        str(VERA/'llvm/build/music_original.wav')],check=True)
    notes,amplitudes,drums=analyze(audio)
    stream,registers,counts=encode(notes,amplitudes,drums)
    args.output.write_bytes(stream)
    preview(registers,VERA/'llvm/build/music_psg_preview.wav')
    report={'source':str(args.input),'duration_seconds':len(audio)/16000,
        'frames':len(registers),'psg_bytes':len(stream),
        'writes_per_frame_mean':float(np.mean(counts)),
        'writes_per_frame_max':int(max(counts)),
        'approximate_transcription':True,'integrated_in_game':False,
        'percussion':'Two alternating low taiko strikes with overlapping tails; no woodblock/noise',
        'preview_note':'Approximate PSG render, hardware gain, not AppleWin capture'}
    (VERA/'llvm/build/music_psg_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
