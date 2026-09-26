"""Render mono16 FIFO against CPU cycles, including orphan-byte discard."""
from test_mos import Machine, VERA

def call(m,name,arg=0):
    pc,sp=m.cpu.pc,m.cpu.sp
    m.cpu.a=arg;m.cpu.stPushWord(0x02FE);m.cpu.pc=m.sym[name]
    m.until(lambda:m.cpu.pc==0x02FF)
    assert m.cpu.sp==sp
    m.cpu.pc=pc

for slot,effect,name in ((2,2,'match1'),(2,3,'match2'),(2,4,'match3'),(4,2,'match1'),(4,3,'match2'),(4,4,'match3')):
    m=Machine(slot);m.boot_game(1);m.mem.pcm_clocked=True
    rendered=bytearray();phase=[0];orphans=[0]
    original_step=m.step
    def advance(cycles):
        if not m.mem.reg[28]:return
        phase[0]+=cycles*m.mem.reg[28]*25_000_000
        period=1_023_000*512*128
        while phase[0]>=period:
            phase[0]-=period
            if len(m.mem.pcm_fifo)>=2:
                rendered.extend(m.mem.pcm_fifo[:2]);del m.mem.pcm_fifo[:2]
            elif m.mem.pcm_fifo:
                m.mem.pcm_fifo.clear();orphans[0]+=1
    def step():
        before=m.cpu.processorCycles;original_step()
        advance(m.cpu.processorCycles-before)
    m.step=step
    call(m,'sound_play',effect)
    expected=(VERA/'generated'/f'{name}.pcm').read_bytes()[:6640]
    for frame in range(300):
        # A deliberately long gap drains FIFO; later normal gaps exercise
        # hardware playback *during* aux page reads and byte-by-byte feeds.
        advance(230_000 if frame%7==0 else 22_000)
        call(m,'music_tick');call(m,'sound_tick')
        if not m.mem.reg[28]:break
    assert rendered==expected,(name,len(rendered),len(expected),orphans[0],next((i for i,(a,b) in enumerate(zip(rendered,expected)) if a!=b),None))
    assert not (m.mem.reg[27]&15),'EOF must mute the retained output sample'
    print(f'PASS slot {slot} clocked {name}: actual rendered samples exact, orphan recoveries={orphans[0]}',flush=True)
