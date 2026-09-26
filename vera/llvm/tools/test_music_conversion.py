"""Converter smoke tests, not a judgement of musical transcription quality."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from wav2psg import analyze, encode, percussion, route_short_transients, VERA

notes_test=np.array([40,60,74]);levels_test=np.zeros((60,3));drums_test=np.zeros((60,2))
levels_test[10:13,0]=1;levels_test[20:40,0]=1
levels_test[10:13,1:]=1;drums_test[11]=1
cleaned,routed=route_short_transients(notes_test,levels_test,drums_test)
assert not cleaned[10:13,0].any() and not cleaned[10:13,2].any()
assert cleaned[20:40,0].all() and cleaned[10:13,1].all()

hits=np.zeros((60,2));hits[10:14]=1
struck=percussion(hits)
assert np.any(struck[10,:,2]&63),'onset must trigger percussion'
assert not np.any(struck[29:,:,2]&63),'struck sounds must decay, not sustain'
assert np.all(struck[:,:,3]==0x80),'percussion must not revert to continuous noise'
assert struck[10,1,2]&63,'taiko must have a low membrane resonance voice'
double=np.zeros((60,2));double[10,0]=double[22,0]=1
double_hit=percussion(double)
assert double_hit[22,0,2]&63 and double_hit[22,2,2]&63,'second dong must not cut off first dong'
frequencies=double_hit[:,:,0].astype(int)+double_hit[:,:,1].astype(int)*256
assert np.max(frequencies*48828.125/131072)<140,'no woodblock/high click partials'

silence=np.zeros(16000)
notes,levels,drums=analyze(silence)
assert not levels.any() and not drums.any()
stream,registers,counts=encode(notes,levels,drums)
assert not registers[:,2::4].any(),'silence must not produce phantom notes'
tone=np.sin(2*np.pi*440*np.arange(16000)/16000)*0.5
notes,levels,drums=analyze(tone)
assert int(notes[np.argmax(levels[30])])==69,'A4 reference tone must detect A4'
stream,registers,counts=encode(notes,levels,drums)
active=[c for c in range(12) if registers[30,c*4+2]&63]
assert active
for c in active:
    freq=int(registers[30,c*4])+(int(registers[30,c*4+1])<<8)
    assert abs(freq*48828.125/131072-440)<1

data=(VERA/'generated/music_trial.psg').read_bytes()
pos=frames=pairs=0;shadow=bytearray(64)
while data[pos]!=255:
    count=data[pos];assert count<=64
    for n in range(count):
        reg,value=data[pos+1+n*2:pos+3+n*2]
        assert reg<64;shadow[reg]=value
    pos+=1+count*2;frames+=1;pairs+=count
assert pos+3==len(data) and data[pos+1:]==bytes(2)
assert not any(shadow[2::4]),'loop boundary must silence all voices'
assert frames==7583
print(f'PASS silence/A4 analysis and full original-duration stream: {frames} frames, {pairs} writes, {len(data)} bytes')
