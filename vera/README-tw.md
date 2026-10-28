# Freegemas for Apple //e VERA

[English](README.md) | 繁體中文

這是 Freegemas 的 Apple //e VERA 移植版。遊戲以 LLVM-MOS C 編譯為 65C02 程式，使用 VERA 320×240、8bpp bitmap、常駐 gem sprites 與頂部遮罩繪圖，透過 ProDOS HDV 分段載入標題、遊戲和說明／設定畫面。

目前可直接測試的磁碟映像是 [`freegemas.hdv`](freegemas.hdv)，容量 800 KB。

## 建置

需要 Node.js、Python（NumPy）、ffmpeg／ffprobe、CMake、LLVM-MOS SDK 與 Cadius。Windows 使用隨附的 `llvm/tools/cadius.exe`；其他平台需將 Cadius 放入 `PATH`，或以 `-DCADIUS_EXECUTABLE=/path/to/cadius` 指定。ProDOS 系統檔位於 `assets/prodos-system/`，不依賴 time-pilot checkout。

在 repo 根目錄執行：

```powershell
node vera\tools\build_assets.mjs
cmake -S vera\llvm -B vera\llvm\build
cmake --build vera\llvm\build --target disk --parallel 4
```

`build_assets.mjs` 從 repo 的 `media/` 產生 indexed bitmap、sprites、palette 與 RLE 場景。CMake 會建立 slot 2／slot 4 的遊戲 binary，`build_hdv.py` 再將它們和場景檔打包成 `vera/freegemas.hdv`。

目前工具鏈預設位於 `C:\dev\llvm-mos-sdk\install`；其他安裝位置可用 CMake 的 `-DLLVM_MOS_SDK=...` 指定。HDV builder 使用 Cadius 建立新的 800 KB ProDOS volume，再加入系統檔與遊戲檔案，不再依賴 HDV 範本。

AppleWin 範例：

```powershell
AppleWin.exe -s2 vera -s7 hdc -h1 C:\dev\freegemas\vera\freegemas.hdv
```

AppleWin 若正掛載映像，重建前先關閉模擬器，避免 HDV 被鎖住。

## 以 ProDOS 檔案安裝

HDV volume name 為 `FREEGEMAS`。若要安裝到其他 ProDOS volume 或子目錄，請將 HDV 內所有檔案複製到目標位置，唯獨不複製 `PRODOS`。請保留 `FREEGEMAS` marker 檔，將 ProDOS prefix 設為該位置，再執行 `FREEGEM.SYSTEM`。Loader 和遊戲會依檔名開啟程式、場景、圖樣、音樂、音效及 `HISCORE.DAT`，不依賴原 HDV 的 block 配置。新產生的檔案目錄項目會寫入本機建置日期與時間，格式符合 ProDOS。

舊版以範本建立的 HDV 已用 AppleWin 確認可直接開機、進入遊戲並返回 Title；檔案層級安裝到 VeraSD 也已確認可執行且 `HISCORE.DAT` 能持久寫入。新的 Cadius HDV 已建置並檢查 ProDOS catalog，但仍需重新驗證開機。

啟動時先偵測 slot 2／4 的 VERA；兩者皆無卡時仍完整顯示作者、網址、滑鼠偵測及操作說明。STATUS 顯示 `VERA NOT DETECTED`，下方顯示 `STOPPED: VERA REQUIRED IN SLOT 2 OR 4` 並停止；按鍵也不會進入 Title 或遊戲。

## 操作

- Title：方向鍵選擇；Space／Enter 開啟 Time Trial、Endless、How to Play 或 Options。
- How to Play：任意鍵返回 Title。
- Options：上下移動；Space／Enter 切換 Music、Sound，或選 Back；Esc 返回 Title。
- 遊戲：方向鍵或 Apple Mouse Card 移動游標；Space 或滑鼠點擊選取／交換，H 顯示提示，R 重設，Esc 返回 Title。滑鼠顯示原作手形游標，也可點左側 Show Hint、Reset Game、Exit。滑鼠支援 slot 4／5；VERA 裝在 slot 4 時，Mouse Card 請裝 slot 5。
- Title 的 EXIT：保存高分後，以 ProDOS QUIT 回到 Bitsy Bye 檔案選單。
- 啟動時先顯示作者 ANOMIXER 2026 與操作鍵說明；按任意鍵或等 5 秒進入 Title，遊戲回 Title 不重播。
- 開機 STATUS 也顯示 `MOUSE: SLOT 4`／`MOUSE: SLOT 5`／`MOUSE: NONE`，確認滑鼠卡偵測結果。

Sound 已改為原作 `select.ogg`、`fall.ogg`、`match1–3.ogg` 解碼的 VERA PCM，不再使用自創 PSG 音色。原作音量 0.3／0.25 保留；沒有額外的 Hint／Reset／Game Over 音效。Options 的 Sound／Music 分別控制音效與遊戲背景音樂。Fullscreen 固定 ON。Time Trial 為兩分鐘倒數；Endless 不顯示時間面板。

