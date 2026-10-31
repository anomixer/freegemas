# 開發指南：Apple //e VERA 版 Freegemas

## 主線與原則

- 目前可執行版本是 `vera/llvm/` 下的 LLVM-MOS／C 移植，開機系統是 ProDOS `FREEGEM.SYSTEM`。主要遊戲 binary 載入 `$3000`。
- 舊 6502 組語原型與舊 `.po` 建置流程已移出 repo 備份，不再維護；新功能只修改 `vera/llvm/` 主線。
- 遊戲規則與分數應以 repo 根目錄的原作 C++ 實作為依據；畫面與互動以 `1.png`–`5.png` 等參考圖及 `media/` 原始素材比對。
- VERA sprite／register 行為以 `C:\dev\applewin\VERA.md`、`C:\dev\veratest\docs\vera-session.md` 和 `C:\dev\veratest\AGENTS.md` 為開發參考。AppleWin 版本的實作細節可能和 Commander X16 文件不同，先確認目前模擬器實際支援的格式。
- 棋盤 bitmap 維持原樣，64 顆 gem 常駐 hardware sprites；移動只更新受影響的 sprite 屬性。游標、浮字與星芒也使用 sprites。HUD 只改變動的數字，不要在一般棋步中整張重畫。
- 大型場景採 ProDOS 分段載入和 RLE 串流；不要為了省一個資產把整張畫面塞進 `$3000` 程式。

## 目錄與載入流程

- `llvm/src/loader.c`、`loader.s`：常駐的 ProDOS SYS loader，位於 `$2000`；依 page 3 的請求碼載入不同 binary，也負責將 RLE 場景串流至 VERA。
- `llvm/src/title.c`：Title、模式選擇與子頁面入口。
- `llvm/src/menu_screen.c`：How to Play 和 Options 的小型控制程式，透過 `OPTIONS_SCREEN` 編譯選項產生兩種版本。
- `llvm/src/main.c`、`board.c`、`board.h`：遊戲、棋盤、計分、動畫與畫面更新。
- `llvm/src/effects.c`／`effects.h`：游標、選取框、消除星芒和每組 match 得分浮字。限 4 組同時浮字、32 顆星芒；超量以 ring pool 取代最舊特效，不影響實際計分。
- `llvm/src/sound.c`／`sound.h`／`pcm_feed.S`：五個原作 PCM 音效（signed 8-bit mono、8010.86 Hz，`build_sound.mjs` 產生，總計 9740 bytes）完整預載到 VERA VRAM `$14800` 之後；播放不讀磁碟、不占 Aux RAM，也不動 PSG。`pcm_copy`／`pcm_mix` 以 `$FF00,Y` 加修補高位元處理跨頁讀取；`pcm_effect` 由 C 端提供，不要在組語重複宣告同名 `.bss` 符號（曾因此讓混音讀到 page 0）。
- `llvm/src/music.c`／`music.h`：整首 `MUSIC.PCM`（signed 8-bit、8010.86 Hz、1012224 bytes／1977 blocks）在遊戲中從磁碟串流，沒有 FM／PSG／VZM 路徑。`music_tick` 以 1KB ring buffer 維持 FIFO 約 1024 bytes 深度、每 VSYNC 補 133／134 samples；`feed()` 回傳實際送入的 samples，`music_tick` 再以它當**實時時鐘**（`music_frames_elapsed()` 以 `133514`＝8010.86 Hz÷60 的千分位累加，Time Trial 的 `timer_frame` 改加 ticks，沒有串流時退回一 frame 一 tick）。frame 超過 VSYNC 時 `waitvsync` 立即返回，只補 133／134 跟不上硬體連續消耗，所以 `music_tick` 之後進 top-up 迴圈：只要 ISR bit 3（`VERA_IRQ_AUDIO_LOW`，FIFO < 1024）仍為真就清 bit 3 再補 `MUSIC_CATCHUP` 128 samples，直到佇列回到目標深度或來源耗盡；`frame_pump()`（`frame_pump.h`）讓長 CPU 迴圈（`board_find_solution` 每列、`board_generate` 每輪）在 VSYNC latch 已設時就地付掉 `effects_tick`／`music_tick`，掃描期間不會把 FIFO 抽乾（timer 仍只由主迴圈推進，避免重入 Game Over）；每次 loop 只做一次 SET_MARK，之後連續 MLI READ 最多 1KB，短讀取退回 `disk_read`（512 bytes＋SET_MARK）。`feed()` 在入口保存 VERA 的 control／address／address_hi，並**先還原 control** 再還原位址，否則音效 staging 留在 port 0 會把位址寫錯 port。`sound_play` 只設定 effects（`effect_source`／`effect_remaining`），音樂與音效在 `pcm_mix` 相加（音樂峰值 ±61、音效 ±37，signed 相加不溢位；音樂也維持在半刻度以下，避免網頁版 apple2ts 的 `(PSG + PCM)` ×2 混音器在峰值 clamp；AppleWin 是直接相加後 clamp int16，只有超過 127 才削波）。`music_init` 先驗證檔案大小，`sound_init` 再載入音效；兩者都會開檔，`disk_epoch()` 讓音樂在 epoch 改變時重新開啟 `MUSIC.PCM`。`fm_detect()` 只用於 Intro 顯示（`FM: YM2151 DETECTED (OPM)`／`FM: NONE`），播放方式與晶片無關。
- `llvm/src/hiscore.h`：跨 segment 的兩模式高分與 dirty flag。
- `tools/build_assets.mjs`：以 `media/` 建立遊戲／標題 palette、RLE 場景和 sprites。
- `llvm/tools/build_hdv.py`：把程式與 RLE 場景打包至 2048 KB ProDOS HDV，並建立跨 directory block 的檔案目錄。
- `llvm/src/loader.c`、`main.c`、`sound.c`、`music.c`：ProDOS 檔案層級載入；以 GET_PREFIX 組合遊戲目錄路徑，再透過 OPEN／GET_EOF／SET_MARK／READ／WRITE 存取檔案，不依賴原映像的 block 配置。`FREEGEMAS` 是遊戲目錄 marker，HDV volume name 也固定為 `FREEGEMAS`。
- ProDOS `OPEN` 使用獨立、256-byte 對齊的 `$B800` I/O buffer；payload READ 使用 `$0C00` staging buffer。不要讓檔案資料覆蓋 ProDOS I/O buffer。返回 resident loader 前需關閉遊戲最後開啟的檔案，避免 loader 重用 I/O buffer 時失敗。
- HDV builder 使用 Cadius 建立全新的 `FREEGEMAS` 2048 KB ProDOS volume，並加入 `assets/prodos-system/` 中的 `PRODOS` 與 `CLOCK.SYSTEM`。遊戲檔案由 packager 配置 block，執行時依 ProDOS 檔名讀取，不依賴 HDV 固定 block。
- 新產生的普通檔案目錄項目寫入本機 ProDOS 建置日期與時間（含 Y2K year encoding）；保留 Cadius 建立的 volume header 與系統檔 metadata。Windows 使用 `llvm/tools/cadius.exe`；其他平台需將 Cadius 放入 `PATH` 或設定 `CADIUS_EXECUTABLE`。
- `generated/`：CMake 和 HDV builder 的輸入素材。不要只修改輸出 `.bin`／`.hdv`；先修正來源，再重新產生。
- `generated/` 不保留未採用的 MIDI／PSG 比較輸出；音樂研究文件中的歷史檔名是過往產物記錄，不代表目前仍存在或屬於建置依賴。

## 建置和交付

從 repo 根目錄執行：

```powershell
node vera\tools\build_assets.mjs
cmake -S vera\llvm -B vera\llvm\build
cmake --build vera\llvm\build --target disk --parallel 4
```

資產腳本需要 `ffmpeg` 和 `ffprobe`。LLVM-MOS SDK 預設在 `C:\dev\llvm-mos-sdk\install`；CMake cache 可用 `-DLLVM_MOS_SDK=...` 指定其他位置。HDV builder 使用 Cadius 建立新 volume，不再依賴 `800kb.hdv` 模板；ProDOS 和 CLOCK.SYSTEM 來源位於 `vera/assets/prodos-system/`。

產物：

- `llvm/build/freegemas.bin`／`freegemas4.bin`：slot 2／slot 4 遊戲程式。
- `llvm/build/title.bin`／`title4.bin`、`howto.bin`／`howto4.bin`、`option.bin`／`option4.bin`：各頁面程式。
- `freegemas.hdv`：可開機的 2048 KB 測試映像。
- File-level 安裝時，將 HDV 所有檔案複製到目標 ProDOS volume／目錄，唯獨排除 `PRODOS`；保留 `FREEGEMAS` marker，將 ProDOS prefix 指向該目錄後執行 `FREEGEM.SYSTEM`。
- 舊版範本 HDV 已用 AppleWin 驗證開機、進入遊戲與返回 Title；檔案層級複製到 VeraSD 也已確認可執行且 `HISCORE.DAT` 可持久寫入。Cadius 新建的 HDV 已建置並檢查 ProDOS catalog，尚待重新驗證開機。模擬器結果不取代 Apple II 實機驗證。

AppleWin 重新建置前先卸載或關閉正在使用該 HDV 的模擬器。確認載入提示、slot 2 和 slot 4 路徑、模式切換及遊戲畫面後，再交付映像；不要只根據編譯成功宣稱實機驗證完成。

## VERA 顯示與 VRAM 配置

