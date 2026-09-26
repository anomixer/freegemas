#!/usr/bin/env python3
"""Execute shipped 65C02 images against an instrumented VERA/MLI model.

Requires py65 (pip install py65). This supplements, not replaces, AppleWin.
Uses a private in-memory HDV copy: test scores never alter the user's disk.
"""
from pathlib import Path
import subprocess
import os
from collections import Counter
from py65.devices.mpu65c02 import MPU

LLVM=Path(__file__).resolve().parents[1]
VERA=LLVM.parent
NM=Path('C:/dev/llvm-mos-sdk/install/bin/llvm-nm.exe')

def symbols(file):
    result={}
    for line in subprocess.check_output([str(NM),str(file)],text=True).splitlines():
        fields=line.split()
        if len(fields)==3: result[fields[2]]=int(fields[0],16)
    return result

def entry(disk,name):
    block=2
    while block:
        page=disk[block*512:(block+1)*512]
        for i in range(1 if block==2 else 0,13):
            e=page[4+i*39:4+(i+1)*39]
            if e[0] and bytes(e[1:1+(e[0]&15)]).decode('ascii')==name:
                return e[0]>>4,e[17]|e[18]<<8,int.from_bytes(e[21:24],'little')
        block=page[2]|page[3]<<8
    raise AssertionError(f'Missing {name}')

def scene_pixels(file):
    data=file.read_bytes()
    if data[:2]==bytes(2): pixels=data[2:]
    else:
        pixels=bytearray()
        for i in range(0,len(data),2):pixels.extend(bytes([data[i+1]])*data[i])
    assert len(pixels)==76800
    return pixels

class Memory:
    def __init__(self,slot):
        self.ram=bytearray(65536);self.vram=bytearray(131072)
        self.aux=bytearray(65536);self.aux_read=False;self.aux_write=False;self.aux_present=True
        self.base=0xC000+slot*256;self.addr=[0,0];self.inc=[0,0];self.ctrl=0
        self.reg=bytearray(32);self.writes=Counter();self.keys_cleared=0;self.frames=0
        self.psg_writes=[]
        self.pcm_fifo=bytearray();self.pcm_writes=[];self.pcm_resets=0
        self.pcm_clocked=False
    def __getitem__(self,a):
        if isinstance(a,slice): return self.ram[a]
        if self.base<=a<self.base+32:
            r=a-self.base;port=self.ctrl&1
            if r<3:
                return (self.addr[port]>>(r*8))&255 if r<2 else ((self.addr[port]>>16)|([0,1,2,4,8,16,32,64,128,256,512,40,80,160,320,640].index(self.inc[port])<<4))
            if r in (3,4):
                port=r-3;v=self.vram[self.addr[port]&0x1FFFF];self.addr[port]=(self.addr[port]+self.inc[port])&0x1FFFF;return v
            if r==5:return self.ctrl
            if r==7:return 1 # deterministic VSYNC pulse per wait, not wall-clock
            if r==27:return (self.reg[r]&63)|(128 if len(self.pcm_fifo)>=4095 else 0)|(64 if not self.pcm_fifo else 0)
            return self.reg[r]
        if a==0xC010:self.ram[0xC000]&=127;self.keys_cleared+=1
        if 0xC200<=a<0xC220 or 0xC400<=a<0xC420:return 0 # empty other slot
        if 0x0200<=a<0xC000 and self.aux_read:return self.aux[a]
        return self.ram[a]
    def __setitem__(self,a,v):
        if isinstance(a,slice):self.ram[a]=v;return
        v&=255
        if self.base<=a<self.base+32:
            r=a-self.base;p=self.ctrl&1
            if r<3:
                shift=r*8;mask=255 if r<2 else 1
                self.addr[p]=(self.addr[p]&~(mask<<shift))|((v&mask)<<shift)
                if r==2:self.inc[p]=[0,1,2,4,8,16,32,64,128,256,512,40,80,160,320,640][v>>4]
            elif r in (3,4):
                p=r-3;address=self.addr[p]&0x1FFFF;self.vram[address]=v;self.writes[address]+=1
                if 0x1F9C0<=address<0x1FA00:self.psg_writes.append((self.frames,address,v))
                self.addr[p]=(address+self.inc[p])&0x1FFFF
            elif r==5:self.ctrl=v
            else:
                if r==27 and v&128:self.pcm_fifo.clear();self.pcm_resets+=1
                if r==29:
                    assert len(self.pcm_fifo)<4095,'PCM FIFO overflow'
                    self.pcm_fifo.append(v);self.pcm_writes.append(v)
                self.reg[r]=v
                if r==7:
                    self.frames+=1
                    if self.reg[28] and not self.pcm_clocked:
                        samples=round(self.reg[28]*48828.125/128/60)
                        stride=(1,2,2,4)[(self.reg[27]>>4)&3]
                        del self.pcm_fifo[:samples*stride]
            return
        if a==0xC010:self.ram[0xC000]&=127;self.keys_cleared+=1
        elif a==0xC002:self.aux_read=False
        elif a==0xC003:self.aux_read=self.aux_present
        elif a==0xC004:self.aux_write=False
        elif a==0xC005:self.aux_write=self.aux_present
        elif a==0xC000:pass # 80STORE off, not keyboard input
        elif 0xC200<=a<0xC220 or 0xC400<=a<0xC420:return
        elif 0x0200<=a<0xC000 and self.aux_write:self.aux[a]=v
        else:self.ram[a]=v

