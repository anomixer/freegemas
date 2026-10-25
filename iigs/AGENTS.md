# Freegemas Apple IIgs 開發指南

> 本檔是 IIGS 移植的唯一開發與接手指南。只記錄目前有效的架構、約定、建置方式及驗證狀態；不累積逐回合歷史。

## 目前版本

- 正式 IIGS 程式是 `iigs/merlin32/src/main.s`：65816 原生模式組語、Merlin32、GS/OS S16。`iigs/src/` 是早期 stub，不是正式版本。
- 畫面為 320×200 SHR、4bpp，每條 scanline 使用 16 色 palette；不要假設能重現 VERA 256 色或 Windows 原圖的漸層。
- 遊戲資料、音效、音樂與 `HISCORE.DAT` 放在 `/DATA`；磁碟根目錄保留 `FREEGEM.S16`、`README.TXT` 和系統檔案。GS/OS 透過檔案呼叫讀取資產。
- 現有功能含 Title、How to Play、Options、Time Trial、Endless、match/cascade、hint、reset、Game Over、滑鼠點選與相鄰寶石拖曳交換。鍵盤支援 WASD 與方向鍵。
- 寶石採使用者核定的 2D 方塊像素風格。How to Play 使用與遊戲相同的 gem raster/palette。側欄 Show Hint 是發光燈泡，Reset Game 是圓形箭頭；其他場景可見的微小角落像素屬已知外觀，不要特別增加清理程式。

## 目錄與產物

- `iigs/merlin32/src/main.s`：啟動、SHR/blitter、輸入、遊戲規則、HUD、Toolbox/GS/OS 呼叫與音訊。
- `iigs/merlin32/macros/`：Merlin32 `USE` 巨集；`iigs/merlin32/Makefile`：組譯及 disk target。
- `iigs/tools/build_iigs_assets.py`、`shr_art.py`、`committed_art.py`、`hud_art.py`：由來源圖產生 SHR 場景、寶石與側欄。
- `iigs/tools/build_iigs_sounds.py`：由 `media/` 音檔產生 IIGS PCM。
- `iigs/tools/pack_disk.py`、`pack_cadius.py`、`make_startup.py`：建立開機映像與 `/SYSTEM/SetStart.data`。
- `iigs/tools/emu/`：GSSquared 控制、截圖、錄音與檢查工具；指令細節在 `iigs/tools/emu/README.md`。
- `iigs/finder/Finder.Data`、`Finder.Root`：已保存的 Finder 排列；重打映像時由 packer 使用。

## 建置與磁碟映像

在 `iigs/merlin32` 執行：

```powershell
C:\dev\Merlin32.exe macros src/main.s
make disk
```

`make disk` 使用 `../build/gsos-template.2mg`、Cadius 及 `../tools/pack_disk.py`，產生 `build/FREEGEM.S16` 與 `build/freegemas.2mg`。沒有 `make` 時，在同一目錄直接執行：

```powershell
python ../tools/pack_disk.py --template ../build/gsos-template.2mg --image build/freegemas.2mg --volume FREEGEMAS --build build --app FREEGEM.S16 --cadius ../cadius.exe
```

打包後以 `cadius CHECKVOLUME` 和 `CATALOG` 驗證。Cadius 可能失敗但仍回傳 exit 0，需檢查輸出中的 `Error :`。pack_disk 會以暫存 ProDOS 檔名 `NAME#TTAAAA` 設定 type/aux。映像內 `README.TXT` 必須是 GS/OS TXT、CR-only，才能由 Teach 開啟。不要直接修改打包映像或產生資產；修改來源／產生器後重建。

### 工具與本機環境