目前以 320×240、8bpp bitmap 顯示。Title 使用 DC_VIDEO `$51`；遊戲使用 `$71`（L0 + L1 + sprites）。L1 透明 tilemap 只在最上方 16px 覆蓋原 bitmap，防止補牌露出棋盤頂框。gem z-depth=2，游標／浮字／星芒 z-depth=3；sprite 8bpp 選項設在 attribute byte 1 的 bit 7。

| VRAM 範圍 | 用途 |
|---|---|
| `$00000–$12BFF` | 320×240 8bpp bitmap |
| `$12C00–$147FF` | 7 個 32×32 8bpp gem sprite patterns |
| `$14800–$18FFF` | PCM 音效池：五個 8-bit 音效共 9740 bytes 連續放在 `$14800`（結尾 `$16AEB`），其餘保留 |
| `$19000–$197FF` | 游標／選取框 32×32 patterns |
| `$19800–$198FF` | 4 張 8×8 星芒 patterns |
| `$19900–$1A2FF` | 10 個 16×16 浮字數字 patterns |
| `$1A300–$1A7FF` | 空閒（原 PCM 預載池） |
| `$1A800–$1B7FF` | L1 64×32 tilemap，僅前兩列不透明 |
| `$1B800–$1CC3F` | 透明 tile 0 + 80 個頂部背景 tiles |
| `$1CC40–$1D83F` | 3 個 32×32 綠色 hint 框 patterns |
| `$1D840–$1F03F` | 空閒（原 PCM 預載池） |
| `$1F040–$1F0BF` | 原作手形滑鼠游標，16×16／4bpp（128 bytes） |
| `$1F100–$1F8FF` | 空閒（原 PCM 預載池）；HUD 背景已移主 RAM |
| `$1F9C0–$1F9FF` | VERA PSG registers（16 聲道；目前音樂與音效都走 PCM，未使用） |
| `$1FA00–$1FBFF` | 256 色、RGB444 palette |
| `$1FC00–$1FFFF` | 128 個 sprite attributes，每個 8 bytes |

棋盤 gem 的 24px 圖像置於 32px sprite 中央，以 26px 棋盤 pitch 放置。slot 0–63 是 gem，64 是手形滑鼠游標，65 是 hint，66／67 是棋盤游標與白色選取角框，68–87 是浮字數字，88–119 是星芒。hand 與 hint 必須排在其他 overlays 前：32px 高 gem／26px pitch 使相鄰兩列 sprite 重疊，每條掃描線的 800 clocks 預算可能截斷晚順位提示框。掉落只改會移動的 gem，落地保留 sprites，不再 commit 成 bitmap。Gem 圖像縮小使用 area filter，sprite 的原圖 alpha <128 或黑 matte 轉透明；hand 則保留原作黑色外框，使用既有白色／黑色 palette inks，不改場景色盤。

## 遊戲流程約定

- 開機先載入獨立 `INTRO.BIN`／`INTRO4.BIN`（文字頁，參考 Time Pilot loader），顯示 ANOMIXER 2026、repo 網址、slot 與操作鍵。任意鍵或 300 VSYNC 後進 Title；一般返回 Title 不重播。冷 RAM 的請求碼不假設為零；ProDOS QUIT 後清初始化旗標，重新啟動會再顯示說明。`test_intro.py` 涵蓋兩 slot、非零冷 RAM、逾時與按鍵跳過。resident loader BSS 現在約 `$2FD1`，只剩 47 bytes，新增大功能應放獨立 segment。
- Title 的 EXIT 送出 `$A8` 請求至 resident loader：保存 pending high scores、關閉 VERA，切回 40 欄文字並透過 MLI `$65` QUIT 回到磁碟內的 Bitsy Bye。`test_quit.py` 驗證兩 slot 的 Title 選單輸入、退出前存檔及 QUIT 參數；AppleWin 確認 Bitsy Bye 檔案選單。Game 的 Esc／EXIT 仍先返回 Title。
- Time Trial 初始兩分鐘，以 VSYNC 計時；Endless 不顯示時間面板。
- 合法交換後才開始消除。分數依原作每組 match 計算 `gem 數 × 5 × cascade 倍率`；交叉位置可以屬於兩個 match group。
- 已開始的合法回合即使時間到，也要先完成交換、消除、掉落與所有連鎖，再執行 Game Over 掉落動畫。
- 完成全部 cascade 後，無合法交換依原作分模式處理：Endless 執行 Game Over 並結算高分；Time Trial 讓整盤寶石掉出、重新生成有效棋盤並從上方補入，保留分數與正在倒數的時間。此自動換盤不同於 R（R 重新開始並清分／重置時間）。換盤動畫若時間到，延後至動畫結束再結算。`test_no_moves.py` 驗證兩 slot、兩模式、Endless 高分保存、換盤不重畫 bitmap 與途中逾時。
- 無解判定在棋步及所有連鎖結束後立即執行；主循環也每 30 個 VSYNC 檢查穩定棋盤，不依賴 H 或待檢查旗標。交換合法性以虛擬交換檢查兩個端點，不改動 live board。`test_no_moves.py` 包含使用者 `nomove.png` 的完整棋盤，先完成開局檢查再置入無解盤；不注入排程旗標、不按鍵、不直接呼叫判定函式，等待自動 Game Over，驗證寶石隱藏、高分、唯一一次結束及 Time Trial 補牌後 sprite 對齊。此驗證是 65C02／VERA model，不能稱為 AppleWin 或實機驗證。
- 開局不再固定使用 `0xBEEF`；Title 輪詢次數累積玩家操作時機到 page 3 `$03EA–$03EB`，作為新局 seed，生成棋盤後保存 RNG 狀態。R 繼續同一亂數序列；保留無初始 match、至少一個合法交換的生成檢查。`test_random.py` 驗證兩 slot 不同選單停留時間產生不同有效棋盤；`test_mos.py` 只在測試 fixture 注入固定 seed，以重現既有連鎖案例。
- 初版 seed 修正只在 Title idle loop 累積，動畫途中先按 Space 會排隊，導致第一次開局仍可得到固定 seed=1。現在 `random_poll()` 在 Intro 與 Title 動畫等待期間也偵測按鍵上升緣，把輪詢時機混入 seed；不能只累積固定動畫 frame 數。兩 slot 回歸加入動畫第 2／10／30 frame 提早開始；AppleWin slot 4 兩次獨立啟動擷取的 seed 為 `$001A`／`$CD40`，64 格棋盤資料不同。
- `H` 使用提示後，該回合初始 match 不計分，依原作規則處理後續 cascade。
- Hint 依 `src/GameHint.cpp` 使用獨立綠色框（sprite 64）標出第一個解的寶石，40 ticks 內分段放大後消失；不改變 cursor／已選取寶石。綠色從既有 palette 選取，不改色盤。合法交換、R、Game Over 清除提示框；游標移動不移動提示框。CPU regression 驗證三段圖樣的完整四邊、實際 sprite 配置在各掃描線的預算、位置、保留選取狀態、逾時與棋盤零重畫。
- Options 的 Sound 控制原作 PCM 音效，page3 `$03F3` 為 ON／OFF；Music `$03F2` 控制整首串流 PCM 音樂（`MUSIC.PCM`，rate 21／8010.86 Hz），Fullscreen 固定 ON。Sound／Music 互不連動，Esc 回 Title 前同時靜音、關檔；R 從頭重播音樂。兩者共用一條 PCM FIFO，軟體混音；PSG 已不再使用。

## 除錯注意事項

- VERA bitmap 是 76,800 bytes，會跨 `$10000` bank；地址設定需保留 20-bit VRAM 位址，不能只用 16-bit offset。
- AppleWin 的 VERA sprite pattern 編址以 32-byte 單位，attribute byte 中的色深、palette、z-depth 和尺寸欄位需依 `apple2e.h`／AppleWin session 文件解讀。
- ProDOS MLI 會使用 zero page。`mli.s` 讀／寫 block 都保存並恢復 `$00–$BF`，防止 compiler registers／狀態被破壞。trampoline 的最後一次 MLI 後直接重設 hardware SP=`$FF` 再進入 segment，避免每次切頁累積永不返回的 return addresses。
- `link2000.ld` 限定 resident loader 的 code/data/BSS 全在 `$2000–$2FFF`；遊戲 `$3000` 段不能覆蓋它。目前 loader BSS 結束於約 `$2ED1`，修改時留意 linker 上限。
- Loader 轉頁時先關閉 VERA output，再顯示文字模式 loading 訊息；場景和 palette 設定完成後才開啟 bitmap。這可避免舊 palette 顯示新場景造成跑色。
- 場景通常是 `(count, palette_index)` RLE byte pairs。若 RLE 比 raw 更大，generator 改用 `$00,$00` 前綴加 76,800 bytes 原始 indexed pixels；loader 以 6502 block copier 串流。目錄 EOF 使用 ProDOS 24-bit 長度，不能截成 uint16。場景需正好展開 320×240，sapling 上限 256 blocks；CPU 測試會涵蓋 raw 場景跨 64KB 的載入。
- Options 設定目前存於 page 3，只在一次執行期間保留，未寫入 ProDOS 檔案。
- High score 分模式存於 page 3 `$03E0–$03E7`，dirty／初始化標記在 `$03E8–$03E9`。回 loader 時保存單一 block 的 `HISCORE.DAT`：`FGH` + version 1 + 兩個 little-endian uint32（共 12 bytes）。失敗不清 dirty，之後切頁再試。Options 下方兩行 `TIMETRIAL:`／`ENDLESS  :` 不列入游標選項。未回選單就強制關閉，尚未落盤的紀錄會丟失；builder 會按名稱從既有映像取出有效紀錄，重新建置不再清零。
- Title／子頁面色盤使用加權 median cut + RGB444 refinement，保留 index 255 白色；背景使用誤差擴散減少漸層色帶。不要在 runtime 借用或改寫背景 palette slot 畫指標。
- 遊戲左側 HUD 背景改用 `media/stateMainMenu/mainMenuBackground.png`，消除 Time Left 下方原 board.png 亮色斑塊；y<36 保留原 Logo，y=36–51 漸變銜接，x>=88 棋盤保持原素材。純背景採誤差擴散改善 RGB444 色帶，HUD／按鈕保留清晰像素邊緣。Time Trial 與 Endless 共用此底圖；Endless 隱藏時間區時也須取自新底圖。
- 棋盤色澤參照 `6.png`：UI palette 21–46 使用 26 個棕色代表色，47–63 使用 17 個藍色／暗色代表色。加權 median cut 保留原 RGB 到最後才四捨五入成 RGB444；重複中心以尚未涵蓋的來源色補足。棋盤可共用 gem 的暖色陰影，漸層誤差擴散避開格線、Logo 和 HUD，避免大片灰綠／紫褐色斑塊。Gem 的 64–255 palette 與 sprites 不變。背景輸出 RLE 過大時使用 `00 00` + 76,800 bytes；`main.c` 讀完整 24-bit EOF 並支援 raw 串流，`test_mos.py` 開局比對完整背景（排除執行期 HUD 數字），防止跨 64KB 截斷。

