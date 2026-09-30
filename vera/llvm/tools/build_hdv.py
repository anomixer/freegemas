#!/usr/bin/env python3
"""Create a bootable 800 KB ProDOS HDV for the segmented Freegemas port."""
from pathlib import Path

BLOCK = 512
RESERVE = 100                 # ProDOS/CLOCK.SYSTEM from the known-good base HDV
KEEP = {"PRODOS", "CLOCK.SYSTEM"}

def saved_scores(disk):
    """Keep user records across rebuilds even when their data block moves."""
    block=2
    visited=set()
    while block and block not in visited and block*BLOCK+BLOCK <= len(disk):
        visited.add(block)
        page=disk[block*BLOCK:(block+1)*BLOCK]
        for i in range(1 if block==2 else 0,13):
            e=page[4+i*39:4+(i+1)*39]
            if e[0]>>4 != 1 or bytes(e[1:1+(e[0]&15)]) != b'HISCORE.DAT': continue
            key=e[0x11]|e[0x12]<<8
            data=bytes(disk[key*BLOCK:key*BLOCK+12])
            if len(data)==12 and data[:4]==b'FGH\x01': return data
        block=page[2]|page[3]<<8
    return b'FGH\x01'+bytes(8)

class Alloc:
    def __init__(self): self.used=set(range(RESERVE)); self.new=[]; self.next=RESERVE
    def one(self):
        while self.next in self.used: self.next += 1
        result=self.next; self.used.add(result); self.new.append(result); self.next += 1
        return result

def raw_bin(path, expected=0x3000):
    data=path.read_bytes()
    if len(data)<4 or data[0] | data[1]<<8 != expected: raise RuntimeError(f"bad BIN header: {path}")
    return data[4:], data[0] | data[1]<<8

def put(disk, alloc, name, typ, aux, data):
    n=(len(data)+511)//512
    if not 1<=n<=256: raise ValueError(f'{name}: exceeds seedling/sapling capacity')
    if n == 1:
        key=alloc.one(); disk[key*BLOCK:key*BLOCK+len(data)]=data; storage=1; total=1
    else:
        key=alloc.one(); index=bytearray(BLOCK)
        for i in range(n):
            b=alloc.one(); index[i]=b&255; index[256+i]=b>>8
            chunk=data[i*BLOCK:(i+1)*BLOCK]; disk[b*BLOCK:b*BLOCK+len(chunk)]=chunk
        disk[key*BLOCK:(key+1)*BLOCK]=index; storage=2; total=n+1
    return dict(name=name, storage=storage, typ=typ, key=key, total=total, eof=len(data), aux=aux)

def entry(vol, offset, f):
    vol[offset]=(f['storage']<<4)|len(f['name'])
    vol[offset+1:offset+1+len(f['name'])]=f['name'].encode('ascii')
    vol[offset+0x10]=f['typ']; vol[offset+0x11]=f['key']&255; vol[offset+0x12]=f['key']>>8
    vol[offset+0x13]=f['total']&255; vol[offset+0x14]=f['total']>>8
    vol[offset+0x15]=f['eof']&255; vol[offset+0x16]=(f['eof']>>8)&255; vol[offset+0x17]=(f['eof']>>16)&255
    vol[offset+0x1e]=0xc3; vol[offset+0x1f]=f['aux']&255; vol[offset+0x20]=f['aux']>>8; vol[offset+0x25]=2

