# VERA PSG 音樂研究與目前取捨

## 已採用至遊戲：純音平滑版

後續音量追調：遊戲 Music gain 由2改為2.828427，相較前版約+3dB，相較來源PSG約+9dB；量化至VERA LUT，超過每聲道最高511則封頂。編排／音高／事件時間不改，核准的WAV本身未修改。音效预載是另一項尚未完成的工作，不能把音樂aux預載視為PCM音效也已預載。

使用者核准 `music_pure_player_linear_listen_louder.wav` 後，採其來源 `generated/music_midi_pure_smooth.psg` 的純音編排接入遊戲。`tools/build_music.py` 以 native PSG volume LUT 映射2倍增益，去重並bit-pack為 `generated/music.fgm`（41139 bytes／7398 frames，約123.3秒循環），disk target打包為 `MUSIC.FGM`。不用再取得ignored build內的原 MIDI 即可重建遊戲音樂。

`llvm/src/music.c`／`music_aux.S` 開局前預載至aux `$0800`起（不得超出 `$BFFF`），播放只從aux頁cache解碼，不做音樂 disk I/O。需要128KB Apple IIe；無aux安全停用。Options Music ON／OFF、R從頭、Esc停止再返回Title；目前Title／Options不播放。PCM音效與PSG音樂獨立。18-byte MAIN／AUX `$0300` reader鏡像避免RAMRD instruction-fetch切換造成崩潰，讀頁時關IRQ、結束恢復MAIN；loader下次launch會覆寫MAIN reader。

兩slot的實際65C02 binary經instrumented model逐frame比對全部7398frames通過，包含loop、OFF/ON、缺aux、Music初始OFF、graphics port保留、PCM互不影響、R／Esc和返回Title；音樂自身平均2801cycles、最高14948。遊戲／PCM／no-move／Options回歸通過；整體動畫仍約35.3kcycles平均（PCM串流等成本），並非1MHz全程60fps。尚未實際AppleWin／硬體試聽。

重要限制：核准WAV是高精度triangle／線性混音預覽，VERA實際波形6-bit與增益不同。遊戲是其純音音符／包絡的PSG版加約6dB，不是該WAV逐sample重播，不能聲稱响度或砂礫聲完全一致。若實機仍有不能接受的顆粒感，需另外評估PCM音樂、磁碟容量及與PCM音效混音的成本；本次沒有偷偷改回bass／打擊編排。

## Ensemble 短音清理（2026-09-27）

播放器排查：`tools/build_psgplay_compare.ps1` 建置 `llvm/build/psgplay_compare.exe`。Wrapper 編譯引用外部 veramusic 原始 player，不修改外部 repo；預設用 linear /16 headroom，`--original` 還原原版 tanh。`--render output.wav` 可用相同 oscillator／phase／register 更新方式離線輸出全曲。純音 PSG 實測混音 peak 0.903789（進 tanh 前除3），沒有高到足以直接認定嚴重飽和；不得把播放器 tanh 當已確認的砂礫聲來源。比較檔 `music_pure_player_original.wav` 與 `music_pure_player_linear_listen.wav`（linear /16 以16/3線性增益補回，近似原版小訊號增益）均無 PCM clipping，長度7398frames。預覽不是硬體擷取；線性播放器預設較小聲，測試時須注意響度差，尚未執行實際音訊播放驗證。使用者可再用 --original 作對照，PSG 音符不變。

純音排查版：`python vera/tools/midi_psg_arrange.py --pure --smooth`，輸出 `music_midi_pure_smooth.psg`。移除 note<48 與明確 GM drum／taiko，保留高音域的來源音符，統一 keys triangle 包絡；不加整數泛音、音域配器／鼓模擬／強音壓縮，保留短高音清理及 60Hz 平滑。來源沒有分軌，按音域移除 bass 也可能拿掉其他低音旋律；高音域內原轉錄的敲擊碎片不能聲稱完全分離。測試涵蓋 bass／drum 不輸出、單音不產生額外聲道與純 triangle。這是用來排查砂礫聲的版本，非原曲精確分軌，尚未接入遊戲。