遊戲背景音樂有兩條路徑。機器上有 A2VERA FM 女兒板時，開機 Intro 會偵測 YM2151 並顯示 `FM: YM2151 DETECTED (OPM)`，遊戲改載入 `MUSIC.VZM`（packed ZSM 串流，22974 bytes、7582 個 VSYNC tick、約 126.4 秒），以八個 FM 聲道演奏旋律、PSG 打擊聲部。沒有晶片或找不到 `MUSIC.VZM` 時顯示 `FM: NONE, PSG MUSIC ONLY`，改用下方的 `MUSIC.PSG`。`tools/build_music_vzm.py` 在建置時把原作 `media/music.ogg` 轉成此串流（FFT 音高／起音分析、聲部指派、寄存器去重）；Intro 與播放器共用的 71-byte BUSY probe 放在 `llvm/src/fm_probe.h`。整份 VZM 預載到輔助 RAM（90 個 logical page），播放時零磁碟讀取；HDV 同時包含 `MUSIC.PSG` 與 `MUSIC.VZM`。

後備的 PSG 路徑採使用者選定的純音平滑版（+9dB 增益，`generated/music_pure_gained.psg`，56675 bytes、7398 frames、約 123.3 秒循環），直接以原始 `MUSIC.PSG` 格式播放，不再使用執行期 FGM2／Huffman 曲線解壓縮（同時釋放主 RAM 空間）。開局前全部預載到 Apple IIe 輔助 RAM（`$0800–$BFFF`，46 KB）與 Auxiliary Language Card Bank 1（連續 `$D000–$FFFF`，12 KB），播放時零磁碟讀取；PSG 與 PCM 音效分開，R 重播、Esc 靜音返回 Title。音樂目前只在遊戲畫面播放，Title／Options 不播放。需要 128KB Apple IIe；沒有輔助 RAM 時安全停用音樂與音效。

`MUSIC.VZM` 在起播與每次 loop 會先送 key-off 並把 YM2151 寄存器歸零，這兩個 tick 各約 45k cycles（1.023 MHz 下約 44 ms）；其餘 tick 平均只有數百 cycles。

match1／2／3 在建置階段直接截斷為前約 0.30 秒（6640 bytes），切掉長尾音；五個 PCM 音效總計降為 26912 bytes，完全塞入 VERA VRAM 的 27904 bytes 預載池，不再佔用輔助 RAM。硬體 PCM FIFO 固定 4KB，起播已填滿，不能由遊戲調大；現有取樣格式約可緩衝 185ms。FIFO 播完後明確靜音、停採樣並清空，不保留最後樣本。select／fall 未變；三份 match 音效不再是完整原作錄音播放。

`LOADING GAME...` 在遊戲程式載入後會顯示20格進度條、百分比及目前資產階段；依實際 data blocks 更新，棋盤準備完成才到100%。遊戲 binary 本身載入期間仍是原本文字提示，進度條涵蓋寶石／場景／音樂／音效預載，不會加入額外等待。

FIFO 見底時會先停止採樣，再恢復16-bit樣本對齊並預填 FIFO 後恢復播放：AppleWin 會丟棄尾端孤立的1 byte，補資料前須重送該樣本的 low byte，且不能在補完 high byte 前繼續採樣。此路徑有 match2／3 強制 underrun 回歸，以及 `test_pcm_clock.py` 按CPU時間實際消耗FIFO的渲染樣本比對；長運算造成的缺音與實際聽感仍需另行驗證。

無合法交換時依原作規則：Endless 結束並顯示 Game Over；Time Trial 自動讓寶石掉出、補入新棋盤，保留分數並繼續倒數。R 則是重新開始本局。

## 專案內容

- `llvm/src/`：loader、title、menu screens、遊戲與棋盤邏輯。
- `llvm/tools/build_hdv.py`：建立 ProDOS HDV。
- `assets/prodos-system/`：Cadius 建立 HDV volume 時加入的 ProDOS 與 CLOCK.SYSTEM 系統檔。
- `llvm/tools/cadius.exe`：Windows 隨附的 Cadius；其他平台可使用自行安裝的版本。
- `tools/build_assets.mjs`：從原作素材產生 VERA assets。
- `generated/`：重建 binary 所需的 palette、sprite、tile 和 RLE 輸入檔。
- `AGENTS.md`：架構、記憶體配置、開發流程與容易踩到的問題。

## 目前範圍

滑鼠支援 Title 選項、Options 的 Music／Sound／Back，以及 How to Play 點擊返回。遊戲可點選兩顆相鄰 gem，或按住第一顆拖至相鄰 gem 立即交換；每次拖曳只觸發一次。Show Hint、Reset Game、Exit 亦可點擊，所有頁面使用原作手形游標。Fullscreen 固定 ON。