class Machine:
    def __init__(self,slot=2,disk=None):
        self.mem=Memory(slot);self.cpu=MPU(memory=self.mem,pc=0x2000)
        self.disk=bytearray(disk or Path(os.environ.get('FREEGEMAS_TEST_DISK',str(VERA/'freegemas.hdv'))).read_bytes())
        system=(LLVM/'build/freegemas.sys').read_bytes()
        if int.from_bytes(system[:2],'little')==0x2000:system=system[4:]
        self.mem.ram[0x2000:0x2000+len(system)]=system
        self.mem.ram[0xBF30]=0x70;self.write_calls=0;self.read_calls=0;self.fail_write=False
        # Fixed seed only in the test fixture, for repeatable cascade coverage.
        self.mem.ram[0x3EA:0x3EC]=(0xBEEF).to_bytes(2,'little')
        self.sym=symbols(LLVM/f'build/freegemas{4 if slot==4 else ""}.bin.elf')
        self.endings=[]
        self.wait_cycles=[];self.last_wait=0
    def step(self):
        if self.cpu.pc==0xBF00:
            # Real JSR return address precedes inline MLI command + parameter ptr.
            low=self.cpu.stPop();high=self.cpu.stPop();ret=low|high<<8
            cmd=self.mem.ram[ret+1];p=int.from_bytes(self.mem.ram[ret+2:ret+4],'little')
            params=self.mem.ram[p:p+6];dest=int.from_bytes(params[2:4],'little');block=int.from_bytes(params[4:6],'little')
            assert cmd in (0x80,0x81),(hex(cmd),hex(ret))
            status=0
            if cmd==0x80:
                self.read_calls+=1
                self.mem.ram[dest:dest+512]=self.disk[block*512:(block+1)*512]
            else:
                self.write_calls+=1
                if self.fail_write:status=0x27
                else:self.disk[block*512:(block+1)*512]=self.mem.ram[dest:dest+512]
            # Deliberately clobber ALL compiler ZP state and X/Y like a system call.
            self.mem.ram[:192]=bytes([0xDA])*192
            self.cpu.x=0xAA;self.cpu.y=0xBB;self.cpu.a=status
            self.cpu.p=(self.cpu.p&~1)|(1 if status else 0);self.cpu.pc=(ret+4)&65535
        else:
            if self.cpu.pc==self.sym.get('waitvsync'):
                if self.last_wait and self.value('resolving'):self.wait_cycles.append(self.cpu.processorCycles-self.last_wait)
                self.last_wait=self.cpu.processorCycles
            if self.cpu.pc==self.sym.get('show_game_over'):
                self.endings.append((self.value('score',4),self.mem.ram[self.sym['resolving']],has_match(self.board())))
            self.cpu.step()
    def until(self,predicate,limit=12_000_000):
        for n in range(limit):
            if predicate():return n
            self.step()
        raise AssertionError(f'timeout PC=${self.cpu.pc:04X}, frames={self.mem.frames}')
    def boot_game(self,mode=0):
        self.mem.ram[0x3F0]=0xA5;self.mem.ram[0x3F1]=mode
        self.until(lambda:self.cpu.pc==self.sym['waitvsync'] and self.mem.reg[9]==0x71)
        self.idle_sp=self.cpu.sp
        expected=scene_pixels(VERA/('generated/game_endless.rle' if mode else 'generated/game_scene.rle'))
        for y in range(240):
            for x in range(320):
                if (7<=x<84 and 50<=y<67) or (31<=x<79 and 98<=y<113):continue
                assert self.mem.vram[y*320+x]==expected[y*320+x],('game background load mismatch',x,y)
        assert all(1<=gem<=7 for gem in self.board())
        assert self.mem.vram[0x12C00:0x14800]==(VERA/'generated/game_gems_32.idx').read_bytes()
        assert self.mem.vram[0x1FA18:0x1FA1A]==bytes(2),'popup outline ink must be reserved black'
        assert not any(self.mem.vram[0x1B800:0x1B840]),'mask tile zero must be transparent'
        assert not any(self.mem.vram[0x1A900:0x1B800]),'mask must not cover the playing board'
        for y in range(2):
            for x in range(40):
                tile=0x1B800+(1+y*40+x)*64
                for row in range(8):
                    source=(y*8+row)*320+x*8
                    assert self.mem.vram[tile+row*8:tile+row*8+8]==self.mem.vram[source:source+8]
    def key(self,key):
        clears=self.mem.keys_cleared;self.mem.ram[0xC000]=key|128
        self.until(lambda:self.mem.keys_cleared>clears and self.cpu.pc==self.sym['waitvsync'] and self.cpu.sp==self.idle_sp and not self.value('resolving'))
    def value(self,name,length=1):
        a=self.sym[name];return int.from_bytes(self.mem.ram[a:a+length],'little')
    def put(self,name,value,length=1):
        a=self.sym[name];self.mem.ram[a:a+length]=value.to_bytes(length,'little')
    def board(self):return self.mem.ram[self.sym['board']:self.sym['board']+64]
    def return_loader(self):
        self.cpu.pc=0x2000;self.mem.ram[0x3F0]=0
        self.until(lambda:self.cpu.pc==0x3000)
        assert self.cpu.sp==255,'segment transfer must reset hardware stack'
        assert self.mem.vram[:76800]==scene_pixels(VERA/'generated/title_scene.rle'),'raw/RLE scene upload differs from generated pixels'
    def disk_scores(self):
        storage,key,size=entry(self.disk,'HISCORE.DAT');assert storage==1 and size==12
        data=self.disk[key*512:key*512+12];assert data[:4]==b'FGH\x01'
        return [int.from_bytes(data[i:i+4],'little') for i in (4,8)]

