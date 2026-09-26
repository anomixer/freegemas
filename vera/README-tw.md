# Freegemas for Apple II + VERA

[English](README.md) | 繁體中文

這是 Freegemas 的 Apple IIe／VERA 移植版。遊戲以 LLVM-MOS C 編譯為 65C02 程式，使用 VERA 320×240、8bpp bitmap、常駐 gem sprites 與頂部遮罩繪圖，透過 ProDOS HDV 分段載入標題、遊戲和說明／設定畫面。

目前可直接測試的磁碟映像是 [`freegemas.hdv`](freegemas.hdv)，容量 800 KB。

## 建置

需要 Node.js、Python（NumPy）、ffmpeg／ffprobe、CMake、LLVM-MOS SDK。ProDOS 基底映像已附於 `assets/800kb.hdv`，不依賴 time-pilot checkout。

在 repo 根目錄執行：

```powershell
node vera\tools\build_assets.mjs
cmake -S vera\llvm -B vera\llvm\build
cmake --build vera\llvm\build --target disk --parallel 4
```

`build_assets.mjs` 從 repo 的 `media/` 產生 indexed bitmap、sprites、palette 與 RLE 場景。CMake 會建立 slot 2／slot 4 的遊戲 binary，`build_hdv.py` 再將它們和場景檔打包成 `vera/freegemas.hdv`。

目前工具鏈預設位於 `C:\dev\llvm-mos-sdk\install`；其他安裝位置可用 CMake 的 `-DLLVM_MOS_SDK=...` 指定。HDV builder 依腳本位置解析 repo 內的模板路徑，不需修改。

AppleWin 範例：

```powershell
AppleWin.exe -s2 vera -s7 hdc -h1 C:\dev\freegemas\vera\freegemas.hdv
```

AppleWin 若正掛載映像，重建前先關閉模擬器，避免 HDV 被鎖住。

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

遊戲背景音樂採使用者選定的純音平滑版：無 bass／鼓模擬／額外泛音，使用 PSG triangle，原生 PSG 音量提高約9dB（較第一個遊戲音樂版再提高約3dB；超出單聲道音量上限時封頂）。來源為 `generated/music_midi_pure_smooth.psg`，`tools/build_music.py` 無損打包成 `music.fgm`（9014 bytes 音符事件）及 `music_curves.bin`（9167 bytes 共用音量曲線），7398 frames、約123.3秒循環。開局前全部預載到主／輔助 RAM，播放時不讀音樂磁碟；PSG 與 PCM 音效分開，R 重播、Esc 靜音返回 Title。音樂目前只在遊戲畫面播放，Title／Options 不播放。需要128KB Apple IIe；沒有輔助 RAM 時安全停用音樂與音效。

核准的 `music_pure_player_linear_listen_louder.wav` 是線性軟體播放預覽；VERA 的6-bit波形、音量量化與輸出增益不同，遊戲不是串流此 WAV，不能聲稱實機聽感／響度完全相同。遊戲採相同純音音符、平滑包絡與相對來源 PSG 約+9dB，需 AppleWin／實機試聽確認。

音效不跨 VRAM／aux 邊界：match2 完整放 aux `$2C00–$757B`，match3 放 `$757C–$BFBF`；VRAM 尾端56 bytes 留空。硬體 PCM FIFO 固定4KB，起播已填滿，不能由遊戲調大；現有取樣格式約可緩衝185ms。

match1／2／3 現在都只播前約0.30秒（6640 bytes），切掉長尾音；原始素材與預載配置保留。FIFO 播完後明確靜音、停採樣並清空，不保留最後樣本。select／fall 與音樂未變；三份 match 音效不再是完整原作錄音播放。

`LOADING GAME...` 在遊戲程式載入後會顯示20格進度條、百分比及目前資產階段；依實際 data blocks 更新，棋盤準備完成才到100%。遊戲 binary 本身載入期間仍是原本文字提示，進度條涵蓋寶石／場景／音樂／音效預載，不會加入額外等待。

FIFO 見底時會先停止採樣，再恢復16-bit樣本對齊並預填 FIFO 後恢復播放：AppleWin 會丟棄尾端孤立的1 byte，補資料前須重送該樣本的 low byte，且不能在補完 high byte 前繼續採樣。此路徑有 match2／3 強制 underrun 回歸，以及 `test_pcm_clock.py` 按CPU時間實際消耗FIFO的渲染樣本比對；長運算造成的缺音與實際聽感仍需另行驗證。

無合法交換時依原作規則：Endless 結束並顯示 Game Over；Time Trial 自動讓寶石掉出、補入新棋盤，保留分數並繼續倒數。R 則是重新開始本局。