Title、How to Play、Options、兩種遊戲模式、match／cascade／計分、消除星芒、得分浮字與 Game Over 動畫已移植。gem 落地保留 sprites，不整張重畫棋盤；HUD 只更新變動數字。Title 色盤已重新量化並改善漸層。

Options 下方顯示兩種模式的最高分，回選單時保存至 `HISCORE.DAT`，已做 AppleWin 寫入／重開讀回測試。未回選單就強制關閉，尚未保存的紀錄會丟失；重新建置 HDV 會保留既有有效紀錄。

PCM 現階段為 **原作錄音的移植原型，不是 100% 原作音訊**：16-bit mono、VERA rate 29（11062.622 Hz），原作是 44.1／48 kHz，部分音效是 stereo。五個音效（含截斷為 6640 bytes 的 match1–3）共 26912 bytes，開局全部預載進 VERA VRAM 預載池（27904 bytes），不再使用輔助 RAM；播放只從 VRAM 補 FIFO，零音效磁碟讀取，未新增有損壓縮。只有一條 PCM stream，新音效會中斷舊音效，未實作原作重疊混音，Title／Options 導航聲尚未接入。所有 PSG 聲道供音樂使用；1 MHz 遊戲效能和實際播放仍需試聽，預載並不代表 CPU 不需補 FIFO。disk target 自動執行 `tools/build_sound.mjs`，產生 PCM 和 `llvm/build/*_pcm.wav` 試聽檔，沒有 normalize 或改音高。音訊設定持久化尚未完成。

## WAV → PSG 音樂試作

MIDI 配器研究與新版試作見 [`docs/music-conversion-research.md`](docs/music-conversion-research.md)。`python vera/tools/midi_psg_arrange.py --style clean`／`--style ensemble` 使用使用者提供的 `llvm/build/music_original.mid`；保留來源音高與力度，移除舊 converter 特定曲目用的額外和声／升八度／過長低音拖尾。ensemble 僅按音域推估 Guitar/Bass/Celesta/Marimba 分工，並未恢復原作多樂器分軌。兩版本未接入遊戲，聲道上限／音色／記憶體配置還需要驗證。

`python vera/tools/wav2psg.py`（另需 NumPy）從原作 `media/music.ogg` 離線分析多音高／打擊瞬態，重建 triangle／noise PSG 事件。這是近似轉譜，不是原作錄音的無損轉換；尚未接入遊戲或完成音樂／音效共存的記憶體配置。輸出 `generated/music_trial.psg` 可用 `C:/dev/veramusic/tools/psgplay.exe` 播放；原作 WAV、PSG WAV 預覽及事件流統計放在 `llvm/build/music_*.wav`／`music_psg_report.json`。預覽使用硬體音量、不自動 normalize；noise 為近似渲染，不是 AppleWin 擷取。

## 回歸測試指令

```powershell
python -m pip install py65 numpy
python -u vera\llvm\tools\test_music_vzm.py
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
python -u vera\llvm\tools\test_music.py
python -u vera\llvm\tools\test_mouse.py
python -u vera\llvm\tools\test_vera_detect.py
```

執行實際的 65C02 binaries，使用可追蹤 VRAM 寫入的 VERA／MLI model，涵蓋 slot 2／4、連鎖、局部更新、Hint、時間到／R 與高分讀寫。磁碟是記憶體中的副本，不會寫入測試分數到交付映像。這是補充測試，不能取代 AppleWin 和實機驗證。

`test_music_vzm.py` 不經過 resident loader：它在 model 上直接驅動 Intro 的 FM 偵測、`music_init()` 的檔案選擇（有 FM→`MUSIC.VZM`、無 FM 或檔案不存在→`MUSIC.PSG`）與整份 VZM 解碼，兩個 slot 都逐 tick 比對 PSG 寄存器影像、YM2151 寫入順序、loop 與 stop／OFF 靜音，共 7583 tick byte-exact。它不能證明 FM 晶片的實際聽感。

`test_mos.py` 的 model 現在除了 block 讀寫（`$80`／`$81`）也實作 resident loader 用到的檔案層 MLI（`GET_PREFIX` `$C7`、`OPEN` `$C8`、`READ` `$CA`、`WRITE` `$CB`、`SET_MARK` `$CE`、`GET_EOF` `$D1`、`CLOSE` `$CC`、`QUIT` `$65`），冷開機、Title 與遊戲內路徑都能在 harness 跑完。`test_music.py` 改為播放實際出貨的 raw `MUSIC.PSG` 後備流，逐 frame 比對 7398 frames；`test_sound.py` 改比對四個 VRAM 預載池內的五段 PCM；`test_loading_progress.py` 依磁碟實際檔案計 block。這些仍是 model 測試，不是 AppleWin 或實機驗證。