- Merlin32：`C:\dev\Merlin32.exe` v1.2 beta 2；Makefile 可用 `MERLIN32=` 覆寫。Cadius 1.4.5 隨 repo 存在於 `iigs/cadius.exe`，Makefile 預設 `CADIUS=../cadius.exe`。
- GS/OS template `iigs/build/gsos-template.2mg` 不在版控；新環境需從 `https://github.com/anomixer/Time-Pilot` 的 `TimePilot-IIgs/appleIIgs/gsos-template.2mg` 取得並放入 `iigs/build/`。產生 SHR 圖需 Python 3 + Pillow；產生 PCM 需 ffmpeg 與 `media/` OGG。
- GSSquared 預設執行檔 `C:\dev\emu\gssquared\GSSquared.exe`，profile 為 `%USERPROFILE%\Documents\GSSquared\IIgs.gs2`。這是使用者本機資料，不要覆寫；自動化路徑可用 `FG_GS2`、`FG_GS2CFG`、`FG_IMG`、`FG_WORK` 覆寫。
- GSSquared 自動化工具細節在 `iigs/tools/emu/README.md`。`FG-Init` 會強制停止現有 GSSquared process；先確認沒有使用者重要的遊戲狀態再跑。

## Merlin32 與 65816 注意事項

- Merlin32 的 A/X 寬度由 `SEP`/`REP` 指令決定；`longa on/off` 只影響組譯器追蹤，不會產生執行期指令。分支可跳進不同寬度區塊時，在入口同步 `SEP`/`REP`，避免 8-bit immediate 被編成 16-bit，殘留 `$00` 變成 BRK。
- `SEP`/`REP`、label 與 assembler directive 各自獨立成行。Merlin32 label 和 directive 不要寫在同一行。
- 短分支約限 128 bytes；遠距離使用 `BRL`，必要時用反向條件分支跳過 `BRL`。
- Merlin32 運算式沒有一般運算子優先序，也不支援括號；複合計算拆成具名 `EQU`。
- 16-bit `LDA #label` 只有 offset，沒有 bank byte；需要完整位址時使用 24-bit pointer/directive。
- 改 `main.s` 後，依需求執行 `python ../tools/check_branch_mode.py ...`；加入 `dbgTab` 欄位時，同步更新 `fgemu.ps1` 的表長與 index。

## 畫面與資產約定

- SHR framebuffer 線性別名為 `$012000`，320×200、每列 160 bytes、共 32,000 bytes；每 byte 兩個像素，左像素在 high nibble。SCB 在 `$019D00`、palette 在 `$019E00`。
- 由 `build_iigs_assets.py` 產生場景、寶石和 palette；由 `hud_art.py` 產生側欄。修改生成器，不要只改 `generated/` 或 `build/` 輸出。
- How to Play 的寶石與 palette 必須重用遊戲寶石 raster；改圖後檢查 `generated/preview_howto.png`。保留方塊紅寶石的平面像素風格及使用者核定的配色。
- 一般遊戲動作只重畫受影響的 cell/damage rectangle，不要重畫整個 8×8 棋盤。落下和重置使用逐格動畫；游標、選取框及 hint 更新要清理原區域但避免覆寫新畫面。
- `generated/scene_*.bin` 等是產生物，需由來源重新產生並檢視 preview；Finder icon 由 `tools/build_app_icon.py` 產生，不要手改映像內 icon。

## 遊戲與輸入約定

- 規則、計分與流程以 repo 根目錄原作 C++ 為準。合法交換才消除；每組分數為寶石數 × 5 × cascade 倍率，交叉消除可同時計入兩組。
- Time Trial 為 120 秒；時間到仍完成正在進行的交換與 cascade 再進 Game Over。Endless 無倒數；無合法交換時進 Game Over。Time Trial 無解時重生棋盤但保留分數與剩餘時間。
- Hint 只標示合法移動，不更動選取狀態；合法交換、reset、Game Over 清除提示。Reset 清空本局分數並重設倒數／棋盤。
- WASD 和方向鍵共用移動流程；Space 選取後移到相鄰格再 Space 交換。滑鼠點選與按住拖到相鄰寶石都走相同交換流程。H 提示、R 重置、Esc 離開遊戲或回標題。
- GS/OS Quit 前恢復原有滑鼠、palette、SCB、SHR/文字模式狀態，停止音樂並恢復 DOC interrupt hook；不要遺留遊戲接管的系統狀態。