## 溝通與變更紀錄

2026-10-31 VERA 音訊補寫改為「佇列深度驅動」、Time Trial 改用 PCM 取樣數計時（使用者回報「不定期會出現 bo~bo~」、「放著不玩純聽音樂也會」、「播放完 2:00，遊戲時間才過 1:24」）：
1. 量測方法：以 `processorCycles` 逐 cycle 消耗 FIFO（8010.86 Hz、1 MHz CPU）＋wall-clock VSYNC 模型（17,073 cycles／frame）跑真實鍵盤交換。發現兩個獨立問題：frame 平均 27–31k cycles（1.6–1.8 個 VSYNC），而 `check_no_moves()` 每 30 frame 的全盤掃描（128 個虛擬交換）單次 115–160k cycles＝6–9 個 frame，期間完全沒有 `music_tick`，FIFO 從 1024 被抽乾到 0；另外 `waitvsync` 看到 latch 已設就立即返回，Time Trial 以「loop 次數」計時，所以遊戲時間只走實時的 0.48–0.60 倍，累積成音樂 2:00 對遊戲 1:24。
2. 修正一（斷音）：`music_tick` 不再猜固定 64 samples，改成 top-up 迴圈——先補一個 VSYNC 的 133／134，再 `while (VERA.irq_flags & VERA_IRQ_AUDIO_LOW) { 清 bit 3; feed(MUSIC_CATCHUP=128); 佇列回滿或來源耗盡就停 }`，`feed()` 回傳實際 sample 數。frame 多長都無所謂，佇列一定回到 1024。
3. 修正二（掃描期間的飢餓）：新增 `llvm/src/frame_pump.h`／`main.c` 的 `frame_pump()`；`board_find_solution` 每列、`board_generate` 每輪呼叫，若 VSYNC latch 已設就就地付掉 `effects_tick()`＋`music_tick()`。刻意不含 `timer_frame()`，避免在掃描途中重入 Game Over 流程。
4. 修正三（計時器）：Time Trial 改以「送出的 PCM sample 數」為時鐘——VERA 固定 8010.86 Hz 消耗 FIFO、佇列深度由 top-up 維持，所以 sample 數就是實時。`music.c` 新增 `clock_acc`／`clock_active` 與 `music_frames_elapsed()`（`CLOCK_PER_FRAME 133514`，千分位），`timer_frame()` 改加 ticks；`music_init`／`music_stop` 清除時鐘狀態。`time_frames` 由 `= 0` 改成 `-= 60` 並保留秒以下的餘數，不再每次跨秒丟掉 1–59 個 tick。
5. 驗證（wall-clock VSYNC ＋ 逐 cycle FIFO 模型，`test-zero.hdv`）：idle 900 periods＝timer 0.996–1.019、FIFO 歸零 0 cycles；8 次真實合法交換（score 0→60）＝0.999、FIFO 歸零 0 cycles、動畫之間平均 31k cycles。修正前同一模型 idle 約每秒漏 1 個 VSYNC、動畫期間 FIFO 見底。
6. 回歸：`test_mos.py`（兩 slot 全綠，含最後一秒完成回合、R、hint）、`test_music.py`、`test_pcm_clock.py`、`test_sound.py`、`test_no_moves.py`、`test_loading_progress.py`、`test_intro.py`、`test_loading.py`、`test_mouse.py`、`test_options.py`、`test_quit.py`、`test_random.py`、`test_vera_detect.py` 全綠。`test_music.py`／`test_pcm_clock.py` 起始多呼叫一次 `music_stop()` 把串流倒回第 0 byte，因為 `frame_pump()` 可能在 `start_game` 內就啟動引擎（`pcm_resets` 仍須恰好 1 次）。
7. 重建 HDV：`MUSIC.PCM` 仍 1012224 bytes／1977 blocks、映像 2048 KB，交付映像高分保留 `464748018f02000088040000`。以上都是 65C02／VERA model 結果，**尚未**做 AppleWin 或實機音訊擷取；斷音是否真的消失、2:00 與遊戲計時是否對齊，仍待使用者在 apple2ts 網頁版試聽確認。
8. 已知殘留：`R` 重載場景（`upload_scene` 串流 76,800 bytes）與開機進場景期間沒有 pump，會有一次性約 0.1 秒的 FIFO 歸零；不影響正常遊玩與音樂播放。動畫 frame 仍要 27–31k cycles（音訊本身就吃掉約 4.6k），這是 1 MHz 65C02 的固有限制；計時器已不依賴 frame 成本。

2026-10-31 VERA 音樂 PCM 電平修正（使用者回報太大聲、有「粉粉」的顆粒雜音）：
1. 原因有兩層。來源 `media/music.ogg` 本身峰值已達 0.94 全刻度，`build_music_pcm.py` 卻又 `volume=2.0`（+6 dB）再 `alimiter=limit=0.70`，等於整首貼著 ceiling 被削平，1.9% 的 sample 壓在頂端；另外網頁版 apple2ts 的 VERA 混音是 `(PSG + PCM) * 2` 後 clamp 到 ±1.0（AppleWin 是直接相加後 clamp int16，**沒有**加倍），0.70 全刻度的 PCM 乘 2 = 1.4 必然削波。來源檔削波加上混音器削波，就是聽到的粉狀雜音，而且是在喇叭前才產生，單純轉小聲不會消失。
2. 修正：`MUSIC_GAIN = 0.36`（改為衰減，不再增益），`MUSIC_LIMIT = 0.70` 保留但只當保險上限、正常不觸發。`music.pcm` 仍是 1012224 bytes／1977 blocks，峰值 ±61（0.48 全刻度、約 -22.9 dBFS）、rms 9.1；apple2ts 乘 2 後 0.96 不 clamp，音樂＋音效最壞相加 98/128 也不 wrap。音效檔與 runtime 混音程式未改。
3. 重建：`disk` target 重新產生 `MUSIC.PCM` 並重建 2048 KB HDV，`HISCORE.DAT` 保留（`464748018f02000088040000`）。`test_music.py`、`test_pcm_clock.py`、`test_sound.py`、`test_loading_progress.py` 兩 slot 全綠。
4. 後續追查「音量對了但還有雜音」：先排除量化雜訊——用同一條 ffmpeg 鏈重建參考訊號與 `music.pcm` 比對，誤差只有 0.287 LSB rms（峰值 0.50），A／B／C 三個候選檔試聽都聽不到雜音；再排除削波——現行電平在 apple2ts 的 ×2 clamp 下，所有音樂＋音效組合的裁切率都是 0%。剩下的來源是 FIFO 飢餓。
5. 在 `test_mos.py` 加 cycle 精確的 VSYNC 模型（17073 cycles／frame，FIFO 依 CPU cycle 消耗）後重現：遊戲 frame 經常超過一個 VSYNC（動畫 p95 約 24–30k cycles），`waitvsync` 看到 latch 已設就立即返回，但 `music_tick` 仍只補 133／134 samples，於是每個錯過的 VSYNC 就少補一個 VSYNC 的音訊；實測 240 frames 內 FIFO 歸零 4 次、共 2324 samples（每次 70–80 ms 空白），聽起來就是約每秒一次的「bo~bo~」斷音。
6. （已被上方 2026-10-31 音訊補寫／計時修正取代，保留為歷史記錄）修正：`music.c` 新增 `MUSIC_CATCHUP 64`；佇列低於目標深度（VERA ISR bit 3／`VERA_IRQ_AUDIO_LOW`，FIFO < 1024，AppleWin 與 apple2ts 都是即時計算）時，每 frame 多補 64 samples，並寫 bit 3 清除。目標深度不變，音效延遲仍約 128 ms；EMPTY 時整批補 1024 的保險也保留。
7. 驗證：同一個 cycle 精確模型重跑後 0 underrun bursts、FIFO 維持約 1000–1190；`test_music.py`、`test_pcm_clock.py`、`test_sound.py` 兩 slot 全綠；`test_mos.py` 兩 slot 全綠（要改用零高分的測試映像，見下方「可重現的測試」；交付映像的高分仍保留 `464748018f02000088040000`）。這些都是 65C02／VERA model 結果，仍未做 AppleWin 或實機音訊擷取，聽感待使用者確認。
8. 測試模型修正：`test_mos.py` 原本把任何 ISR 寫入都當成一次 VSYNC（會加 `frames` 並排空 FIFO），新增的 bit 3 清除會被誤算成 frame；現在只有寫 bit 0 才算一次 wait。

