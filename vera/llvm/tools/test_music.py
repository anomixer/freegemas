"""Execute both real 65C02 players: full approved pure stream and aux banks.

Instrumented model only, not a listening test or real hardware timing.
"""
import sys
from pathlib import Path
import numpy as np
from test_mos import Machine,VERA
sys.path.insert(0,str(VERA/'tools'))
from build_music import pack,MUSIC_GAIN
from wav2psg import VOLUME

def call(m,name,arg=0):
    pc,sp=m.cpu.pc,m.cpu.sp
    m.cpu.a=arg;m.cpu.stPushWord(0x02FE);m.cpu.pc=m.sym[name]
    m.until(lambda:m.cpu.pc==0x02FF)
    assert m.cpu.sp==sp and not m.mem.aux_read and not m.mem.aux_write
    m.cpu.pc=pc

source=(VERA/'generated/music_midi_pure_smooth.psg').read_bytes()
packed=(VERA/'generated/music.fgm').read_bytes()
assert pack(source)==packed
expected=[];shadow=bytearray(64);shadow[3::4]=bytes([128])*16;pos=0
lut=VOLUME*4
while source[pos]!=255:
    count=source[pos];pos+=1
    for _ in range(count):
        reg,value=source[pos:pos+2];pos+=2
        if reg%4==2:
            value=int(np.argmin(np.abs(lut-min(511,lut[value&63]*MUSIC_GAIN))))
            if value:value|=192
        shadow[reg]=value
    expected.append(bytes(shadow))

for slot in (2,4):
    disabled=Machine(slot);disabled.mem.ram[0x3F4]=0xA5;disabled.mem.ram[0x3F2]=0
    disabled.boot_game(1);call(disabled,'music_tick')
    assert not disabled.value('music_on') and not any(disabled.mem.vram[0x1F9C2:0x1FA00:4])
    limited=Machine(slot);limited.mem.aux_present=False;limited.mem.ram[0x800]=0xA5
    limited.boot_game(1)
    assert not limited.value('music_ready') and limited.mem.ram[0x800]==0xA5,'no aux must safely disable music'
    m=Machine(slot);m.boot_game(1)
    assert m.value('music_ready')==1
    assert m.mem.aux[0x800:0x800+len(packed)]==packed
    assert m.mem.ram[0x300:0x312]==m.mem.aux[0x300:0x312]
    m.mem.ram[0x3F2]=1
    m.mem.addr[:]=[0x12345,0x18010];m.mem.inc[:]=[320,40];m.mem.ctrl=3
    saved=(m.mem.addr[:],m.mem.inc[:],m.mem.ctrl)
    reads=m.read_calls;cycles=[];m.mem.writes.clear()
    for frame,registers in enumerate(expected):
        before=m.cpu.processorCycles;call(m,'music_tick');cycles.append(m.cpu.processorCycles-before)
        assert m.mem.vram[0x1F9C0:0x1FA00]==registers,(slot,frame)
        assert (m.mem.addr,m.mem.inc,m.mem.ctrl)==saved,(slot,frame,'graphics port')
        assert m.read_calls==reads,'music must not read disk while playing'
    assert not any(m.mem.vram[0x1F9C2:0x1FA00:4]),'final frame must be silent'
    assert all(0x1F9C0<=a<0x1FA00 for a in m.mem.writes),'music touched graphics'
    call(m,'music_tick')
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[0],'loop must restart cleanly'
    for _ in range(30):call(m,'music_tick')
    m.mem.ram[0x3F2]=0;call(m,'music_tick')
    assert not any(m.mem.vram[0x1F9C2:0x1FA00:4])
    before=m.value('music_frame',2);call(m,'music_tick');assert m.value('music_frame',2)==before
    m.mem.ram[0x3F2]=1;call(m,'music_tick')
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[0]
    # Independent sound OFF must not stop PSG; PCM playback must not touch PSG.
    m.mem.ram[0x3F3]=0;call(m,'sound_tick');call(m,'music_tick')
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[1]
    m.mem.ram[0x3F3]=1;call(m,'sound_play',0)
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[1]
    call(m,'music_stop');assert not any(m.mem.vram[0x1F9C2:0x1FA00:4])
    m.key(ord('R'))
    assert m.value('music_frame',2)==0 and not m.value('music_on'),'R must restart music'
    call(m,'music_tick');assert m.mem.vram[0x1F9C0:0x1FA00]==expected[0]
    m.mem.ram[0xC000]=0x9B;m.until(lambda:m.cpu.pc==0x2000)
    assert not any(m.mem.vram[0x1F9C2:0x1FA00:4]) and not m.mem.reg[28],'Esc must stop both audio paths'
    m.return_loader()
    print(f'PASS slot {slot}: {len(expected)} frames byte-exact, aux preload, zero runtime music disk reads, loop/OFF/ON, PCM independence; music cycles mean={np.mean(cycles):.0f} max={max(cycles)}',flush=True)