使用者要求回 smooth_soft 單獨拿掉 taiko：`--style ensemble --no-overtones --smooth --soft-percussion --no-taiko`。MIDI 全 channel0／program0，並沒有真正 taiko 聲道。檢查約5.36／11.22／17.08／22.94秒都有強短 D2（note38）與短低音碎片群；以 note38、velocity>=75、75–150ms 作錨點，移除其前1秒／後0.8秒內 note<48、duration<=180ms 的配對事件。全曲同規則，非整段靜音；保留 marimba 與持續 bass，但可能刪掉該區域真正的短 bass，必須試聽確認。輸出 `music_midi_ensemble_no_overtones_smooth_soft_no_taiko.psg`，移除529事件對／90351 bytes，測試檢查四處錨點及持續 bass／marimba 保留，完整 stream 通過。尚未確認這些就是砂礫声來源，未接入遊戲。

無打擊樂對照：`--style ensemble --no-overtones --smooth --no-percussion`，移除啟發式 marimba（note 60–71）及明確 GM drum channel／taiko program 音符，保留 bass／guitar／celesta。來源 MIDI 沒有真正的打擊分軌，因此可能一併移除該音域的旋律，且 celesta／guitar 仍有 pluck 音色；不可稱為原曲分軌分離。輸出名稱 `music_midi_ensemble_no_overtones_smooth_no_percussion.psg`，保留其他版本供比較；測試檢查 marimba／drum 被省略且 guitar 不受開關影響，未接入遊戲。

大敲擊仍有砂礫感的第三份對照：`--style ensemble --no-overtones --smooth --soft-percussion`，輸出 `music_midi_ensemble_no_overtones_smooth_soft.psg`（103753 bytes）。對啟發式 guitar／marimba／celesta／drum 的音符力度套 soft knee：振幅 <=0.12 不改，以上以指數漸近至 0.20；bass 不改。這不是從 MIDI 找回真正敲擊分軌，也會降低較強的旋律 pluck。力度改變會影響 voice allocation（245 steals，原平滑版255）；來源事件／節奏／音高不改，但不能聲稱所有較輕音符的輸出 registers 完全相同。動態函式單調、不增益、低力度與 bass 保留測試及完整 stream 驗證通過。仍待 psgplay 試聽，不宣稱砂礫聲已消除。

砂礫聲第二份對照：在 `--no-overtones` 後加 `--smooth`，輸出 `music_midi_ensemble_no_overtones_smooth.psg`（105887 bytes／7398 frames）。關閉 20Hz 包絡節流、改每 frame 更新；gate／同聲道換音高的連續段套三 frame raised-cosine 起落，立即換音高前一 frame 靜音。保留來源音高與事件時間，但短音會較柔和，輸出事件數增加。測試涵蓋起落衰減、換音高靜音、音高不改及尾端靜音；PSG 流驗證通過。這不是 sample-level de-click，播放器相位／tanh 混音也未更改，砂礫聲是否消除仍待使用者試聽；未接入遊戲。

砂粒感對照版：`python vera/tools/midi_psg_arrange.py --style ensemble --no-overtones`，輸出 `generated/music_midi_ensemble_no_overtones.psg` 及同名 WAV／JSON。僅停用額外 2f／3f 短促泛音，主音配器、清理、力度與包絡不變；保留原 ensemble 檔供 A/B 試聽。單音測試確認無額外聲道且 primary registers 相同。此對照尚未證明砂粒聲來源，未接入 HDV。

依使用者回報檢查 0:23、1:11、1:13、1:17、1:21：MIDI 存在弱力度、高音域的短促音群。Ensemble 現在過濾 note >=84、velocity <=40、duration <=220ms 的疑似轉錄雜音，以及其前後 80ms 內 note >=72、velocity <=50、duration <=75ms 的短音。規則套用全曲，不按指定時間整段靜音；成對移除 note-on/off，保留較強或較長音符。這是啟發式清理，仍可能移除真實弱短音，需試聽確認；原 MIDI 與 clean 版本不變。

