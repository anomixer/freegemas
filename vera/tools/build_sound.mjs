import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {spawnSync} from 'node:child_process';
// Original recordings, original gain; VERA 16-bit mono at rate 29.
const vera=path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const rate=29*25000000/512/128;
for(const name of ['select','fall','match1','match2','match3']) {
  const gain=name.startsWith('match')?0.25:0.3;
  const result=spawnSync('ffmpeg',['-v','error','-i',path.join(vera,'../media',name+'.ogg'),
    '-af',`volume=${gain},aresample=${Math.round(rate)}:filter_size=64:phase_shift=10`,
    '-ac','1','-f','s16le','pipe:1'],{maxBuffer:2**24});
  if(result.status!==0)throw new Error(result.stderr.toString());
  let outData = result.stdout;
  if(name.startsWith('match') && outData.length > 6640) {
    outData = outData.subarray(0, 6640);
  }
  fs.writeFileSync(path.join(vera,'generated',name+'.pcm'), outData);
  const wav=spawnSync('ffmpeg',['-v','error','-y','-f','s16le','-ar',String(Math.round(rate)),
    '-ac','1','-i','pipe:0',path.join(vera,'llvm/build',name+'_pcm.wav')],{input: outData});
  if(wav.status!==0)throw new Error(wav.stderr.toString());
  console.log(`${name}: ${outData.length} bytes, gain ${gain}, VERA rate 29 (${rate} Hz)`);
}