2026-10-29 音樂改為整首串流 PCM（`MUSIC.PCM`），移除 FM／VZM／PSG 音樂路徑：
1. 使用者聽過 FM 版後決定改成「像 IIgs 那樣全部 PCM」，且不管有沒有 YM2151 都用 PCM。`vera/tools/build_music_pcm.py` 以 `vera/assets/music.mid` → ffmpeg `aresample=8011`、`volume=2.0,alimiter=limit=0.70`、`-f s8` 產生 `vera/generated/music.pcm`（1012224 bytes，峰值 ±90、rms 37.5，約 126.35 秒）；`vera/tools/build_sound.mjs` 同樣改為 8-bit mono 8011 Hz、`volume=0.35,alimiter=limit=0.29`，五個音效共 9740 bytes（select 1100、fall 1431、match1 2403、match2 2403、match3 2403）。兩者共用一條 FIFO，為了在軟體相加時不溢位，音樂上限 90、音效上限 37。
2. `llvm/src/music.c` 重寫為串流引擎：`MUSIC_RATE 21`（AppleWin 換算 8010.86 Hz）、1KB ring、每 VSYNC 補 133／134 samples（由 VSYNC 計數交錯，非浮點），以 `SET_MARK`＋連續 MLI READ 讀 `MUSIC.PCM`，不預載、不占 Aux RAM；FIFO 掉到 EMPTY 時整批補 1024 bytes，`engine_start` 先預填 1024。`disk_epoch()` 解決「`sound_init` 再開檔導致音樂 refnum 失效」的問題，epoch 變了就重新 OPEN／SET_MARK。
3. `llvm/src/pcm_feed.S`：`pcm_copy` 純拷貝、`pcm_mix` 以 signed 相加把音效混進音樂；跨頁以 `LDA $FF00,Y`／`ADC $FF00,X` 加執行期修補高位元，`INY`／`INX` 後 `BNE` 判斷是否要 `INC` 高位，只在區段入口檢查一次 FULL。**不要**在組語重複宣告 `pcm_effect` 的 `.bss`（見除錯注意事項）。
4. 修正 `feed()` 的還原順序：原本先還原 `address` 再還原 `control`，在音效 staging 期間會把位址寫到錯誤的 port（實測 `addr` 兩次都是 `$18010`、`inc` 兩次都是 40）；現在一律 `VERA.control = ctrl; VERA.address = address; VERA.address_hi = hi;`，`sound_stage` 也保存／還原 port 0 的 `address_hi`／`address`／inc 狀態。
5. `vera/llvm/tools/build_hdv.py` 改為 2048 KB volume（`MUSIC.PCM` 1977 blocks），`build_loading.py` 的進度分母變 186 blocks（涵蓋 gems／select／fall／match／scene，不含 `MUSIC.PCM`）。
6. `test_music.py` 重寫成比對 1012224 bytes 的 `MUSIC.PCM` 實際送進 FIFO／VRAM 的內容、磁碟讀取位置、OFF／ON、與音效混音、R 重播、Esc 靜音；`test_sound.py` 比對五份檔案在 `$14800` 起連續位址 byte-exact；`test_pcm_clock.py` 以 CPU cycle 推進 FIFO，驗證音樂 5964 samples 與混音 2403 samples 都 exact 且沒有任何 PSG 寫入；`test_loading_progress.py` 更新為 186 blocks。兩 slot 全綠。
7. 刪除 FM／VZM／PSG 相關產物與工具（`music_aux.S`、`vzm_player_stub.c`、`build_music*.py`、`midi_psg_arrange.py`、`wav2psg.py`、`test_music_vzm.py`、`test_music_conversion.py`、`test_midi_arrangement.py` 等）。`fm_probe.h` 保留，但 `fm_detect()` 只在 Intro 顯示晶片有無，與播放無關；`vera/assets/music.mid` 保留為轉檔來源。
8. 尚未完成：本環境的 AppleWin `-fm-wav-dump` 只會產生全零樣本，無法客觀驗證音訊，因此這一版沒有 AppleWin 或實機聽感驗證；音樂是否「不乱」仍待使用者試聽。8 kHz 在 1 MHz CPU 上的代價約 4.56k cycles／frame，`test_mos.py` 動畫平均 17,937／17,991 cycles，偶爾會錯過 VSYNC，這是此硬體條件下的固有限制。

2026-10-28 測試 harness 補上檔案層 MLI，全部回歸重新全綠：
1. `test_mos.py` 的 `Machine` 新增 `read_catalog()`／`file_blocks()`（storage 1 單一 data block、storage 2／3 跟隨 index／master index）與 `mli()`：`$C7` 回 `/FREEGEMAS`、`$C8` 用 pathname 最後一段比對 catalog 名稱並發 refnum、`$CA` 依 offset 讀入指定緩衝、`$CB` 寫入並把 `HISCORE.DAT` 回寫 data block、`$CE`／`$D1` 用 3-byte 位置、`$CC` 關閉、`$65` 記錄 QUIT 參數；未知 command 直接 assert。
2. READ 越過 EOF 回 status `$42` 但 carry clear，其餘錯誤 status 才設 carry。這是 loader trampoline `BCS fail` 能載入非 512 整數倍 binary 的關鍵；若照「非零 status 一律 set carry」會停在 `fail` 回圈（PC `$2C68`）。
3. 三個測試原本寫死舊資產／舊函式：`test_music.py` 由 FGM2 改成播放出貨 raw `MUSIC.PSG`（7398 frame byte-exact、aux＋Aux LC 預載、loop／OFF／ON、R 重播）；`test_sound.py` 改比對 26912 bytes PCM 在四段 VRAM 池的實際位址；`test_loading_progress.py` 的檔案清單改為 `MUSIC.PSG` 等現行資產（每模式 329 blocks，不再找 `MUSIC.FGM`／`MUSIC.CRV`）。`test_no_moves.py` 移除已不存在的 `draw_gems`（棋盤現在只更新 sprites），`test_mouse.py` 的 LC 斷言改為 loader／音樂結束後的實際狀態 `$C082`（ROM read、bank 2）。
4. 全部 16 個回歸（`test_vera_detect`、`test_music_vzm`、`test_music_conversion`、`test_midi_arrangement`、`test_options`、`test_loading`、`test_intro`、`test_quit`、`test_random`、`test_loading_progress`、`test_pcm_clock`、`test_sound`、`test_mouse`、`test_no_moves`、`test_music`、`test_mos`）兩 slot 通過；這些仍是 65C02／VERA model 結果，不是 AppleWin 或實機測試。

2026-10-28 YM2151 FM 音樂路徑（`MUSIC.VZM`）與 PSG 後備：
1. `llvm/src/fm_probe.h`：71-byte 的 YM2151 BUSY probe，依 `VERA_BASE`（slot 2 `$C0A0/$C0A1`、slot 4 `$C0C0/$C0C1`）分成兩份表。`fm_detect()` 把它抄到 `$0300`、呼叫後讀 `$02FF`；`music_init` 與 `intro.c` 共用同一份表，Intro row 4 顯示 `FM: YM2151 DETECTED (OPM)` 或 `FM: NONE, PSG MUSIC ONLY`。probe 必須在 `music_aux_init` 之前跑，因為後者會把 18-byte reader 鏡像到同一個 `$0300`。
2. `llvm/src/music.c`：`music_init` 先偵測晶片，有 FM 且 `MUSIC.VZM` 存在（3 ≤ size ≤ 63488）時載入 VZM，否則載入 `MUSIC.PSG`；兩者都整份預載、播放期間不讀碟。VZM 沒有檔頭與 512-byte 記錄補齊（目前 28534 bytes、112 個 logical page，只用 Aux RAM `$0800` 之後），只有 `$FF` 在結尾代表 loop 回 0。
3. VZM 記錄格式（不是完整 ZSM 檔）：`$00–$7F` 延遲 N 個 VSYNC tick、`$80–$BF` PSG（`0x80|reg`,value）、`$C0–$DF` FM batch（count=`(byte&$1F)+1`，count 組 reg/value）、`$E0–$FE` NOP、`$FF` 結束並 loop。tick 0 與每次 loop 先 key-off 並把 YM 寄存器 `$20–$FF` 歸零（PSG 基線 `0,0,0,128`），因此轉換器的去重基線就是全零；`$08`（key mask）永遠不省略。
4. `vera/tools/build_music_vzm.py`：以 `vera/assets/music.mid`（使用者提供的 MIDI 轉譜，format 0、3175 音符、122.8 秒、無鼓軌）的音符清單建置，不再使用 `wav2psg.py` 的 FFT／onset 分析。聲部：聲道 7 為最高音旋律（lead），聲道 0／1 為低音 bass，聲道 2–6 為 tine 伴奏；音符由 key-on 到 key-off 固定佔用同一聲道（不因旋律改變而重觸發），聲道滿時偷取最早結束的音。每個 carrier TL 只依 MIDI 力度在 note-on 寫一次，CON=4、三組 patch（bass／tine／lead）在 frame 0 編程；產出 `generated/music.vzm`、`generated/music.zsm`、`generated/music_vzm.h` 與 `llvm/build/music_vzm_report.json`（7367 ticks、10959 FM writes、0 PSG writes、432 次 voice steal）。CMake 的 disk target 會重跑此腳本，`build_hdv.py` 額外打包 `MUSIC.VZM`。
5. YM2151 細節：operator slot 順序是 `M1,M2,C1,C2`，CON=4 時 carrier 是 slot 2／3（TL `$70+ch`／`$78+ch`），modulator 是 slot 0／1（`$40/$48+ch`）；KC 用 `midi//12-2`、code 14（C）對 C，其餘 `midi//12-1` 配 `KC_INVERSE`，實測約 ±40 cents。TL 約 0.75 dB／step。
6. 測試：`llvm/tools/test_music_vzm.py` 不經 resident loader，直接比對 probe（有／無晶片）、Intro 文字、`music_init` 選擇與後備、以及 7368 tick 的 PSG 影像與 FM 寫入順序（兩 slot 都 byte-exact，含 loop 與 stop／OFF）；`test_mos.py` 增加 YM2151 model（BUSY、select/data port 與寫入紀錄）。FM 起播／loop 兩個 tick 各約 44k cycles（約 43 ms），其餘平均約 743 cycles。
7. 尚未完成：本 session 的 AppleWin 在無互動桌面／無音訊裝置下無法推進（DirectSound 初始化後停住），因此沒有實機或 AppleWin 聽感驗證。這次以大迴圈校正：FM-only 串流的 chroma 與原作 OGG 在整首各段相關係數 0.64–0.77（舊 FFT 版 0.47），逐半音以 melodius 量測 KC 音高誤差 <40 cents，這些都是客觀比對，不能取代試聽；轉譜仍非原作分軌或人工校訂樂譜。