def has_match(b):
    return any(b[y*8+x] and b[y*8+x]==b[y*8+x+1]==b[y*8+x+2] for y in range(8) for x in range(6)) or any(b[y*8+x] and b[y*8+x]==b[(y+1)*8+x]==b[(y+2)*8+x] for y in range(6) for x in range(8))
def solution(b):
    for y in range(8):
        for x in range(8):
            for dx,dy in ((1,0),(0,1)):
                if x+dx>=8 or y+dy>=8:continue
                test=bytearray(b);a=y*8+x;c=(y+dy)*8+x+dx;test[a],test[c]=test[c],test[a]
                if has_match(test):return x,y,x+dx,y+dy
    raise AssertionError('no solution')
def move(m,x,y):
    for name,target,left,right in (('cursor_x',x,8,21),('cursor_y',y,11,10)):
        while m.value(name)!=target:m.key(left if m.value(name)>target else right)
def swap(m,last_second=False):
    ax,ay,bx,by=solution(m.board());move(m,ax,ay);m.key(32);move(m,bx,by)
    if last_second:m.put('time_left',1);m.put('time_frames',58)
    before=bytes(m.board());frame=m.mem.frames;m.key(32)
    assert bytes(m.board())!=before and not has_match(m.board())
    return m.mem.frames-frame

