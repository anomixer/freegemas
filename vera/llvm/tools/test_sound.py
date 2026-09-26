"""Verify actual original PCM bytes, FIFO boundaries and game integration."""
from test_mos import Machine, VERA, move, swap

def playback(name):
    data=(VERA/'generated'/f'{name}.pcm').read_bytes()
    return data[:6640] if name in ('match1','match2','match3') else data

def call(m,name,arg=0):
    pc,sp=m.cpu.pc,m.cpu.sp
    m.cpu.a=arg;m.cpu.stPushWord(0x02FE);m.cpu.pc=m.sym[name]
    m.until(lambda:m.cpu.pc==0x02FF)
    assert m.cpu.sp==sp
    m.cpu.pc=pc

for slot in (2,4):
    m=Machine(slot);m.boot_game(1)
    assert m.value('ready')==1,'all original samples must load'
    # Every sample must stay in one memory domain, never switch VRAM to aux.
    for index in range(5):
        at=m.sym['samples']+index*6
        offset=int.from_bytes(m.mem.ram[at:at+4],'little')
        length=int.from_bytes(m.mem.ram[at+4:at+6],'little')
        assert offset>=27904 or offset+length<=27904,(slot,index,offset,length)
    assert int.from_bytes(m.mem.ram[m.sym['samples']+18:m.sym['samples']+22],'little')==27904
    expected_match2=(VERA/'generated'/'match2.pcm').read_bytes()
    assert bytes(m.mem.aux[0x2C00:0x2C00+len(expected_match2)])==expected_match2
    m.mem.vram[0x1F9C0:0x1FA00]=bytes([0xA5])*64
    m.mem.addr[:]=[0x12345,0x18010];m.mem.inc[:]=[320,40];m.mem.ctrl=3
    saved=(m.mem.addr[:],m.mem.inc[:],m.mem.ctrl)
    for effect,name in ((0,'select'),(5,'fall'),(2,'match1'),(3,'match2'),(4,'match3')):
        m.mem.pcm_writes.clear();m.mem.writes.clear()
        reads_before=m.read_calls
        call(m,'sound_play',effect)
        assert m.mem.reg[28]==29 and m.mem.reg[27]&63==47
        for frame in range(80):
            # Advance model playback by a frame, then execute actual refill.
            m.mem[m.mem.base+7]=1
            call(m,'sound_tick')
            if not m.mem.reg[28]:break
        else:raise AssertionError('sample must drain and stop')
        expected=playback(name)
        assert bytes(m.mem.pcm_writes)==expected,(slot,name,len(m.mem.pcm_writes),len(expected))
        assert not (m.mem.reg[27]&15),'EOF must mute PCM, not hold its last sample'
        assert m.read_calls==reads_before,'playing cached PCM must not read disk'
        assert not m.mem.writes and (m.mem.addr,m.mem.inc,m.mem.ctrl)==saved
        assert m.mem.vram[0x1F9C0:0x1FA00]==bytes([0xA5])*64
    # AppleWin drops a lone low byte when a 16-bit FIFO underruns. A full
    # 4095-byte FIFO leaves an odd source cursor: refill must replay that low
    # byte rather than treating the high byte as the next sample's low byte.
    for effect,name in ((3,'match2'),(4,'match3')):
        call(m,'sound_play',effect)
        assert len(m.mem.pcm_fifo)==4095
        m.mem.pcm_fifo.clear() # long CPU gap; hardware consumed/discarded tail
        m.mem.pcm_writes.clear()
        call(m,'sound_tick')
        expected=playback(name)
        assert bytes(m.mem.pcm_writes)==expected[4094:4094+len(m.mem.pcm_writes)],'underrun shifted 16-bit byte alignment'
    # Force a cascade before each previous effect has drained. The new FIFO
    # and every subsequent refill must contain only the replacement sample.
    call(m,'sound_play',2)
    for effect,name in ((3,'match2'),(4,'match3')):
        assert m.mem.pcm_fifo,'previous effect still playing'
        resets=m.mem.pcm_resets;reads=m.read_calls
        m.mem.pcm_writes.clear()
        call(m,'sound_play',effect)
        expected=playback(name)
        assert m.mem.pcm_resets==resets+1
        assert bytes(m.mem.pcm_fifo)==expected[:len(m.mem.pcm_fifo)]
        for frame in range(3):
            m.mem[m.mem.base+7]=1;call(m,'sound_tick')
        assert bytes(m.mem.pcm_writes)==expected[:len(m.mem.pcm_writes)],'old effect leaked after replacement'
        assert m.read_calls==reads
    call(m,'sound_stop')
    assert not m.mem.reg[28] and not m.mem.pcm_fifo and not m.value('remaining',2)
    assert not m.value('cursor',4) and not m.value('cached_aux')
    call(m,'sound_tick');assert not m.mem.pcm_fifo,'stopped sample must not resume'
    call(m,'sound_play',2);m.mem.ram[0x3F3]=0;call(m,'sound_tick')
    assert not m.mem.reg[28] and not m.mem.pcm_fifo
    sent=len(m.mem.pcm_writes);call(m,'sound_play',0)
    assert len(m.mem.pcm_writes)==sent
    m.mem.ram[0x3F3]=1;call(m,'sound_play',0);assert m.mem.reg[28]==29
    # Unsupported invented effects must not alter PCM playback.
    state=(m.mem.reg[28],bytes(m.mem.pcm_fifo),m.mem.pcm_resets)
    for effect in (1,6,7,8):call(m,'sound_play',effect)
    assert state==(m.mem.reg[28],bytes(m.mem.pcm_fifo),m.mem.pcm_resets)
    call(m,'sound_stop')
    move(m,4,3);swap(m)
    m.mem.ram[0xC000]=0x9B
    m.until(lambda:m.cpu.pc==0x2000)
    assert not m.mem.reg[28] and not m.mem.pcm_fifo
    print(f'PASS slot {slot}: five original PCM streams byte-exact, match2/3 underrun realignment, FIFO bounded/drained, OFF/ON, graphics/PSG untouched, swap/exit')