2026-09-30 音效裁切與完整 Raw PSG 記憶體預載（`optimize` 分支）：
1. `build_sound.mjs` 將 `match1.pcm`、`match2.pcm`、`match3.pcm` 直接在建置階段截斷為 6640 bytes（約 0.30 秒），五個 PCM 總計由 65672 bytes 降至 26912 bytes，完全塞入 VERA VRAM 的 109 頁預載池（27904 bytes），徹底釋放 Aux RAM，並移除 `sound.c` 的 Aux RAM 讀取邏輯與 `MUSIC.CRV`。
2. `music.c` 與 `music_aux.S` 改為直接載入並播放 `MUSIC.PSG`（由 `music_midi_pure_smooth.psg` 經 `build_music.py` 套用 +9dB 增益產生的 `generated/music_pure_gained.psg`，56675 bytes，約 222 pages），不再使用 FGM2／Huffman 曲線壓縮（同時釋放 Main RAM 的曲線表空間）：
   - Logical pages `$08..$BF`（184 pages，46 KB）存入 Aux 48K RAM `$0800..$BFFF`。讀取時必須透過 `music_aux_init` 鏡像在 Main/Aux `$0300` 的 18-byte `music_reader` 切換 `$C003`/`$C002`（`RAMRD` 會連同 CPU instruction fetch 一起切換，不可直接在 Main RAM `.text` 內開啟 `$C003`）。
   - Logical pages `$C0..$FF`（最多 64 pages / 16 KB，實際使用 38 pages / 9.5 KB）透過 `ALTZP`（`$C009`）直接連續線性映射至 Aux Language Card Bank 1 `$D000..$FFFF`（`$C08B`），徹底摒除 Bank 2 切換與位址折疊，整段 46KB 之後資料連續平坦存取。
   - 存取 Aux LC 期間禁止在 `STA $C009` 與 `STA $C008` 之間使用 `PHA`/`PLA`（因為 `ALTZP` 會連硬體 Stack `$0100` 一起切到 Aux），且結束後必須執行 `LDA $C081; LDA $C081; LDA $C082` 還原全域 LC 狀態為 Bank 2 + ROM read / write-protect，避免 ProDOS 與 Mouse firmware 崩潰。
   - 修復 1:38（第 5916 frame / page `$C0`）音樂切斷問題：原本在搬移 loop 內每 byte 切換一次 `ALTZP` 導致 Aux LC 寫入狀態錯亂，且讀取時多讀一次 `$C083` 變成讀寫模式；修正為搬移 256 bytes 期間僅在外層單次切換 `ALTZP` 並改用連續 Bank 1，確保 46KB 之後的資料正確寫入與讀出，曲子可完整播完 2 分 03 秒。
3. `build_music.py` 音量再調增 20%（`MUSIC_GAIN` = 3.394，約 +10.6 dB），提升遊戲內 PSG 音樂聽感。

2026-09-30 修復 Endless Mode 進入 Game Over 後，按 R (Reset) 不會畫出分數 `0` 的問題。原因為 `upload_scene()` 雖清除了 VRAM 畫面，但 HUD 快取 `displayed_digits` 並未失效，導致 `draw_score()` 以為畫面上仍有之前的 `0` 而略過繪製。在處理 R 鍵時將 `displayed_digits` 陣列全數標記為 `0xFF`，強迫 `draw_score()` 重繪即可解決。

2026-09-30 修復 Game Over 後按 Reset 的動畫流程，使其符合原作行為：

1. **`redraw_game()` 改為補牌落下動畫**：原本 `hide_sprite(0..127)` + `draw_gems()` 直接定位。現在改為只隱藏效果 slots（64–127），將所有 gem sprites 預放在螢幕上方（負 Y），再呼叫 `animate_fall()` 讓所有寶石從頂部掉落，符合原作 Reset 動畫。

2. **R 鍵 Reset 呼叫 `upload_scene()` 重載場景**（螢幕維持開啟，線上重繪），再進入落下動畫。不做 VRAM 備份。

   **曾嘗試但放棄的方案**：
   - 填零清除文字帶（`erase_game_over` fill 0）→ 把棋盤底圖也清掉了，底圖不是 color 0。
   - VRAM 雙埠備份（`GO_BACKUP_VRAM=0x16400`）→ 該位址落在 PCM pool（`0x14800`起）和游標 sprite pattern（`0x19000`）範圍內，VRAM 沒有連續 16KB 空閒區塊；寫入後游標 pattern 被 bitmap 像素覆蓋，游標變雜碼。
   - Sprites 遮蓋文字（no-op erase）→ gem sprite 四周有透明邊緣（24px artwork 在 32px frame），GAME OVER 文字從縫隙透出，不可行。
   - `VERA.display.video=0` 黑屏後 `upload_scene()` 再開回 → 可行但不必要，用戶反映直接線上重載即可。

2026-09-27 遊戲HUD亦改sentence case：Score／Time left／Show hint／Reset game／Exit。只修改素材generator的標籤，位置、字級、按鈕置中、emoticons及hitboxes不變；Time Trial／Endless場景及palette同步重建。原作logo、分數／時間數字、Game Over文字及開機文字不在此變更範圍。

2026-09-27 選單文字改 sentence case：Title 使用 Timetrial mode／Endless mode／How to play?／Options／Exit；How to Play 標題、說明段落及返回提示改句首大寫；Options 使用 Music／Sound／Fullscreen: On／Back／High score，runtime On／Off 與 Timetrial／Endless 高分標籤同步小寫。`build_assets.mjs`補齊5×7小寫glyph，原字級、置中與hitboxes不變；重新量化共用title palette後需一起更新Title／Howto／Options場景及title gems。遊戲HUD、原作logo及開機文字保持原樣。兩slot高分置中／右對齊回歸通過。

2026-09-27 無卡文字頁補完（取代下方單行停止提示）：loader 保存偵測slot至page3 `$03EC`（0=無卡），无卡亦載入 INTRO.BIN，但跳過VERA寄存器設定及高分讀取。Intro完整顯示作者、網址、STATUS、mouse signature結果與操作；無卡不碰VERA／不等待VSYNC，顯示 `STATUS: VERA NOT DETECTED` 和 `STOPPED: VERA REQUIRED IN SLOT 2 OR 4` 後永久停止，按鍵不會繼續。probe只驗證DATA0 read導致VRAM address +1，不寫bitmap；仍拒絕open bus及RAM echo。`test_vera_detect.py`新增完整文字及按鍵不能跳過的驗證，兩slot正常按鍵／逾時Intro回歸通過。

2026-09-27 無 VERA 防誤判：loader 的舊 probe 只驗證寄存器／DATA0 寫入回讀，ROM shadow／普通 RAM 可能也回傳相同值。改驗證 VRAM DATA0 read 後 address 自動 +1，slot2／4都不通過時，文字顯示 `STATUS: VERA NOT DETECTED - STOPPED` 並永久停止，不載入 Intro／Title／Game，也不等待不存在的 VSYNC。`test_vera_detect.py` 涵蓋 open bus、RAM echo 假卡與兩種真卡模型。resident loader空間不足，縮短高分寫入失敗提示至 `HIGH SCORE SAVE FAILED`，失敗不QUIT／dirty不清的行為不變。

2026-09-27 開機 STATUS 補上 `MOUSE: SLOT 4`／`MOUSE: SLOT 5`／`MOUSE: NONE`，以及 click／drag 操作說明。Intro 只讀 ROM signature，不呼叫 firmware，以免 screen holes 破壞文字頁；VERA slot 4 排除同 slot 的 mouse。README 分為英文 `README.md` 與繁中 `README-tw.md`，互相連結。`test_intro.py` 驗證 mouse 有／無及兩種VERA slot的按鍵／逾時清畫面路徑。

