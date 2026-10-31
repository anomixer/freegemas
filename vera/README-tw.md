# Freegemas for Apple //e VERA

[English](README.md) | 繁體中文

這是 Freegemas 的 Apple //e VERA 移植版。遊戲以 LLVM-MOS C 編譯為 65C02 程式，使用 VERA 320×240、8bpp bitmap、常駐 gem sprites 與頂部遮罩繪圖，透過 ProDOS HDV 分段載入標題、遊戲和說明／設定畫面。

目前可直接測試的磁碟映像是 [`freegemas.hdv`](freegemas.hdv)，容量 2048 KB。

## 建置

需要 Node.js、Python（NumPy）、ffmpeg／ffprobe、CMake、LLVM-MOS SDK 與 Cadius。Windows 使用隨附的 `llvm/tools/cadius.exe`；其他平台需將 Cadius 放入 `PATH`，或以 `-DCADIUS_EXECUTABLE=/path/to/cadius` 指定。ProDOS 系統檔位於 `assets/prodos-system/`，不依賴 time-pilot checkout。

在 repo 根目錄執行：

```powershell
node vera\tools\build_assets.mjs
cmake -S vera\llvm -B vera\llvm\build
cmake --build vera\llvm\build --target disk --parallel 4
```

`build_assets.mjs` 從 repo 的 `media/` 產生 indexed bitmap、sprites、palette 與 RLE 場景。CMake 會建立 slot 2／slot 4 的遊戲 binary，`build_hdv.py` 再將它們和場景檔打包成 `vera/freegemas.hdv`。

目前工具鏈預設位於 `C:\dev\llvm-mos-sdk\install`；其他安裝位置可用 CMake 的 `-DLLVM_MOS_SDK=...` 指定。HDV builder 使用 Cadius 建立新的 2048 KB ProDOS volume，再加入系統檔與遊戲檔案，不再依賴 HDV 範本。

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

Sound 使用原作 `select.ogg`、`fall.ogg`、`match1–3.ogg`，以 signed 8-bit mono VERA PCM、rate 21（8010.86 Hz）與原作增益轉換，五份合計 9740 bytes，全部預載到 VERA VRAM `$14800` 之後，播放零磁碟讀取、不佔輔助 RAM。

VERA 只有一個 PCM FIFO，音樂與音效共用，因此遊戲以軟體混音：建置時把音樂峰值正規化到約 ±61、音效限在 ±37，signed 8-bit 相加不會溢位。音樂維持在半滿刻度以下，也避免 VERA 的 (PSG + PCM) 加倍混音器在峰值時 clamp——先前把音樂推到 0.70 全刻度時，那種顆粒雜音就是這裡削出來的。音效 staging 透過 port 0 讀 VRAM，並還原兩個位址 port 與 control，混音不會破壞繪圖狀態。新音效會取代舊音效，但永遠疊在音樂之上。

音樂在每一台 VERA 機器上都改成整首串流 PCM（IIgs 方式）：`MUSIC.PCM` 為 1012224 bytes（1977 個 ProDOS block、126.35 秒）。`tools/build_music_pcm.py` 以 ffmpeg 產生（linear-interp 重採樣到 8011 Hz、衰減到約 0.48 全刻度、40-sample fade）；原始音軌本身已接近全刻度，再加 6 dB 只會讓 limiter 削波。0.70 limiter 現在只是保險上限，不會被觸發。遊戲以 1KB ring buffer 從磁碟串流，FIFO 維持約 1024 bytes，每 VSYNC 補 133／134 samples。每次 loop 只做一次 SET_MARK，之後連續 MLI READ 最多 1KB；短讀取退回 512-byte 讀取。整首循環播放。

YM2151 probe 現在只供顯示：Intro 會印 `FM: YM2151 DETECTED (OPM)` 或 `FM: NONE`，但播放方式完全相同。已沒有 FM／PSG 音樂路徑，磁碟上也沒有 `MUSIC.VZM`、`MUSIC.PSG`，不再預載到輔助 RAM；HDV 容量 2048 KB。