## Ensoniq DOC 音訊與記憶體

- DOC sample RAM 為 64 KiB；短音效載入 DOC RAM，音效與 BGM 使用獨立 oscillator pairs：select 0/1、fall 2/3、match 4/5、BGM 6/7。
- BGM 使用 oscillator 6 的 DOC end interrupt 切換兩個 4 KiB wave table。`$E1002C` JML callback 只處理切換／狀態；GS/OS 讀檔與 PCM 複製留在 foreground。停止音樂時 drain 並還原原 hook。不要恢復舊的 Misc Tools SetVector 實驗，也不要修改模擬器原始碼。
- `MUSIC.PCM` 為 1,413,400 bytes、約 126.354 秒、mono unsigned 8-bit / 11,186 Hz。遊戲嘗試用一個 locked cross-bank Memory Manager handle 快取整首歌；配置或讀取失敗會退回 GS/OS HD streaming。每面 stream buffer 為 4 KiB，DOC 端使用 ping-pong。
- 完整 RAM cache 約需 1.35 MiB handle，另需 GS/OS、程式及圖形記憶體。README 建議至少 2 MiB、較舒適為 4 MiB 以上；實機最低可用記憶體尚未量測。
- 暫存測試版強制 RAM cache 不可用、實際走 HD streamer，在 GSSquared 8 MB profile 錄音約 160 秒；`musBad=0`、無 clipping，使用者接受此 fallback。這不是低記憶體實機測試。
- GSSquared `.gs2` profile 可選 ROM/platform、cards、storage、display，沒有 IIgs fast-RAM 容量欄位。`platform = "apple2gs"` 是 ROM 01、`apple2gs_rom3` 是 ROM 03；單改 ROM 不能限制 RAM。ROM 01 + 1 MiB expansion 的 1.25 MiB 系統仍需真實可設定 RAM 的模擬器或實機驗證。
- `SDL_AUDIODRIVER=disk` 只將音訊寫入 raw 檔、不會從喇叭播放；聽感需正常音訊輸出，不可用錄音統計代替人耳結論。

## 模擬器驗證

- `fgcheck.ps1` 做開機、Title、Time Trial、交換、音效與回標題 smoke；`fgparitycheck.ps1` 做倒數、cascade、reset/Game Over；`fgmousecheck.ps1` 覆蓋滑鼠與 UI。只在使用者要求測試／驗證或任務需要時執行。
- 讀 debug memory 前必須 Pause，讀完一定 Continue；不可把低速／凍結讀值當成程式狀態。`FINDMEM` 搜 `DE AD BE EF` 定位 `dbgTab`，不要寫死程式 bank。
- GSSquared debug socket 不支援桌面滑鼠注入；滑鼠手感需在 web GSSquared 或實機操作確認。模擬器結果與實機結果分開記錄。

## 驗證狀態與限制

- 使用者在 GSplus 完成一整局，回報現行 audio IRQ 版音樂沒有跳針，包括遊戲中播放音效時。此結果只代表該次模擬器遊玩。
- 仍待真機或可設定 RAM 的模擬器驗證：低記憶體配置、實際 DOC 音質／長時間播放、ADB 滑鼠手感、軟碟串流，以及安裝現行 DOC callback 後的 Exit。不可把模擬器結果寫成實機結果。
- 開機時約 40 ms 的音訊突波也會在完全移除遊戲 DOC 呼叫的診斷版出現，來源尚未確定；不要將它歸因於現行 BGM streamer。
- 保持本文 UTF-8、LF 且**不得超過 65,536 bytes**。只保留有效的現況與可重現流程；狀態改變時更新 README，刪除過期矛盾描述。