2026-09-27 滑鼠操作補完：遊戲按住第一顆 gem 拖至相鄰格即使用既有交換／消除流程，一次按住只交換一次；放開後可重新操作，原有兩次點擊保留。Title 五項支援滑鼠移入選取／點擊，Options 支援 Music、Sound 切換及 Back（Fullscreen 固定 ON），How to Play 點擊返回。子頁面清除前頁 sprite attributes，共用 `menu_mouse.c` 的原作手形 16×16 8bpp sprite，白色255及 title palette 最暗非透明色，不修改色盤；每 VSYNC polling，靜止滑鼠不覆蓋鍵盤選項。Mouse driver 同樣連入六個選單 binaries，保護 firmware ZP／LC。音效 disk/PCM staging 共用保留 `$0C00..$0DFF`，音樂 runtime cache 獨立，釋放512-byte BSS以容納拖曳程式；正常播放不讀碟。`test_mouse.py` 新增選單導覽、切換／長按不重複、How to Play 返回、拖曳交換與不重複觸發；仍為65C02模型而非實機。

使用者以繁體中文溝通。畫面 bug 優先對照原作截圖和素材，再定位負責產圖、loader 或執行期繪製的單一來源。修正後重建 HDV；回報時說明實際改動和驗證範圍，區分 AppleWin 驗證與實機測試。

開機說明結束（按鍵或逾時）先清除整個文字 page 1，再返回 loader 顯示 `LOADING TITLE...`；不能只覆寫第一行而留下操作說明。`test_intro.py` 檢查兩條路徑的其餘 23 行均為空白。

loader 的 `status()` 本身也必須清除 `$0400–$07FF`，不能依賴 intro 已經清過；`loader.s` 的 `clear_text` 不占 ZP，適用 Options／Game 返回 Title 的每次 loading。`test_loading.py` 用髒文字頁驗證兩 slot；AppleWin slot 4 重現 Options → Esc → Title，確認只剩載入訊息。

Title 對照 1.png，寶石終點與五個選項整組上移 12px：sprite y=104、選項 y=144 起每項 17px，EXIT y=212，底部保留 21px。動畫維持由底部升起；指標備份／繪製位置與選項同步，indexed preview 也同步更新。AppleWin 已確認 EXIT 指標與 Options 轉頁。

Options 高分區使用 1× 字級（小於上方 2× 選單），`HIGH SCORE` 置中於 y=151；兩模式列位於 y=171／185，依較長分數的位數計算共用寬度，整塊以 x=160 置中，冒號與右對齊數字共用欄位。6px pitch 可容納完整 uint32；`python vera/llvm/tools/test_options.py` 驗證兩 slot 的 0、五位數、不同位數與十位數紀錄。

重要演進：專案最初曾以 6502 組語做單一遊戲畫面的原型；後續改為 LLVM-MOS C，並拆成常駐 loader、title／子頁面程式與遊戲程式。現在的分數、計時、sprites、RLE 場景與 How to Play／Options 都屬於此分段版本。

## 待辦事項

2026-10-29 起音訊已全部改為 PCM：音樂是 `MUSIC.PCM` 串流、音效是 `$14800` 的 8-bit PCM，沒有 FM／VZM／PSG／Aux RAM／`music_aux.S` 路徑。以下 2026-09-27／09-30／10-28 的音效與音樂條目（含 `MUSIC.PSG`、`MUSIC.VZM`、FGM／Huffman 曲線、Aux Language Card、`test_music_vzm.py`、PSG 打擊合成、`midi_psg_arrange.py`、`wav2psg.py` 等）都已被取代，只作為歷史記錄，不是現行待辦，也不要再從這裡挑工作。

音量追調：使用者表示遊戲音樂太小聲，`build_music.py` 的 `MUSIC_GAIN` 由2提高至2.828427（較前版約+3dB，較原始PSG約+9dB），按硬體LUT取最近音量，超過511上限則封頂，沒有改音高／tempo／編排。此後音樂完整寄存器比對依新映射。

2026-09-27 音效預載重整（取代下方舊串流／FGM1 記憶體描述）：五份 raw PCM 共65672 bytes，27904 bytes 放上述四段 VRAM，餘37768 bytes 放 aux `$2C00..$BFFF`；播放不讀磁碟，原始 PCM byte 不變。音樂 FGM2 事件9014 bytes 放 aux `$0800..$2BFF`（配置9216 bytes），共用 Huffman 音量曲線9167 bytes 放 MAIN `$0800..$0BFF`、`$0E00..$1FFF` 及3535-byte BSS；避開磁碟 buffer `$0C00..$0DFF`。`music_aux_top` 決定音效 aux 起點；必須先 `music_init` 再 `sound_init`。aux reader 的 source 與 destination operands 都需同步 MAIN／AUX 鏡像，音效 cache 不可覆蓋音樂 cache。Gem patterns 改由 `GEM.PAT` 載入，不再重複佔用主程式7KB。HUD 背景備份移主 RAM，取消 Game Over VRAM 備份；Game Over 按 R 才在靜音後重載場景，正常消除／R 不重載場景。起播先填滿約4KB FIFO，後續每 tick 最多補1024 bytes（FULL 就停），避免慢消除時512-byte補充不足。兩 slot 五份音效完整 FIFO byte 比對、零 runtime 磁碟讀取及音樂7398-frame全部寄存器比對通過；音樂解碼平均4652、最高17324 CPU cycles/tick。主程式 `__bss_end=$AFF9`。VERA 仍需 CPU 補 FIFO，不是自動從 VRAM 播放；不能僅因預載宣稱所有實機 lag 消失。下方早期測量保留作歷史，不代表目前效能。

