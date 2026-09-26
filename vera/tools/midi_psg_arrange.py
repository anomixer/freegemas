"""Clean offline MIDI -> VERA PSG arrangement (no invented fifths/octaves).

Design references: DreamTracker VERA instruments/envelopes and Furnace VERA
macros. Source MIDI is preserved. Requires NumPy; preview uses the local VERA
register model and is not an AppleWin capture. No external synth dependency.
"""
from pathlib import Path
from collections import Counter, defaultdict
import argparse
import json
import struct
import numpy as np
from wav2psg import VERA, CLOCK, VOLUME, preview

def read_midi(file):
    data=file.read_bytes()
    if data[:4]!=b'MThd':raise ValueError('Missing MIDI header')
    length=int.from_bytes(data[4:8],'big')
    fmt,tracks,division=struct.unpack('>HHH',data[8:14])
    if fmt>1 or division&0x8000:raise ValueError('Requires MIDI type 0/1 and PPQN timing')
    events=[];pos=8+length
    def vlq(buf,at):
        value=0
        while True:
            byte=buf[at];at+=1;value=(value<<7)|(byte&127)
            if not byte&128:return value,at
    for track in range(tracks):
        if data[pos:pos+4]!=b'MTrk':raise ValueError('Missing track')
        size=int.from_bytes(data[pos+4:pos+8],'big');buf=data[pos+8:pos+8+size];pos+=8+size
        at=tick=status=0
        while at<len(buf):
            delta,at=vlq(buf,at);tick+=delta
            if buf[at]&128:
                code=buf[at];at+=1
                if code<240:status=code
            else:code=status
            if code==255:
                kind=buf[at];at+=1;n,at=vlq(buf,at);payload=buf[at:at+n];at+=n
                if kind==81:events.append((tick,track,'tempo',int.from_bytes(payload,'big'),0,0))
                if kind==47:events.append((tick,track,'end',0,0,0))
            elif code in (240,247):
                n,at=vlq(buf,at);at+=n
            else:
                kind=code>>4;channel=code&15;a=buf[at];at+=1
                b=0 if kind in (12,13) else buf[at];at+=kind not in (12,13)
                events.append((tick,track,kind,channel,a,b))
    events.sort(key=lambda e:(e[0],e[1]))
    tempo=500000;last_tick=0;seconds=0;timed=[]
    for tick,track,kind,ch,a,b in events:
        seconds+=(tick-last_tick)*tempo/1e6/division;last_tick=tick
        if kind=='tempo':tempo=ch
        else:timed.append((seconds,kind,ch,a,b))
    return timed,{'format':fmt,'tracks':tracks,'ppqn':division,'midi_duration':seconds}

def remove_transcription_blips(events):
    """Conservative cleanup of weak/brief treble transcription artifacts.
    Pair matching note-offs; keep strong and sustained melody. Never edit the
    source file or hard-code a song timestamp.
    """
    pending=defaultdict(list);pairs=[]
    for index,(time,kind,ch,note,velocity) in enumerate(events):
        if kind==9 and velocity:pending[ch,note].append(index)
        elif kind==8 or (kind==9 and not velocity):
            if pending[ch,note]:
                start=pending[ch,note].pop(0)
                pairs.append((start,index,time-events[start][0]))
    high=[(i,j,d) for i,j,d in pairs if events[i][3]>=84 and events[i][4]<=40 and d<=0.22]
    burst_times=np.array([events[i][0] for i,j,d in high])
    remove=set();report=[]
    for i,j,duration in pairs:
        time,_,ch,note,velocity=events[i]
        high_blip=note>=84 and velocity<=40 and duration<=0.22
        burst_blip=note>=72 and velocity<=50 and duration<=0.075 and np.any(np.abs(burst_times-time)<=0.08)
        if high_blip or burst_blip:
            remove.update((i,j));report.append({'time':round(time,4),'note':note,'velocity':velocity,'duration':round(duration,4)})
    return [e for i,e in enumerate(events) if i not in remove],report

