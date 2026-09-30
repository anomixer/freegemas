"""Losslessly factor approved PSG into timed notes and shared volume curves.

FGM2 header: magic, frames(u16), size(u16), note count(u16), curve size(u16).
Records: frame2, channel1, frequency index1, curve offset2, duration1.
Curve symbols: amount to subtract (0..63), or 64 + absolute6. Static Huffman.
Main-RAM curves and aux-RAM events free enough aux for raw, unmodified PCM.
"""
from pathlib import Path
import argparse
from collections import Counter
import heapq
import numpy as np
from wav2psg import VOLUME,VERA
MUSIC_GAIN=3.394112549695428  # +20% gain (approx +10.6dB)

def build(source):
    pos=0;shadow=np.zeros(64,dtype=np.uint8);frames=[];lut=VOLUME*4
    while pos<len(source) and source[pos]!=255:
        count=source[pos];pos+=1
        if count>64:raise ValueError('Invalid frame')
        for _ in range(count):
            reg,value=source[pos:pos+2];pos+=2
            if reg>=64:raise ValueError('Invalid register')
            if reg%4==3 and value!=128:raise ValueError('Requires pure triangle')
            if reg%4==2:
                if value&192 not in (0,192):raise ValueError('Requires centered music')
                value=int(np.argmin(np.abs(lut-min(511,lut[value&63]*MUSIC_GAIN))))
            shadow[reg]=value
        frames.append(shadow.copy())
    if source[pos:]!=bytes((255,0,0)):raise ValueError('Requires complete loop-zero stream')
    registers=np.array(frames);notes=[];curves=bytearray();dictionary={};frequencies=[]
    for channel in range(16):
        frequency=registers[:,channel*4].astype(int)+(registers[:,channel*4+1].astype(int)<<8)
        volume=registers[:,channel*4+2];start=0
        while start<len(frames):
            if not frequency[start]:
                if volume[start]:raise ValueError('Audible zero-frequency channel')
                start+=1;continue
            end=start+1
            while end<len(frames) and frequency[end]==frequency[start]:end+=1
            sequence=bytes(volume[start:end])
            if len(sequence)>255:raise ValueError('Curve duration exceeds u8')
            dictionary.setdefault(sequence,0)
            freq=int(frequency[start])
            if freq not in frequencies:frequencies.append(freq)
            notes.append((start,channel,frequencies.index(freq),sequence))
            start=end
    counts=Counter()
    for sequence in dictionary:
        previous=0
        for value in sequence:counts[previous-value if value<=previous else 64]+=1;previous=value
    heap=[(count,i,symbol) for i,(symbol,count) in enumerate(sorted(counts.items()))];heapq.heapify(heap);serial=len(heap)
    while len(heap)>1:
        a=heapq.heappop(heap);b=heapq.heappop(heap)
        heapq.heappush(heap,(a[0]+b[0],serial,(a[2],b[2])));serial+=1
    tree=[];codes={}
    def flatten(node,path=()):
        if isinstance(node,int):codes[node]=path;return 128+node
        index=len(tree)//2;tree.extend((0,0))
        tree[index*2]=flatten(node[0],path+(0,));tree[index*2+1]=flatten(node[1],path+(1,));return index
    flatten(heap[0][2])
    for sequence in dictionary:
        dictionary[sequence]=len(curves);bits=[];previous=0
        for value in sequence:
            symbol=previous-value if value<=previous else 64;bits.extend(codes[symbol])
            if symbol==64:bits.extend((value>>i)&1 for i in range(5,-1,-1))
            previous=value
        encoded=bytearray((len(bits)+7)//8)
        for i,bit in enumerate(bits):encoded[i//8]|=bit<<(7-i%8)
        curves.extend(encoded)
    notes.sort();payload=bytearray()
    for start,channel,freq,sequence in notes:
        payload.extend(start.to_bytes(2,'little'));payload.extend((channel,freq))
        payload.extend(dictionary[sequence].to_bytes(2,'little'));payload.append(len(sequence))
    size=12+len(payload)
    if size>9216:raise ValueError('Music events leave insufficient aux RAM for raw SFX')
    if len(curves)>11500:raise ValueError(f'Curves exceed main RAM budget: {len(curves)} bytes')
    header=b'FGM2'+len(frames).to_bytes(2,'little')+size.to_bytes(2,'little')
    header+=len(notes).to_bytes(2,'little')+len(curves).to_bytes(2,'little')
    return header+payload,curves,frequencies,tree

def pack(source):return build(source)[0]

def gain_psg(source):
    pos=0;out=bytearray();lut=VOLUME*4
    while pos<len(source) and source[pos]!=255:
        count=source[pos];pos+=1;out.append(count)
        for _ in range(count):
            reg,value=source[pos:pos+2];pos+=2
            if reg%4==2 and value:
                v=int(np.argmin(np.abs(lut-min(511,lut[value&63]*MUSIC_GAIN))))
                value=(value&192)|v if v else 0
            out.extend((reg,value))
    out.extend(source[pos:])
    return bytes(out)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--header',type=Path,default=VERA/'llvm/build/music_data.h')
    args=parser.parse_args()
    raw=(VERA/'generated/music_midi_pure_smooth.psg').read_bytes()
    data,curves,frequencies,tree=build(raw)
    gained=gain_psg(raw)
    (VERA/'generated/music.fgm').write_bytes(data)
    (VERA/'generated/music_curves.bin').write_bytes(curves)
    (VERA/'generated/music_pure_gained.psg').write_bytes(gained)
    header=f'#define MUSIC_CURVE_SIZE {len(curves)}u\n#define MUSIC_CURVE_TAIL_SIZE {max(1,len(curves)-5632)}u\n'
    header+=f'#define MUSIC_FREQUENCIES {len(frequencies)}u\nstatic const uint16_t music_frequencies[]={{'+','.join(map(str,frequencies))+'};\n'
    header+='static const uint8_t music_curve_tree[]={'+','.join(map(str,tree))+'};\n'
    args.header.parent.mkdir(parents=True,exist_ok=True)
    if not args.header.exists() or args.header.read_text()!=header:args.header.write_text(header)
    print(f'Music: {len(gained)} raw PSG bytes ({len(data)} event bytes, {len(curves)} curve bytes); {len(frequencies)} frequencies, native gain +9dB')