def main(output=None):
    here=Path(__file__).resolve().parent; llvm=here.parent; vera=llvm.parent; root=vera.parent
    base=vera/'assets'/'800kb.hdv'
    out=Path(output).resolve() if output else vera/'freegemas.hdv'
    score_source=out if out.exists() else vera/'freegemas.hdv'
    scores=saved_scores(score_source.read_bytes()) if score_source.exists() else b'FGH\x01'+bytes(8)
    disk=bytearray(base.read_bytes())
    alloc=Alloc()
    system=(llvm/'build'/'freegemas.sys').read_bytes()
    if len(system)>=4 and (system[0]|system[1]<<8)==0x2000: system=system[4:]
    if len(system)>0x1000: raise ValueError('Resident loader overlaps $3000 images')
    # ProDOS names are limited to 15 characters; the prior 16-character
    # spelling silently produced a malformed directory entry.
    files=[put(disk,alloc,'FREEGEM.SYSTEM',0xff,0x2000,system)]
    for name, file in [('TITLE.BIN','title.bin'),('TITLE4.BIN','title4.bin'),('GAME.BIN','freegemas.bin'),('GAME4.BIN','freegemas4.bin')]:
        data,address=raw_bin(llvm/'build'/file); files.append(put(disk,alloc,name,0x06,address,data))
    for name,file in [('HOWTO.BIN','howto.bin'),('HOWTO4.BIN','howto4.bin'),('OPTION.BIN','option.bin'),('OPTION4.BIN','option4.bin'),('INTRO.BIN','intro.bin'),('INTRO4.BIN','intro4.bin')]:
        data,address=raw_bin(llvm/'build'/file); files.append(put(disk,alloc,name,0x06,address,data))
    files.append(put(disk,alloc,'TITLE.RLE',0x06,0x0000,(vera/'generated'/'title_scene.rle').read_bytes()))
    files.append(put(disk,alloc,'GAME.RLE',0x06,0x0000,(vera/'generated'/'game_scene.rle').read_bytes()))
    files.append(put(disk,alloc,'ENDLESS.RLE',0x06,0x0000,(vera/'generated'/'game_endless.rle').read_bytes()))
    files.append(put(disk,alloc,'HOWTO.RLE',0x06,0x0000,(vera/'generated'/'howto_scene.rle').read_bytes()))
    files.append(put(disk,alloc,'OPTION.RLE',0x06,0x0000,(vera/'generated'/'options_scene.rle').read_bytes()))
    files.append(put(disk,alloc,'HISCORE.DAT',0x06,0,scores))
    for name in ('select','fall','match1','match2','match3'):
        files.append(put(disk,alloc,name.upper()+'.PCM',0x06,0,(vera/'generated'/(name+'.pcm')).read_bytes()))
    files.append(put(disk,alloc,'MUSIC.PSG',0x06,0,(vera/'generated/music_pure_gained.psg').read_bytes()))
    files.append(put(disk,alloc,'GEM.PAT',0x06,0,(vera/'generated/game_gems_32.idx').read_bytes()))

    vol=memoryview(disk)[2*BLOCK:3*BLOCK]; retained=[]
    for i in range(1,13):
        off=4+i*39
        if not vol[off]: continue
        n=vol[off]&15; name=bytes(vol[off+1:off+1+n]).decode('ascii','replace')
        if name in KEEP: retained.append(bytes(vol[off:off+39]))
    for i in range(1,13): vol[4+i*39:4+(i+1)*39]=b'\0'*39
    for i, old in enumerate(retained,1): vol[4+i*39:4+i*39+39]=old
    all_entries=retained+[None]*len(files)
    for i,f in enumerate(files): all_entries[len(retained)+i]=f
    for i,item in enumerate(all_entries[:12],1):
        if isinstance(item,bytes): vol[4+i*39:4+(i+1)*39]=item
        else: entry(vol,4+i*39,item)
    previous=2
    for start in range(12,len(all_entries),13):
        db=alloc.one()
        disk[previous*BLOCK+2:previous*BLOCK+4]=db.to_bytes(2,'little')
        disk[db*BLOCK:db*BLOCK+BLOCK]=b'\0'*BLOCK
        disk[db*BLOCK:db*BLOCK+2]=previous.to_bytes(2,'little')
        page=memoryview(disk)[db*BLOCK:(db+1)*BLOCK]
        for i,item in enumerate(all_entries[start:start+13]):
            if isinstance(item,bytes):page[4+i*39:4+(i+1)*39]=item
            else:entry(page,4+i*39,item)
        previous=db
    vol[0x25]=len(retained)+len(files); vol[0x26]=0
    for b in alloc.new: disk[6*BLOCK+b//8] &= ~(1 << (7-b%8)) & 255
    if max(alloc.used)>=len(disk)//BLOCK: raise ValueError('HDV capacity exceeded')
    out.write_bytes(disk)
    print(f"Built {out} ({len(disk)//1024} KB): " + ', '.join(f['name'] for f in files))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,help='Alternate image path, e.g. while the normal HDV is mounted')
    main(parser.parse_args().output)