def smooth_register_edges(registers):
    """Soften gate and pitch-change edges within the 60 Hz PSG stream.

    This reduces discontinuities, not sample-level de-clicking: PSG volume
    is still quantized and the player controls oscillator phase.
    """
    result=registers.copy()
    for channel in range(16):
        base=channel*4
        frequency=registers[:,base].astype(int)+(registers[:,base+1].astype(int)<<8)
        active=(registers[:,base+2]&63)>0
        at=0
        while at<len(registers):
            if not active[at]:at+=1;continue
            end=at+1
            while end<len(registers) and active[end] and frequency[end]==frequency[at]:end+=1
            for frame in range(at,end):
                # Three-frame ramps, including brief notes; never boost level.
                fade=min(1.0,(frame-at+1)/4,(end-frame)/4)
                gain=0.5-0.5*np.cos(np.pi*fade)
                ctrl=int(registers[frame,base+2])
                amp=VOLUME[ctrl&63]*gain
                vol=int(np.argmin(np.abs(VOLUME-amp)))
                result[frame,base+2]=(ctrl&192)|vol if vol else 0
            # A reused oscillator must be silent before changing pitch.
            if end<len(registers) and active[end]:result[end-1,base+2]=0
            at=end
    return result

def remove_low_hit_clusters(events):
    """Omit inferred taiko-like bass bursts, not recovered percussion stems.

    The transcribed repeated D2 attacks have strong, brief anchors surrounded
    by short low-pitch fragments. Keep sustained bass; never mute time spans.
    """
    pending=defaultdict(list);pairs=[]
    for index,(time,kind,ch,note,velocity) in enumerate(events):
        if kind==9 and velocity:pending[ch,note].append(index)
        elif kind==8 or (kind==9 and not velocity):
            if pending[ch,note]:
                start=pending[ch,note].pop(0)
                pairs.append((start,index,time-events[start][0]))
    anchors=np.array([events[i][0] for i,j,d in pairs
        if events[i][3]==38 and events[i][4]>=75 and .075<=d<=.15])
    remove=set();report=[]
    for i,j,d in pairs:
        time,_,ch,note,velocity=events[i]
        if note<48 and d<=.18 and np.any((time>=anchors-1.0)&(time<=anchors+.8)):
            remove.update((i,j))
            report.append({'time':round(time,4),'note':note,'velocity':velocity,'duration':round(d,4)})
    return [event for i,event in enumerate(events) if i not in remove],report

def soften_pluck_peak(velocity,role):
    """Soft knee for loud pitched plucks, without boosting quiet notes."""
    if role not in ('guitar','marimba','celesta','drum') or velocity<=0.12:
        return velocity
    return 0.12+0.08*(1-np.exp(-(velocity-0.12)/0.08))