- [ ] 忠實原作音效：使用者拒絕 PSG 合成音。已改五個原作 OGG → 16-bit mono PCM（rate 29／11062.622 Hz），沿用原作 gain 0.3／0.25，刪除自創 Hint／Reset／Game Over 音效。`build_sound.mjs` 使用 ffmpeg 解碼／高品質 SWR 重採樣，輸出五個 `generated/*.pcm`，試聽 WAV 在 `llvm/build/`；disk target 自動轉換／打包。`sound.c` 啟動快取每檔 sapling index（最多 48 blocks），runtime 讀 512-byte buffer，`pcm_feed.S` 補 VERA FIFO，不動 VRAM／PSG。`test_sound.py` 兩 slot 比對五條完整 FIFO stream 與生成 PCM byte-for-byte，覆蓋 FULL／EMPTY、OFF／ON、MLI ZP、swap／Esc。**仍非 100% 原作**：取樣率／stereo、同時混音、Title／Options select 音效尚未完成；目前新音效中斷舊音效。1 MHz CPU 初步動畫平均約 31.5k cycles/frame，比無音效慢，需優先降低串流成本／預載取樣；不能宣稱效能、實機聲音已驗證。
- [x] 遊戲背景音樂：PSG 後備路徑採使用者核准的純音版音符／平滑包絡，無 bass／鼓模擬／額外泛音；`tools/build_music.py` 產生的 `generated/music_pure_gained.psg` 直接以 raw `MUSIC.PSG` 串流播放（+9dB 增益，見上方 2026-09-30 記錄，`music.fgm` 已不再使用）；有 YM2151 時改用 `MUSIC.VZM`（見 2026-10-28 記錄）。VERA 波形／gain 與線性 preview 不同，不能聲稱聽感／响度相同；實機試聽仍待確認。Options Music 真正控制遊戲音樂，R 從頭、Esc 靜音；Title／Options 尚無音樂。與 PCM 音效互不占用同一路徑。
- 音樂記憶體：Apple IIe aux `$0800` 起載入整首 packed stream，範圍不得超過 `$BFFF`；主 RAM 增加512-byte載入buffer、92個block索引、256-byte頁cache。遊戲期間音樂零磁碟讀取；缺aux RAM時安全停用。`music_aux.S` 把18-byte reader鏡像至MAIN／AUX `$0300..$0311`，RAMRD會連instruction fetch一起切換，必須鏡像！source page operand `$0307` 兩份同步，切換期間SEI，RAMWRT保持MAIN；stack/ZP留MAIN。loader下一次launch覆蓋MAIN `$0300`，所以Esc先music_stop，再回loader。不要改ProDOS vectors `$03D0`起或page3設定。
- `test_music.py` 直接播放出貨的 raw `MUSIC.PSG` 後備流（`generated/music_pure_gained.psg`）：兩 slot 各 7398 frames 逐 frame 比對 PSG 寄存器影像，涵蓋 aux／Aux LC Bank 1 預載、loop、OFF／ON、與 PCM 互不干擾、R 重播與 Esc 靜音。FM／VZM 路徑另由 `test_music_vzm.py` 覆蓋（probe、選擇與後備、7368 tick 的 PSG 影像與 FM 寫入順序、loop、stop／OFF）。
- PSG 砂礫聲試聽：`tools/midi_psg_arrange.py --style ensemble --no-overtones --smooth` 產生 `generated/music_midi_ensemble_no_overtones_smooth.psg`；不加短泛音，包絡改 60Hz，三 frame 平滑起落，立即换音高前先靜音。保留舊版／原 MIDI；測試與完整 stream 驗證通過，尚未證實消除雜音，也未接入 HDV。詳細限制見 `docs/music-conversion-research.md`。
- 網路研究／舊 MIDI converter 修正：參考原作者 Easy Lemon 曲目頁、DreamTracker VERA instruments/envelopes、Furnace VERA macros；詳細來源／取捨在 `docs/music-conversion-research.md`。原作配器 Guitar/Bass/Kit/Celesta/Marimba；使用者 MIDI 全部 channel0/program0 鋼琴，沒有鼓組分軌。舊 piano preset 增加 +7 等額外音高、低音升八度、多 voice bass、數秒 bass release、高力度壓縮和 WAV tanh，不能當通用忠實轉換。新 `tools/midi_psg_arrange.py` 保留原音高、力度、tempo/pedal/bend，短 release，priority voice allocation；clean 與按音域推估配器的 ensemble 兩個試作。`test_midi_arrangement.py` 驗證無額外五度／無移調、力度和 release、原 MIDI 和 loop 流；兩版經 check_psg 通過。PSG 75.6KB／91.8KB，仍有 voice steal，未接入遊戲，不能宣稱最佳聽感或已解決記憶體／效能。試聽 `llvm/build/music_midi_clean_listen_25s.wav`／`music_midi_ensemble_listen_25s.wav`（僅試聽線性增益3倍，非硬體擷取）。
- 使用者提供 `llvm/build/music_original.mid`：以 veramusic `mid2psg.mjs --synth=piano --chorus=off --loop` 轉換（先複製為 `music_from_midi.mid`，防止 converter 覆寫同名原作 WAV）。MIDI format 0／3175 notes／122.8秒，PSG 7397 frames／123.3秒含 release、60272 bytes、26436 writes、max40/frame；`check_psg.mjs` 驗證 loop 0／全流通過。PSG 複本在 `generated/music_from_midi.psg`；完整試聽 `llvm/build/music_from_midi.wav`、25秒 `music_from_midi_25s.wav`。這版直接依 MIDI 音符轉換，不套先前 FFT／手工 taiko detector；未接入遊戲，需再確認 MIDI 是否有正確鼓聲標記和聲音表現。原作 `music_original.wav` 保留不覆寫。
- 太鼓再修正（使用者指出仍像木魚）：移除 700／1190Hz woodblock 與高鼓殼起音，打擊聲道 12–15 改成兩組交替的 72Hz 鼓身＋128Hz 共鳴。兩次敲擊各自衰減（18／11 frames），第二個咚不截斷第一個尾音；不硬補固定雙擊，依低頻 onset 保留原來間距。`test_music_conversion.py` 驗證双擊尾音重疊、無高頻木魚 partial、自然靜音。最新試聽 `llvm/build/music_psg_taiko_double_25s.wav`。四段的樂器音色仍需使用者試聽，不能宣稱合成版就是原作取樣。
- 使用者指定 0:05／0:11／0:17／0:23 的促音是 taiko 類敲擊：短 bass smear／與低頻瞬態同時的短高音不再當旋律。`route_short_transients()` 全曲套用規則（不硬寫時間點），保留持續 bass 與其他旋律。低鼓改為近固定 88Hz triangle 鼓身（12-frame 衰減）＋173Hz 短鼓殼起音（6-frame），聲道 12／15；13／14 保留 woodblock。最新 25 秒試聽 `llvm/build/music_psg_taiko_25s.wav`；仍是 PSG 模擬，不是原作太鼓取樣。
- 音樂促音修正：原節奏瞬態直接映射連續 noise，改用離散 onset／refractory 偵測，PSG triangle 模擬低音 tom（快速降音高、8 frame 衰減）與雙部分音 woodblock（4／2 frame 衰減），聲道 12–14，不再有 noise 鼓聲。打擊包絡不受旋律的 20Hz 音量節流影響。`test_music_conversion.py` 增加觸發、衰減和無 noise 測試；新 25 秒預覽為 `llvm/build/music_psg_percussion_25s.wav`。仍是合成近似，尚未接入遊戲。
- 音樂試作：`tools/wav2psg.py`（Python／NumPy／ffmpeg）原作 `music.ogg` → WAV → 離線 FFT／時間中值分析多音高與瞬態 → triangle／noise 60Hz PSG。`generated/music_trial.psg` 為約 126 秒的近似轉譜，非原作錄音／人工校訂樂譜；未接入遊戲。事件流符合 veramusic `check_psg.mjs`；WAV 預覽、原作 WAV、JSON 統計在 ignored `llvm/build/`。預覽沿用 AppleWin PSG 音量 LUT、未 normalize，noise 近似。曲名／作者來自 OGG tag：Easy Lemon／Kevin MacLeod。尚需試聽、修正錯音與配器、規劃和 PCM 音效共存的記憶體配置；不能只因 PSG 流較小就宣稱已解决遊戲 lag。
- [x] 查明原作 high score：Time Trial／Endless 各自一筆；Game Over score table 顯示目前分數與 `Latest high score`。`ScoreTable` 先讀舊紀錄，若本局較高便更新 SDL preference 目錄的 `options.json`；畫面標示的是更新前的紀錄。
- [x] High score：兩模式分開保存／Options 顯示；AppleWin 測試映像寫入 12345／67890，關閉後 slot 4 冷啟動正確讀回。65C02 測試另涵蓋兩 slot、失敗重試、MLI ZP 保護與 rebuild 保留。Game Over 顯示更新後紀錄。
- [x] Title 背景 palette：加權量化、RGB444 refinement、誤差擴散，已比對原圖與 AppleWin 實際顯示。
- [x] 消除 VFX／得分浮字：每組 match 得分、連鎖倍率、hint 初始 0 分；字形預載，星芒縮小消失，不重畫 bitmap。
- [x] 棋盤／gem：常駐 sprites、只更新移動 gem、加速 HUD 局部數字更新、透明邊緣修正、頂框遮罩、落地不再重畫。兩 slot 各測 13 次合法交換（包含 2 次多段連鎖）、非法交換、Hint、R、最後一秒完成回合才 Game Over。

## 可重現的測試

2026-09-27 Loading 完成文字（依使用者澄清）：row1 保留滿格進度條＋`100%`；row2 顯示 `GAME START` 取代 `PREPARING BOARD`，其餘欄位清空。畫100%、更新下方stage後才停用loading，隨即進遊戲、不新增等待。`test_loading_progress.py` 兩slot兩模式驗證完整100%字串與下方GAME START，不能把GAME START放在百分比位置。

2026-09-27 Apple Mouse Card 初版：參考 `C:\dev\a2d\src\mgtk\mgtk.s` 的 ROM 簽章與 firmware 呼叫慣例。VERA slot 2 build 掃 slot 4、5；VERA slot 4 build 只掃 slot 5，避免把 VERA 當 mouse card。命中 `$Cn0C=$20`、`$CnFB=$D6` 後呼叫 INITMOUSE／CLAMPMOUSE（320×240）／SETMOUSE／HOMEMOUSE，遊戲每 VSYNC READMOUSE；游標映射至 26px 棋格，primary button 按下沿等同 Space，可點選後再點相鄰 gem 交換。無卡時保留鍵盤操作。已編譯兩種 VERA slot；尚未用 Apple Mouse Card 實機或 AppleWin mouse card 驗證，第一次交付前需實際測試座標方向、按鈕極性和 VERA slot 4／mouse slot 5 共存。

2026-09-27 滑鼠初始化修正（使用者回報 Time Trial 顯示 FILE 後卡住）：初版錯把 `$Cn12..$Cn19` 的單 byte 入口 offset 當成雙 byte 指標，且未設定 firmware 必要的 X=`$Cn`、錯用 slot-indexed clamp 參數。現在向量高位固定 `$Cn`、Y=`slot*16`、clamp 參數寫固定 `$0478/$04F8/$0578/$05F8`；座標回傳才使用 slot-indexed screen holes。Firmware 呼叫保存／還原 `$00..$BF`，同步共用 `mli_saved_zp`（mouse polling 與 MLI 不重入），避免把 `$A0/$A1` 誤當成 linker 保留區。INITMOUSE 前映入系統 ROM，之後還原 LC RAM/ROM 及 bank 1/2；不能沿用 DeskTop 固定 bank 1 的假設或用 `$C081` 當 RAM read。鼠標只在移動／新按下時更新棋盤游標，靜止時不覆蓋鍵盤移動，Game Over 不重顯游標。`test_mouse.py` 以 AppleWin ROM 的實際入口 offsets、firmware 契約 trap／刻意破壞 ZP、LC bank 2 模型，驗證真實 Intro→Title→兩模式載入、三種 VERA/mouse 組合、無卡鍵盤、按下沿與合法交換；這是65C02模型而非實際 AppleWin。若交付HDV被模擬器鎖住，可用 `build_hdv.py --output vera/llvm/build/freegemas-mouse-fixed.hdv` 產出獨立映像，並從原映像保留 high scores。