def aligned(m):
    for i,gem in enumerate(m.board()):
        a=m.mem.vram[0x1FC00+i*8:0x1FC08+i*8]
        pattern=(a[0]<<5)|((a[1]&15)<<13)
        assert pattern==0x12C00+(gem-1)*1024,(i,gem,hex(pattern))
        assert a[6]==8 and (a[2]|a[3]<<8)==93+(i%8)*26 and (a[4]|a[5]<<8)==13+(i//8)*26

def test(slot):
    m=Machine(slot);m.boot_game()
    board_bitmap=bytes(m.mem.vram[:76800]);attrs=bytes(m.mem.vram[0x1FC00:0x1FE00])
    m.mem.writes.clear();m.key(21)
    assert bytes(m.mem.vram[:76800])==board_bitmap,'cursor touched bitmap'
    assert bytes(m.mem.vram[0x1FC00:0x1FE00])==attrs,'cursor rewrote gems'
    graphics_writes=sum(n for a,n in m.mem.writes.items() if not 0x1F9C0<=a<0x1FA00)
    assert graphics_writes<=24,'cursor update excessive'
    print(f'PASS slot {slot}: cursor only ({graphics_writes} graphics VRAM bytes, PSG excluded)')
    m.mem.writes.clear();before=bytes(m.board());m.key(32);m.key(32)
    assert bytes(m.board())==before and not any(a<76800 for a in m.mem.writes)
    print(f'PASS slot {slot}: invalid/same-cell swap leaves board and bitmap unchanged')
    m.mem.writes.clear();swap(m)
    assert m.value('score',4)>0
    # HUD writes permitted, no board bitmap writes, and gems stay enabled/aligned.
    board_writes=sum(n for address,n in m.mem.writes.items() if address<76800 and address%320>=96)
    assert not board_writes,f'{board_writes} board bitmap writes during cascade'
    aligned(m)
    bitmap_after=bytes(m.mem.vram[:76800]);frame=m.mem.frames
    m.until(lambda:m.mem.frames>=frame+55)
    assert all(m.mem.vram[0x1FC06+i*8]==0 for i in range(68,120)),'effects did not expire'
    assert all(m.mem.vram[y*320+96:(y+1)*320]==bitmap_after[y*320+96:(y+1)*320] for y in range(240))
    print(f'PASS slot {slot}: swap/cascade score={m.value("score",4)}, zero board redraw, effects expire')
    print(f'  Animation CPU cycles between waits: average={sum(m.wait_cycles)//len(m.wait_cycles)}, maximum={max(m.wait_cycles)} (1MHz frame budget ~17000)')
    cascades=0
    for turn in range(12):
        try:solution(m.board())
        except AssertionError:m.key(ord('R'))
        m.mem.writes.clear();duration=swap(m);aligned(m)
        cascades+=duration>31
        assert not any(a<76800 and a%320>=96 for a in m.mem.writes)
    assert cascades,'stress fixture must exercise multi-cascade moves'
    print(f'PASS slot {slot}: 12 more swaps, {cascades} multi-cascade moves, artwork/position agree with logical board')
    trial=int.from_bytes(m.mem.ram[0x3E0:0x3E4],'little');m.return_loader();assert m.disk_scores()[0]==trial
    restart=Machine(slot,m.disk);restart.boot_game(1)
    assert int.from_bytes(restart.mem.ram[0x3E0:0x3E4],'little')==trial
    swap(restart);endless=restart.value('score',4);restart.return_loader()
    assert restart.disk_scores()==[trial,endless]
    cold=Machine(slot,restart.disk);cold.boot_game();assert list(int.from_bytes(cold.mem.ram[i:i+4],'little') for i in (0x3E0,0x3E4))==[trial,endless]
    cold.mem.ram[0x3E8]=1;cold.fail_write=True;cold.return_loader();assert cold.mem.ram[0x3E8]==1
    cold.fail_write=False;cold.return_loader();assert cold.mem.ram[0x3E8]==0
    print(f'PASS slot {slot}: separate records, cold reload, failed-write retry; MLI clobbered ZP throughout')
    end=Machine(slot);end.boot_game();swap(end,last_second=True)
    assert end.value('game_over') and end.endings and all(score>0 and not resolving and not match for score,resolving,match in end.endings)
    assert all(end.mem.vram[0x1FC06+i*8]==0 for i in range(64))
    end.key(ord('R'));assert not end.value('game_over') and end.value('score',4)==0
    assert all(end.mem.vram[0x1FC06+i*8]==8 for i in range(64))
    print(f'PASS slot {slot}: last-second move finishes before Game Over, R restores game')
    hint=Machine(slot);hint.boot_game()
    hx,hy,_,_=solution(hint.board())
    move(hint, hx+1 if hx<7 else hx-1, hy);hint.key(32)
    def cursor_attrs():
        return bytes(hint.mem.vram[0x1FC00+66*8:0x1FC00+68*8])
    cursor=cursor_attrs()
    state=[hint.value(n) for n in ('cursor_x','cursor_y','selected','select_x','select_y')]
    hx,hy,_,_=solution(hint.board())
    hint.mem.writes.clear();hint.key(ord('H'))
    assert cursor==cursor_attrs()
    assert state==[hint.value(n) for n in ('cursor_x','cursor_y','selected','select_x','select_y')]
    assert not any(a<76800 for a in hint.mem.writes),'hint must not redraw bitmap'
    attrs=hint.mem.vram[0x1FC00+65*8:0x1FC00+66*8]
    assert attrs[6]==12 and int.from_bytes(attrs[2:4],'little')==93+hx*26
    assert int.from_bytes(attrs[4:6],'little')==13+hy*26
    def complete_hint(stage):
        attr=hint.mem.vram[0x1FC00+65*8:0x1FC00+66*8]
        pattern=(attr[0]<<5)|((attr[1]&15)<<13)
        assert pattern==0x1CC40+stage*1024
        edge=2-stage
        for row in range(32):
            # AppleWin VERA: one lookup clock/slot, one clock/pixel plus
            # one fetch clock/4 pixels in 8bpp. Check actual active sprites
            # ahead of the hint, including overlapping 32px gem rows.
            cost=66+40
            for gemslot in range(64):
                a=hint.mem.vram[0x1FC00+gemslot*8:0x1FC08+gemslot*8]
                sy=int.from_bytes(a[4:6],'little')
                width=8<<((a[7]>>4)&3);height=8<<((a[7]>>6)&3)
                if a[6]&12 and sy<=13+hy*26+row<sy+height:
                    cost+=width+(width+3)//4
            assert cost<801, ('hint scanline truncated',row,cost)
            for col in range(32):
                border=(edge<=row<=31-edge and edge<=col<=31-edge
                        and (row in (edge,31-edge) or col in (edge,31-edge)))
                assert bool(hint.mem.vram[pattern+row*32+col])==border
    complete_hint(0)
    for stage in (1,2):
        expected=((0x1CC40+stage*1024)>>5)&255
        hint.until(lambda:hint.mem.vram[0x1FC00+65*8]==expected)
        complete_hint(stage)
    frames=hint.mem.frames
    hint.until(lambda:hint.mem.frames>=frames+41)
    assert hint.mem.vram[0x1FC06+65*8]==0
    assert cursor==cursor_attrs()
    hint.key(32);swap(hint)
    assert hint.value('score',4)==0
    print(f'PASS slot {slot}: all hint borders/stages fit scanline budget, preserve cursor/selection, expire, suppress initial points')

if __name__=='__main__':
    import sys
    for slot in (list(map(int,sys.argv[1:])) or (2,4)):test(slot)
    import build_hdv
    data=bytearray((VERA/'freegemas.hdv').read_bytes());_,key,_=entry(data,'HISCORE.DAT')
    expected=b'FGH\x01'+(12345).to_bytes(4,'little')+(67890).to_bytes(4,'little')
    data[key*512:key*512+12]=expected
    assert build_hdv.saved_scores(data)==expected
    print('PASS HDV rebuild preserves records across directory blocks')