def arrange(events,tail=0.5,style='clean',cleanup=True,overtones=True,smooth=False,soft_percussion=False,no_percussion=False,no_taiko=False,pure=False):
    filtered=[]
    if (style=='ensemble' or pure) and cleanup:events,filtered=remove_transcription_blips(events)
    removed_hits=[]
    if no_taiko:events,removed_hits=remove_low_hit_clusters(events)
    frames=int(np.ceil((events[-1][0]+tail)*60))+1
    registers=np.zeros((frames,64),dtype=np.uint8)
    # One voice per source note. Extras used only for GM taiko/drums if present.
    voices=[None]*16;last_source=[None]*16;program=[0]*16;pedal=[False]*16;volume=[1.0]*16
    bend=[0.0]*16;pan=[192]*16;cursor=0;stolen=0;max_active=0
    counts=Counter();programs=defaultdict(set);held=defaultdict(list);omitted_percussion=0;omitted_bass=0
    def amplitude(v,frame):
        age=(frame-v['start'])/60
        # Natural pluck decay, preserving MIDI note-off instead of seconds of
        # bass tail. A brief attack avoids organ-like constant-volume tones.
        decay={'bass':0.9,'keys':0.65,'guitar':0.32,'marimba':0.18,'celesta':0.42,'drum':0.28}[v['role']]
        env=(0.7 if age<1/60 and not smooth else 1.0)*np.exp(-age/decay)
        if v['off'] is not None:
            env*=np.exp(-(frame-v['off'])/60/0.045)
        return v['velocity']*volume[v['channel']]*env
    for frame in range(frames):
        now=frame/60
        while cursor<len(events) and events[cursor][0]<=now:
            time,kind,ch,a,b=events[cursor];cursor+=1
            if kind==12:program[ch]=a;programs[ch].add(a)
            elif kind==14:bend[ch]=((a+(b<<7))-8192)/8192*2
            elif kind==11:
                if a in (7,11):volume[ch]=b/127
                elif a==10:pan[ch]=64 if b<32 else 128 if b>95 else 192
                elif a==64:
                    pedal[ch]=b>=64
                    if not pedal[ch]:
                        for v in voices:
                            if v and v['channel']==ch and not v['held'] and v['off'] is None:v['off']=frame
            elif kind==8 or (kind==9 and b==0):
                key=(ch,a)
                if held[key]:
                    v=held[key].pop(0);v['held']=False
                    if not pedal[ch]:v['off']=frame
            elif kind==9:
                counts[ch]+=1
                role='bass' if a<48 else 'keys'
                if style=='ensemble' and role=='keys':
                    role='celesta' if a>=72 else 'marimba' if a>=60 else 'guitar'
                if ch==9 or program[ch]==116:role='drum'
                if pure and a<48:
                    omitted_bass+=1
                    continue
                if pure and role=='drum':
                    omitted_percussion+=1
                    continue
                if no_percussion and role in ('marimba','drum'):
                    omitted_percussion+=1
                    continue
                if pure:role='keys'
                v={'channel':ch,'note':a,'start':frame,'off':None,'held':True,
                   'velocity':(b/127)**1.4*(0.64 if role=='bass' else 0.9),
                   'role':role,'wave':128}
                if soft_percussion:v['velocity']=soften_pluck_peak(v['velocity'],role)
                # Preserve all pitches; no automatic +12 semitone bass shift.
                free=next((i for i,x in enumerate(voices) if x is None),None)
                if free is None:
                    # Keep current high melody and low foundation over quiet
                    # inner chord tones, without generating additional pitches.
                    free=min(range(16),key=lambda i:amplitude(voices[i],frame)*
                        (3 if voices[i]['held'] else 1)*
                        (1.5 if voices[i]['note']>=72 or voices[i]['note']<48 else 1))
                    stolen+=1
                voices[free]=v;held[(ch,a)].append(v)
        active=0
        for channel,v in enumerate(voices):
            base=channel*4;registers[frame,base+3]=128
            if v is None:continue
            amp=amplitude(v,frame)
            if amp<0.004:
                voices[channel]=None;continue
            active+=1;hz=440*2**((v['note']+bend[v['channel']]-69)/12)
            if v['role']=='drum':
                age=(frame-v['start'])/60
                hz=80+8*np.exp(-age/0.015);amp=v['velocity']*np.exp(-age/0.075)
                if age>0.3:voices[channel]=None;continue
            frequency=int(np.clip(round(hz*131072/CLOCK),0,65535))
            vol=int(np.argmin(np.abs(VOLUME/np.max(VOLUME)-amp)))
            registers[frame,base:base+4]=[frequency&255,frequency>>8,pan[v['channel']]|vol if vol else 0,128]
            if not smooth and frame%3 and last_source[channel] is v and frame and v['off']!=frame:
                old=registers[frame-1,base+2]
                if old&63 and vol:registers[frame,base+2]=old
            last_source[channel]=v
        # True integer harmonic transient, only using idle voices. Never
        # insert a separate fifth chord or steal a source note for an overtone.
        if style=='ensemble' and overtones and not pure:
            free=[i for i in range(16) if not registers[frame,i*4+2]&63]
            candidates=sorted((v for v in voices if v and v['role'] in ('guitar','marimba','celesta')),
                key=lambda v:amplitude(v,frame),reverse=True)
            for extra,v in zip(free[:2],candidates[:2]):
                age=(frame-v['start'])/60
                partial=2 if v['role']=='celesta' else 3
                amp=amplitude(v,frame)*0.16*np.exp(-age/0.06)
                vol=int(np.argmin(np.abs(VOLUME/np.max(VOLUME)-amp)))
                if not vol:continue
                hz=partial*440*2**((v['note']+bend[v['channel']]-69)/12)
                frequency=int(np.clip(round(hz*131072/CLOCK),0,65535))
                registers[frame,extra*4:extra*4+4]=[frequency&255,frequency>>8,pan[v['channel']]|vol,128]
        max_active=max(max_active,active)
    # One frame of silence before loop restart, including any pedal-held notes.
    registers[-1,2::4]=0
    if smooth:registers=smooth_register_edges(registers)
    stream=bytearray();previous=np.zeros(64,dtype=np.uint8);writes=[]
    for frame,regs in enumerate(registers):
        changed=np.arange(64) if frame==0 else np.flatnonzero(regs!=previous)
        stream.append(len(changed));writes.append(len(changed))
        for reg in changed:stream.extend((int(reg),int(regs[reg])))
        previous=regs
    stream.extend((255,0,0))
    return stream,registers,{'note_counts_by_channel':dict(counts),
        'omitted_percussion_notes':omitted_percussion,
        'omitted_bass_notes':omitted_bass,
        'removed_low_hit_clusters':removed_hits,
        'removed_transcription_blips':filtered,
        'programs_by_channel':{k:sorted(v) for k,v in programs.items()},
        'voice_steals':stolen,'max_active_voices':max_active,
        'mean_writes_per_frame':float(np.mean(writes)), 'max_writes_per_frame':max(writes)}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input',nargs='?',type=Path,default=VERA/'llvm/build/music_original.mid')
    parser.add_argument('--style',choices=('clean','ensemble'),default='clean')
    parser.add_argument('--no-overtones',action='store_true',help='Disable added transient harmonics; keep primary arrangement unchanged')
    parser.add_argument('--smooth',action='store_true',help='60 Hz envelopes and softened gate/pitch-change edges')
    parser.add_argument('--soft-percussion',action='store_true',help='Attenuate loud heuristic pluck peaks; quiet notes and bass unchanged')
    parser.add_argument('--no-percussion',action='store_true',help='Omit heuristic marimba and explicit GM drums/taiko; not source-stem separation')
    parser.add_argument('--no-taiko',action='store_true',help='Omit inferred brief bass bursts around strong D2 attacks; keep marimba')
    parser.add_argument('--pure',action='store_true',help='No notes below MIDI 48 or GM drums; uniform keys triangle, no added harmonics')
    args=parser.parse_args()
    events,report=read_midi(args.input)
    stream,regs,stats=arrange(events,style=args.style,overtones=not args.no_overtones,smooth=args.smooth,soft_percussion=args.soft_percussion,no_percussion=args.no_percussion,no_taiko=args.no_taiko,pure=args.pure)
    report.update(stats);report.update({'frames':len(regs),'bytes':len(stream),
        'source':str(args.input),'automatic_taiko_inference':args.no_taiko,
        'preview':'Hardware-gain PCM, not AppleWin capture; no tanh saturation'})
    name='music_midi_'+args.style
    if args.no_overtones:name+='_no_overtones'
    if args.smooth:name+='_smooth'
    if args.soft_percussion:name+='_soft'
    if args.no_percussion:name+='_no_percussion'
    if args.no_taiko:name+='_no_taiko'
    if args.pure:name='music_midi_pure'+('_smooth' if args.smooth else '')
    report['pure_keys_no_bass']=args.pure
    report['percussion_omitted']=args.no_percussion
    report['softened_pluck_peaks']=args.soft_percussion
    report['smoothed_register_edges']=args.smooth
    report['added_transient_overtones']=args.style=='ensemble' and not args.no_overtones and not args.pure
    report['style']=args.style
    report['instrument_assignment']='Uniform triangle keys, MIDI notes >=48, no GM drums or added harmonics' if args.pure else 'Heuristic pitch-range arrangement, not recovered source stems' if args.style=='ensemble' else 'Source MIDI piano with bass balance'
    (VERA/'generated'/f'{name}.psg').write_bytes(stream)
    preview(regs,VERA/'llvm/build'/f'{name}.wav')
    (VERA/'llvm/build'/f'{name}_report.json').write_text(json.dumps(report,indent=2)+'\n')
    summary = {key: value for key, value in report.items() if key not in ('removed_transcription_blips','removed_low_hit_clusters')}
    summary['removed_transcription_blip_count'] = len(report['removed_transcription_blips'])
    summary['removed_low_hit_count']=len(report['removed_low_hit_clusters'])
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