Sound／Music 互不連動；音樂只在遊戲畫面播放，R 從頭重播，Esc 會靜音、關閉檔案並把磁碟交回 loader。

`LOADING GAME...` 在遊戲程式載入後會顯示 186 個資產 block 的進度條、百分比與階段；棋盤準備完成才到 100%，下方顯示 `GAME START`。遊戲 binary 本身載入期間仍是原本文字提示；`MUSIC.PCM` 不列入這個進度條，它是在遊戲中邊玩邊從磁碟串流。

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

PCM 現階段為 **原作錄音的移植原型，不是 100% 原作音訊**：signed 8-bit mono、VERA rate 21（8010.86 Hz），原作是 44.1／48 kHz，部分音效是 stereo。五個音效共 9740 bytes，開局全部預載進 VERA VRAM `$14800` 之後，不再使用輔助 RAM；播放只從 VRAM 補 FIFO，零音效磁碟讀取，未新增有損壓縮。音樂與音效共用同一條 PCM FIFO，以軟體相加混音；新音效會中斷舊音效，Title／Options 導航聲尚未接入。1 MHz CPU 仍須每 VSYNC 補 FIFO，預載不等於 CPU 不需工作；實際聽感仍需試聽。disk target 自動執行 `tools/build_sound.mjs` 與 `tools/build_music_pcm.py`，產生 PCM 和 `llvm/build/*.wav` 試聽檔。音訊設定目前只在同一次執行期間保留。

## 音樂轉換研究

`tools/build_music_pcm.py` 與 `tools/build_sound.mjs` 是目前唯二的音訊轉換器。早期 WAV→PSG、MIDI 配器與 YM2151 實驗（含當時的檔名）記錄在 [`docs/music-conversion-research.md`](docs/music-conversion-research.md)；那些工具與 `MUSIC.PSG`／`MUSIC.VZM` 已不在 repo 中。試聽與分析輸出放在 `llvm/build/`。

## 回歸測試指令

```powershell
python -m pip install py65 numpy
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
python -u vera\llvm\tools\test_music.py
python -u vera\llvm\tools\test_pcm_clock.py
python -u vera\llvm\tools\test_mouse.py
python -u vera\llvm\tools\test_vera_detect.py
```

執行實際的 65C02 binaries，使用可追蹤 VRAM 寫入的 VERA／MLI model，涵蓋 slot 2／4、連鎖、局部更新、Hint、時間到／R 與高分讀寫。磁碟是記憶體中的副本，不會寫入測試分數到交付映像。這是補充測試，不能取代 AppleWin 和實機驗證。

`test_music.py` 在兩個 slot 逐 byte 串流完整的 1012224 bytes `MUSIC.PCM`，並驗證磁碟讀取、loop 點、OFF／ON、音效逐 sample 混音、R 重播與 Esc 靜音。`test_sound.py` 驗證五個音效在 VRAM 的實際位址與 byte、OFF／ON、替換、自然播完、port 保留，以及播放音效不會重新開啟檔案。`test_pcm_clock.py` 依 CPU cycle 以 8010.86 Hz 消耗 FIFO，比對實際渲染串流與來源 PCM，包含 230 ms 饑餓缺口與音效混音區間。

`test_mos.py` 的 model 現在除了 block 讀寫（`$80`／`$81`）也實作 resident loader 用到的檔案層 MLI（`GET_PREFIX` `$C7`、`OPEN` `$C8`、`READ` `$CA`、`WRITE` `$CB`、`SET_MARK` `$CE`、`GET_EOF` `$D1`、`CLOSE` `$CC`、`QUIT` `$65`），冷開機、Title 與遊戲內路徑都能在 harness 跑完。`test_loading_progress.py` 依磁碟實際檔案計出 186 個資產 block。這些仍是 model 測試，不是 AppleWin 或實機驗證。