本次移除 151 顆疑似雜音，PSG 89927 bytes，voice steals 255。測試檢查指定區段清理、0:23 持續旋律保留與強高音不被刪除；完整 PSG 流驗證通過。詳細移除清單保留在輸出 JSON。

最新預覽在 `llvm/build/music_midi_ensemble_fixed.wav`（全曲）、`music_midi_ensemble_fixed_25s.wav`（前 25 秒）、`music_midi_ensemble_fixed_69s.wav`（1:09 起 16 秒）。均為線性增益 3 的軟體預覽，未接入遊戲／HDV。

2026-09-27。這些是研究和試作，不代表已移植至遊戲。

## 來源

- [原作者 Easy Lemon 曲目頁](https://incompetech.com/music/royalty-free/index.html?Search=Search&isrc=USUAN1200076)：Guitar、Bass、Kit、Celesta、Marimba，82 BPM，2:06。使用者轉錄的 MIDI 為 format 0、一個 channel、program 0（鋼琴）、3175 notes、約 122.77 秒，並沒有恢復原曲多樂器／鼓組分軌。
- [DreamTracker VERA Instruments](https://dreamtracker.bitbybitsynths.com/manual/vera_instruments/) 與 [Envelopes](https://dreamtracker.bitbybitsynths.com/manual/envelopes/)：音量／PWM envelope、波形、聲道與 pitch 控制是 PSG 配器的基本工具；不是單純替換 MIDI 播放器。
- [Furnace VERA instruments](https://github.com/tildearrow/furnace/blob/master/doc/4-instrument/vera.md)：支援 Volume、Arpeggio、Duty、Waveform、Panning、Pitch macros。可作為手工精修配器的工具；沒有把 MIDI 自動轉成原作樂器的保證。
- [VERA 音訊規格](https://github.com/X16Community/x16-docs/blob/master/X16%20Reference%20-%2009%20-%20VERA%20Programmer%27s%20Reference.md)：16 voices、四種波形、log volume、17-bit phase。AppleWin 實際行為另對照本機 VERAAudio.cpp，不混用 YM2151 或 wavetable expansion 的音色能力。

## 舊 converter 的具體問題

`veramusic/tools/mid2psg.mjs` 的先前 piano preset 是針對其他曲目的特殊調整，不能直接當通用忠實 converter：低音會增加數個 voices（包含 +7 semitone 的額外音高）、低於 note 36 自動升八度、bass note-off 以每 frame 0.35 volume index 減少，尾音可拖數秒，力度被壓到高 volume。WAV 預覽还加入 tanh 飽和增益，且 noise 在該預覽 renderer 為零；pulse duty 公式也不同於本機硬體。

## 新試作

`tools/midi_psg_arrange.py`：保留音符音高／原力度／tempo、CC64 sustain、pitch bend；一個來源音符一個 primary voice；不自動移調、不亂加五度、note-off 約 45ms 指數 release。淡出在 20Hz 更新以縮小事件流；起音／關閉即時更新。仍可能遇到 16 voice 上限，報告列出 voice steal 次數，不掩蓋缺音。

- `--style clean`：保留鋼琴式 triangle，重新平衡 bass 和自然音量 envelope，不做原作樂器分離。
- `--style ensemble`：依音域推估 bass／guitar／marimba／celesta，不聲稱找回原作 stems。不同角色使用不同 pluck decay；僅在有空聲道時加 2f／3f、低音量、快速消退的真泛音起音，不搶 primary。這是可試聽的配器改編，仍需人工校訂與使用者確認。

輸出 `generated/music_midi_clean.psg`／`music_midi_ensemble.psg`。原始硬體增益預覽在 `llvm/build/music_midi_*.wav`；`*_listen_25s.wav` 只為方便試聽提升 3 倍線性音量，沒有 compressor／tanh／normalize；不修改 PSG。預覽不是 AppleWin／實機擷取，不能把它当作硬體試聽驗證。

還需解決：原作 kit／雙擊低鼓的分離、分軌／配器精修、較接近原作的音色、音樂與預載 PCM 音效的共同記憶體配置、IRQ 預算與實機試聽。純 PSG 無法聲稱 100% 恢復原作錄音。