2026-09-27 手形游標與 HUD 點擊：`build_mouse.mjs` 從原作 `media/handCursor.png` 以 area filter 縮為16×16／4bpp透明 pattern，保留黑框及白色填色（13px版本細節過少，因此使用16px）。CMake 產生128-byte header；載入至 `$1F040..$1F0BF`（不碰 PCM 預載池），sprite 64 高順位／z-depth 3，其他 overlay slots 整體後移1。每個滑鼠 polling 更新 hand sprite，不重畫 bitmap；Show Hint `[7,85)×[168,185)`、Reset Game `[7,85)×[187,204)`、Exit `[7,85)×[215,232)` 的 primary 按下沿呼叫既有 H／R／Esc 流程，Game Over 可點 reset／exit。music 啟動讀碟 buffer 改共用既有 `$0C00..$0DFF` staging page（曲線配置本來就避開這段），釋放512-byte BSS，runtime music cache 不變。初始化無卡路徑曾在增加程式後超出短 branch 的127-byte範圍，65C02回歸重現跳入 music_store；已使用 inverse branch＋JMP，兩slot兩模式無卡路徑通過。`test_mouse.py` 增加 hand attribute／pattern未被PCM覆蓋、三按鈕與鍵鼠共存；`test_mos.py` 的 hint／effect slot 檢查同步新配置。

2026-09-27 match1 偶發尾音變大：沿用使用者先前切尾方案，match1 也限制前6640 bytes／約0.30秒，三個 match 共用 `MATCH_SHORT_BYTES`，磁碟素材／預載布局不變、select／fall與音樂不變。`test_sound.py` 三個match比對縮短前綴並檢查結束靜音；`test_pcm_clock.py`新增兩slot的match1實際渲染模型回歸（包括刻意排空FIFO）。這是縮短尾段的處理，不宣稱已查明偶發音量突增的完整實機根因。

2026-09-27 Loading Game 進度條：GAME.BIN 開始執行後在原生文字 page1 row1 `$0480` 顯示20格ASCII條及百分比，row2 `$0500` 顯示 GEMS／SCENE／MUSIC／SOUND EFFECTS／PREPARING BOARD。每個資產 data block 讀入後 `loading_step`，總量由 `llvm/tools/build_loading.py` 依實際資產大小產生 `loading_data.h`（當前兩模式各331 blocks；不包含directory/index）。讀完資產到99%，初始化棋盤／HUD／sprites後才100%，不加人為等待。`loading_active` 開局後清0，正常遊戲及Game Over R重載不重畫文字進度。Resident loader未擴大；GAME binary本身載入期間仍只有原有LOADING GAME文字，進度條涵蓋後續資產預載而非binary。`test_loading_progress.py` 兩slot、兩模式比對HDV實際檔案總block數、單調0..100%、文字條與退出loading狀態；`test_loading.py`保留其他轉頁清文字檢查。進度函式在main.c、共用宣告loading.h；CMake依資產重生總量，不可手工填假百分比或在aux曲線區放文字緩衝。

2026-09-27 使用者要求切尾音：match2／3 改只播放前6640 bytes（3320 mono16 samples，rate29約0.300秒），`MATCH_SHORT_BYTES` 為來源常數；完整原始 PCM 仍預載、不改磁碟素材與配置，不再送出後段。這是使用者核准的縮短版，不能聲稱完整原作音效。EOF 等FIFO排空後改呼叫 `sound_stop`（先靜音、rate0、清FIFO與讀取狀態），不能只rate0留下非零音量／最後樣本。`test_sound.py` 比對match2／3的前6640 bytes、其他三份完整內容；`test_pcm_clock.py`比對實際渲染縮短樣本，兩者另檢查EOF音量為0。音乐不變，聽感／截斷click仍需AppleWin試聽，不能聲稱尾音根因已完全驗證。

2026-09-27 持續爆音第二次時序修正：新增 `test_pcm_clock.py`，用65C02 processorCycles、1.023MHz CPU及VERA rate29計算採樣，在每個CPU instruction後消耗FIFO；mono16只在至少2 bytes時播放，尾端1 byte依AppleWin行為丟棄。搭配music_tick及aux頁讀取，故意插入230ms長運算。此前「EMPTY時只回退1 byte、仍保持採樣」的程式在新測試確實失敗（match2 渲染18796／預期18812 bytes，offset5120起錯位）；補充第一個low byte仍可能在high byte到達前被硬體再次丟棄。現在 EMPTY recovery 先rate=0、回退孤立byte、預填至FULL或樣本EOF，再恢復原rate；aux頁搬運途中EMPTY亦重走此恢復。正常FIFO非空時不暫停。這是模型時序重現／修正，不是AppleWin音訊擷取；實際爆音試聽仍待確認，不能把先前純FIFO寫入byte相同誤稱為實際渲染也正確。

2026-09-27 強制音效替換：match2 必須立即中斷 match1，match3 立即中斷 match2，不等舊音效播完、不混音。原本 `sound_play` 已呼叫 `sound_stop`；現在停止流程先寫 control `$20` 靜音，再 rate=0、control `$A0` 清 FIFO，清 remaining／cursor／cached_aux／initial_fill／pcm_count，最後才設定新音效、預填 FIFO、rate=29。`test_sound.py` 在舊音效 FIFO 尚未空時實際執行 match1→2→3，驗證每次一次 reset、FIFO 與後續 refills 只有新樣本、零磁碟讀取，以及 sound_stop 後不能恢復旧樣本。此檢查不能取代 AppleWin 爆音試聽，不能宣稱此前一定有重疊或本次已證實排除所有爆音。

2026-09-27 match2／3 播放後爆音：新增強制 FIFO underrun 回歸在修正前確實失敗。AppleWin FIFO 上限4095 bytes，mono16 FULL 可讓送出 cursor 停在奇數；播放耗盡時 `renderPcmSample` 會對不足2 bytes的尾端 `fifoReset`，丟棄孤立 low byte。舊程式再由下一個 high byte 開始補，造成剩餘 PCM 全部高低 byte 錯位。`sound_tick` 現在檢查 EMPTY＋奇數 cursor，回退1 byte／remaining加1，重送被丟棄的 low byte；aux 頁讀取後亦再檢查，因讀取期間硬體仍在播放。正常不中斷播放依舊 byte-exact；測試對 match2、match3 各填滿4095 bytes後模擬長運算排空，驗證恢復从樣本 offset4094（不是4095）開始。這修正持續錯位噪音，不代表長運算的短暫缺音已消除；實際 AppleWin 試聽仍需確認。

2026-09-27 match2 記憶體邊界修正：音效不能跨 VRAM／aux 邊界；載入器遇到跨界的完整音效先補零至邊界，再由 aux 起點載入，padding 不算播放長度。目前 VRAM 尾端56 bytes 留空，match2 完整位於 aux `$2C00..$757B`（18812 bytes），match3 位於 `$757C..$BFBF`（19012 bytes），預載池尾端剩64 bytes。原始 PCM 不變，`test_sound.py` 另驗證五個音效不跨記憶體域、aux 中完整 match2 與檔案相同。AppleWin `VERAAudio.h` 的 `FIFO_SIZE=4096`，實作最多容納4095 bytes，遊戲無法調大；目前起播已填滿，rate29／16-bit mono 約185ms。額外軟體 buffer 不會延長硬體 FIFO，剩餘爆音仍需檢查 refill 時序／音效中斷，不能宣稱跨界配置就是確定根因。

```powershell
python -m pip install py65 numpy
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
python -u vera\llvm\tools\test_music.py
python -u vera\llvm\tools\test_pcm_clock.py
```

`test_music.py`／`test_sound.py`／`test_pcm_clock.py`／`test_loading_progress.py` 都是直接對建置出的 65C02 binaries 執行，兩 slot 各跑一遍；VERA 的 PCM FIFO 以 rate 21、每 VSYNC 排空 `round(rate*48828.125/128/60)` 的模型模擬，`test_pcm_clock.py` 另以 `processorCycles`／1.023 MHz 在每條 instruction 後消耗 FIFO。這些是 model 比對，不是 AppleWin 或實機聽感驗證。

`test_mos.py` 會斷言 `disk_scores()` 等於本局打出的分數，所以必須用零高分的測試映像：把交付映像複製到 `llvm/build/test-zero.hdv`，再將其中的 `HISCORE.DAT` 12 bytes 設為 `FGH\x01` 加 8 個 0，然後 `$env:FREEGEMAS_TEST_DISK='...\llvm\build\test-zero.hdv'; python -u vera\llvm\tools\test_mos.py`。直接對保留真實高分的交付映像跑，會在「separate records」那關失敗；合成高分不得寫回交付映像。

model 已補上檔案層 MLI（2026-10-28）：`test_mos.py` 的 `Machine.mli()` 除了 block 讀寫（`$80`／`$81`）也實作 `GET_PREFIX $C7`、`OPEN $C8`、`READ $CA`、`WRITE $CB`、`SET_MARK $CE`、`GET_EOF $D1`、`CLOSE $CC`、`QUIT $65`，檔案內容直接取自 HDV catalog（storage 1／2／3 都跟隨 index block），WRITE 會回寫 `HISCORE.DAT` 的 data block。READ 越過 EOF 時回 status `$42` 但 carry 保持 clear（trampoline 的 `BCS fail` 因此可載入非 512 整數倍的 binary），其他錯誤 status 才設 carry。冷開機、Title、遊戲內、Options、滑鼠與音樂路徑的 harness 回歸因此重新全綠；測試同時更新為現行資產（`MUSIC.PCM` 串流、VRAM-only 8-bit 音效）。

測試直接執行建置的 65C02 binaries，VERA／MLI 是 instrumented model；不是實機測試。游標更新 9 bytes，合法交換／連鎖棋盤 bitmap 寫入量 0；單個測試棋步動畫間平均約 14.9k cycles，但配對／補牌前仍有較長處理間隔，不宣稱全程 60fps。`applewin_probe.ps1` 是測試中的 AppleWin keyboard／debugger／capture helper；測試用 HDV 放 `llvm/build/`，合成高分不得寫入交付映像。
