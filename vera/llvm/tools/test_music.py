"""Play the shipped MUSIC.PSG fallback through the real 65C02 player.

Instrumented model only, not a listening test or real hardware timing.
The FM stream has its own coverage in test_music_vzm.py.
"""
import numpy as np
from test_mos import Machine, VERA

def call(m,name,arg=0):
    pc,sp=m.cpu.pc,m.cpu.sp
    m.cpu.a=arg;m.cpu.stPushWord(0x02FE);m.cpu.pc=m.sym[name]
    m.until(lambda:m.cpu.pc==0x02FF)
    assert m.cpu.sp==sp and not m.mem.aux_read and not m.mem.aux_write
    m.cpu.pc=pc

source=(VERA/'generated/music_pure_gained.psg').read_bytes()
expected=[];starts=[];shadow=bytearray(64);shadow[3::4]=bytes([128])*16;pos=0
while source[pos]!=255:
    starts.append(pos)
    count=source[pos];pos+=1
    assert count<=64
    for _ in range(count):
        reg,value=source[pos:pos+2];pos+=2
        shadow[reg]=value
    expected.append(bytes(shadow))
assert source[pos:]==bytes((255,0,0)),'stream must end with the loop marker'
import bisect
def frame_at(offset):
    return 0 if offset>=pos else bisect.bisect_right(starts,offset)-1

for slot in (2,4):
    disabled=Machine(slot);disabled.mem.ram[0x3F4]=0xA5;disabled.mem.ram[0x3F2]=0
    disabled.boot_game(1);call(disabled,'music_tick')
    assert not disabled.value('music_on') and not any(disabled.mem.vram[0x1F9C2:0x1FA00:4])
    limited=Machine(slot);limited.mem.aux_present=False;limited.mem.ram[0x800]=0xA5
    limited.boot_game(1)
    assert not limited.value('music_ready') and limited.mem.ram[0x800]==0xA5,'no aux must safely disable music'
    m=Machine(slot);m.boot_game(1)
    assert m.value('music_ready')==1 and not m.value('music_fm'),'stock machine must take the PSG path'
    for position,byte in enumerate(source):
        page=8+(position>>8)
        # Pages $08..$BF live in aux 48K RAM; $C0.. go to aux LC bank 1.
        at=0x800+(page-8)*256+(position&255) if page<0xC0 else 0xD000+(page-0xC0)*256+(position&255)
        assert (m.mem.aux if page<0xC0 else m.mem.ram)[at]==byte,(position,hex(at))
    assert m.mem.ram[0x300:0x312]==m.mem.aux[0x300:0x312]
    m.mem.addr[:]=[0x12345,0x18010];m.mem.inc[:]=[320,40];m.mem.ctrl=3
    saved=(m.mem.addr[:],m.mem.inc[:],m.mem.ctrl)
    reads=m.read_calls;cycles=[];m.mem.writes.clear()
    call(m,'music_restart')
    for frame,registers in enumerate(expected):
        before=m.cpu.processorCycles;call(m,'music_tick');cycles.append(m.cpu.processorCycles-before)
        assert m.mem.vram[0x1F9C0:0x1FA00]==registers,(slot,frame)
        assert (m.mem.addr,m.mem.inc,m.mem.ctrl)==saved,(slot,frame,'graphics port')
        assert m.read_calls==reads,'music must not read disk while playing'
    assert not any(m.mem.vram[0x1F9C2:0x1FA00:4]),'final frame must be silent'
    assert all(0x1F9C0<=a<0x1FA00 for a in m.mem.writes),'music touched graphics'
    call(m,'music_tick')
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[0],'loop must restart cleanly'
    # OFF mutes and rewinds; ON replays the stream from the first tick.
    m.mem.ram[0x3F2]=0;call(m,'music_tick')
    assert not any(m.mem.vram[0x1F9C2:0x1FA00:4]) and not m.value('music_on')
    m.mem.ram[0x3F2]=1;call(m,'music_tick')
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[0]
    # Independent sound OFF must not stop PSG; PCM playback must not touch PSG.
    m.mem.ram[0x3F3]=0;call(m,'sound_tick');call(m,'music_tick')
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[1]
    m.mem.ram[0x3F3]=1;call(m,'sound_play',0)
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[1]
    call(m,'music_stop');assert not any(m.mem.vram[0x1F9C2:0x1FA00:4])
    m.key(ord('R'))
    position=m.value('music_position',2)
    assert position<len(source),'R must restart the stream from its first frame'
    call(m,'music_tick')
    assert m.mem.vram[0x1F9C0:0x1FA00]==expected[frame_at(position)],'R must resume a restarted stream'
    assert m.value('music_on'),'R must leave music playing'
    m.mem.ram[0xC000]=0x9B;m.until(lambda:m.cpu.pc==0x2000)
    assert not any(m.mem.vram[0x1F9C2:0x1FA00:4]) and not m.mem.reg[28],'Esc must stop both audio paths'
    m.return_loader()
    print(f'PASS slot {slot}: {len(expected)} frames byte-exact, aux preload, zero runtime music disk reads, loop/OFF/ON, PCM independence; music cycles mean={np.mean(cycles):.0f} max={max(cycles)}',flush=True)
