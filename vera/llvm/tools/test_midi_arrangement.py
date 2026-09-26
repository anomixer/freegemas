"""Clean arrangement preserves notes/dynamics and doesn't invent harmony."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools'))
from midi_psg_arrange import arrange, read_midi, remove_transcription_blips, remove_low_hit_clusters, smooth_register_edges, soften_pluck_peak, VERA
from wav2psg import CLOCK

events=[(0,9,0,33,100),(0.2,8,0,33,0),(0.6,'end',0,0,0)]
stream,regs,stats=arrange(events)
assert stats['max_active_voices']==1,'one bass note must not create extra fifths/octaves'
hz=(regs[:,0].astype(int)+(regs[:,1].astype(int)<<8))*CLOCK/131072
active=(regs[:,2]&63)>0
assert np.all(np.abs(hz[active]-55)<1),'bass pitch must not be transposed'
assert not np.any(regs[30:,2::4]&63),'note-off release must not last several seconds'
soft=arrange([(0,9,0,69,30),(0.1,8,0,69,0),(0.2,'end',0,0,0)])[1]
loud=arrange([(0,9,0,69,110),(0.1,8,0,69,0),(0.2,'end',0,0,0)])[1]
assert soft[1,2]&63<loud[1,2]&63,'velocity must retain useful dynamics'
events,info=read_midi(VERA/'llvm/build/music_original.mid')
no_hits,hits=remove_low_hit_clusters(events)
for at in (5.36,11.22,17.08,22.94):
    assert any(x['note']==38 and abs(x['time']-at)<.03 for x in hits)
fixture_hits=[(0,9,0,38,90),(.1,8,0,38,0),(.15,9,0,32,70),(.65,8,0,32,0),
    (.2,9,0,65,90),(.3,8,0,65,0),(1,'end',0,0,0)]
retained,removed=remove_low_hit_clusters(fixture_hits)
assert len(removed)==1 and (.15,9,0,32,70) in retained and (.2,9,0,65,90) in retained
single=[(0,9,0,69,100),(.3,8,0,69,0),(.6,'end',0,0,0)]
with_partials=arrange(single,style='ensemble')[1]
without_partials=arrange(single,style='ensemble',overtones=False)[1]
assert np.any(np.sum((with_partials[:,2::4]&63)>0,axis=1)>1)
assert np.max(np.sum((without_partials[:,2::4]&63)>0,axis=1))==1
assert np.array_equal(with_partials[:,:4],without_partials[:,:4]),'primary voice must remain unchanged'
edge_fixture=np.zeros((20,64),dtype=np.uint8)
edge_fixture[:10,:4]=[100,1,192|50,128]
edge_fixture[10:18,:4]=[200,1,192|50,128]
edges=smooth_register_edges(edge_fixture)
assert edges[0,2]&63 < edges[3,2]&63 == 50
assert edges[9,2]==0,'mute before immediate pitch reuse'
assert edges[10,2]&63 < edges[13,2]&63 == 50
assert edges[17,2]&63 < 50 and not np.any(edges[18:,2::4])
assert np.array_equal(edges[:,0:2],edge_fixture[:,0:2]),'do not change pitch or timing'
assert np.all((edges[:,2::4]&63)<=(edge_fixture[:,2::4]&63))
for role in ('guitar','marimba','celesta','drum'):
    values=np.array([soften_pluck_peak(v,role) for v in np.linspace(0,1,101)])
    assert np.all(np.diff(values)>=0) and np.all(values<=np.linspace(0,1,101)+1e-12)
    assert soften_pluck_peak(.1,role)==.1 and soften_pluck_peak(.8,role)<.2
assert soften_pluck_peak(.8,'bass')==.8
percussion_fixture=[(0,9,0,65,100),(.2,8,0,65,0),
    (.3,9,9,40,100),(.5,8,9,40,0),(.6,'end',0,0,0)]
_,silent,omitted=arrange(percussion_fixture,style='ensemble',no_percussion=True)
assert omitted['omitted_percussion_notes']==2 and not np.any(silent[:,2::4]&63)
guitar_fixture=[(0,9,0,57,100),(.3,8,0,57,0),(.6,'end',0,0,0)]
_,baseline,_=arrange(guitar_fixture,style='ensemble',overtones=False)
_,kept,omitted=arrange(guitar_fixture,style='ensemble',overtones=False,no_percussion=True)
assert omitted['omitted_percussion_notes']==0 and np.array_equal(kept,baseline)
pure_fixture=[(0,9,0,33,100),(.2,8,0,33,0),(.3,9,9,60,100),(.5,8,9,60,0),
    (.6,9,0,69,100),(.9,8,0,69,0),(1,'end',0,0,0)]
_,pure,stats=arrange(pure_fixture,style='ensemble',pure=True,smooth=True)
assert stats['omitted_bass_notes']==1 and stats['omitted_percussion_notes']==1
assert not np.any(pure[:36,2::4]&63)
assert np.max(np.sum((pure[:,2::4]&63)>0,axis=1))==1
assert np.all(pure[:,3::4]==128),'pure output must only use unmodified triangle'
filtered,blips=remove_transcription_blips(events)
assert any(x['note']==94 and 23.3<x['time']<23.6 for x in blips),'23s high anomaly must be removed'
for at in (71,72.55,77,81.33):
    assert any(abs(x['time']-at)<0.2 for x in blips),(at,'reported high burst not cleaned')
lead = [event for event in events if event[1] == 9 and event[3] == 73 and abs(event[0] - 23.5) < .002]
assert lead and all(event in filtered for event in lead)
fixture=[(0,9,0,94,30),(0.05,8,0,94,0),(.2,9,0,94,100),(.25,8,0,94,0),
    (.3,9,0,73,30),(.7,8,0,73,0),(1,'end',0,0,0)]
fixed,removed=remove_transcription_blips(fixture)
assert len(removed)==1 and (.2,9,0,94,100) in fixed and (.3,9,0,73,30) in fixed
assert sum(k==9 and b>0 for _,k,c,a,b in events)==3175
assert {c for _,k,c,a,b in events if k==9 and b>0}=={0}
data=(VERA/'generated/music_midi_clean.psg').read_bytes();pos=frames=0;shadow=bytearray(64)
while data[pos]!=255:
    count=data[pos];assert count<=64
    for i in range(count):
        r,v=data[pos+1+2*i:pos+3+2*i];assert r<64;shadow[r]=v
    pos+=1+count*2;frames+=1
assert pos+3==len(data) and data[pos+1:]==bytes(2)
assert not any(shadow[2::4]),'all voices must be silent at loop boundary'
print(f'PASS original pitch, no extra harmony, short release, velocity, source MIDI and {frames}-frame stream')