## 專案內容

- `llvm/src/`：loader、title、menu screens、遊戲與棋盤邏輯。
- `llvm/tools/build_hdv.py`：建立 ProDOS HDV。
- `assets/800kb.hdv`：隨 repo 附帶的 800 KB ProDOS 開機模板（含 Bitsy Bye），原始副本來自 TimePilot-IIvera；建置不需要 time-pilot repo。
- `tools/build_assets.mjs`：從原作素材產生 VERA assets。
- `generated/`：重建 binary 所需的 palette、sprite、tile 和 RLE 輸入檔。
- `AGENTS.md`：架構、記憶體配置、開發流程與容易踩到的問題。

## 目前範圍

滑鼠支援 Title 選項、Options 的 Music／Sound／Back，以及 How to Play 點擊返回。遊戲可點選兩顆相鄰 gem，或按住第一顆拖至相鄰 gem 立即交換；每次拖曳只觸發一次。Show Hint、Reset Game、Exit 亦可點擊，所有頁面使用原作手形游標。Fullscreen 固定 ON。

Title、How to Play、Options、兩種遊戲模式、match／cascade／計分、消除星芒、得分浮字與 Game Over 動畫已移植。gem 落地保留 sprites，不整張重畫棋盤；HUD 只更新變動數字。Title 色盤已重新量化並改善漸層。

Options 下方顯示兩種模式的最高分，回選單時保存至 `HISCORE.DAT`，已做 AppleWin 寫入／重開讀回測試。未回選單就強制關閉，尚未保存的紀錄會丟失；重新建置 HDV 會保留既有有效紀錄。

PCM 現階段為 **原作錄音的移植原型，不是 100% 原作音訊**：16-bit mono、VERA rate 29（11062.622 Hz），原作是 44.1／48 kHz，部分音效是 stereo。五個音效共65672 bytes，開局全部預載：27848 bytes 放 VERA VRAM，其餘37824 bytes 放輔助 RAM（VRAM 池27904 bytes，尾端56 bytes 留空避免音效跨區）；播放只從記憶體補 FIFO，零音效磁碟讀取，未新增有損壓縮。只有一條 PCM stream，新音效會中斷舊音效，未實作原作重疊混音，Title／Options 導航聲尚未接入。所有 PSG 聲道供音樂使用；1 MHz 遊戲效能和實際播放仍需試聽，預載並不代表 CPU 不需補 FIFO。disk target 自動執行 `tools/build_sound.mjs`，產生 PCM 和 `llvm/build/*_pcm.wav` 試聽檔，沒有 normalize 或改音高。音訊設定持久化尚未完成。

## WAV → PSG 音樂試作

MIDI 配器研究與新版試作見 [`docs/music-conversion-research.md`](docs/music-conversion-research.md)。`python vera/tools/midi_psg_arrange.py --style clean`／`--style ensemble` 使用使用者提供的 `llvm/build/music_original.mid`；保留來源音高與力度，移除舊 converter 特定曲目用的額外和声／升八度／過長低音拖尾。ensemble 僅按音域推估 Guitar/Bass/Celesta/Marimba 分工，並未恢復原作多樂器分軌。兩版本未接入遊戲，聲道上限／音色／記憶體配置還需要驗證。

`python vera/tools/wav2psg.py`（另需 NumPy）從原作 `media/music.ogg` 離線分析多音高／打擊瞬態，重建 triangle／noise PSG 事件。這是近似轉譜，不是原作錄音的無損轉換；尚未接入遊戲或完成音樂／音效共存的記憶體配置。輸出 `generated/music_trial.psg` 可用 `C:/dev/veramusic/tools/psgplay.exe` 播放；原作 WAV、PSG WAV 預覽及事件流統計放在 `llvm/build/music_*.wav`／`music_psg_report.json`。預覽使用硬體音量、不自動 normalize；noise 為近似渲染，不是 AppleWin 擷取。

## 回歸測試指令

```powershell
python -m pip install py65 numpy
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
python -u vera\llvm\tools\test_music.py
python -u vera\llvm\tools\test_mouse.py
python -u vera\llvm\tools\test_vera_detect.py
```

執行實際的 65C02 binaries，使用可追蹤 VRAM 寫入的 VERA／MLI model，涵蓋 slot 2／4、連鎖、局部更新、Hint、時間到／R 與高分讀寫。磁碟是記憶體中的副本，不會寫入測試分數到交付映像。這是補充測試，不能取代 AppleWin 和實機驗證。
