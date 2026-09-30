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
- `llvm/src/sound.c`／`sound.h`／`pcm_feed.S`：五個原作 PCM 音效（match1–3 已在建置時裁切為前 6640 bytes，總計 26912 bytes）完整預載到 VERA VRAM；播放不讀磁碟也不占 Aux RAM，以 port1 讀取補 FIFO，保存 port1 狀態，不動 PSG。
- `llvm/src/music.c`／`music.h`／`music_aux.S`：整首純音平滑 +9dB PSG（`music_pure_gained.psg`，56675 bytes）預載到 Aux RAM（`$0800–$BFFF`）與 Aux Language Card Bank 1/2（`$D000–$FFFF`），以 VSYNC 直接解析 raw PSG stream；16 聲道供音樂，保留 VERA port0 的位址／stride／control。
- `llvm/src/hiscore.h`：跨 segment 的兩模式高分與 dirty flag。
- `tools/build_assets.mjs`：以 `media/` 建立遊戲／標題 palette、RLE 場景和 sprites。
- `llvm/tools/build_hdv.py`：把程式與 RLE 場景打包至 800 KB ProDOS HDV，並建立跨 directory block 的檔案目錄。
- `generated/`：CMake 和 HDV builder 的輸入素材。不要只修改輸出 `.bin`／`.hdv`；先修正來源，再重新產生。

## 建置和交付

從 repo 根目錄執行：

```powershell
node vera\tools\build_assets.mjs
cmake -S vera\llvm -B vera\llvm\build
cmake --build vera\llvm\build --target disk --parallel 4
```

資產腳本需要 `ffmpeg` 和 `ffprobe`。LLVM-MOS SDK 預設在 `C:\dev\llvm-mos-sdk\install`；CMake cache 可用 `-DLLVM_MOS_SDK=...` 指定其他位置。HDV builder 使用 repo 內的 `vera/assets/800kb.hdv` 作為 ProDOS 基底，以腳本位置解析路徑，不再依賴 time-pilot checkout。模板最初複製自 TimePilot-IIvera 的同名映像，保留 ProDOS／CLOCK.SYSTEM 與 Bitsy Bye；不要把執行遊戲後的映像覆寫回模板。

產物：

- `llvm/build/freegemas.bin`／`freegemas4.bin`：slot 2／slot 4 遊戲程式。
- `llvm/build/title.bin`／`title4.bin`、`howto.bin`／`howto4.bin`、`option.bin`／`option4.bin`：各頁面程式。
- `freegemas.hdv`：可開機的 800 KB 測試映像。

AppleWin 重新建置前先卸載或關閉正在使用該 HDV 的模擬器。確認載入提示、slot 2 和 slot 4 路徑、模式切換及遊戲畫面後，再交付映像；不要只根據編譯成功宣稱實機驗證完成。

## VERA 顯示與 VRAM 配置

目前以 320×240、8bpp bitmap 顯示。Title 使用 DC_VIDEO `$51`；遊戲使用 `$71`（L0 + L1 + sprites）。L1 透明 tilemap 只在最上方 16px 覆蓋原 bitmap，防止補牌露出棋盤頂框。gem z-depth=2，游標／浮字／星芒 z-depth=3；sprite 8bpp 選項設在 attribute byte 1 的 bit 7。

| VRAM 範圍 | 用途 |
|---|---|
| `$00000–$12BFF` | 320×240 8bpp bitmap |
| `$12C00–$147FF` | 7 個 32×32 8bpp gem sprite patterns |
| `$14800–$18FFF` | PCM 預載池，18432 bytes |
| `$19000–$197FF` | 游標／選取框 32×32 patterns |
| `$19800–$198FF` | 4 張 8×8 星芒 patterns |
| `$19900–$1A2FF` | 10 個 16×16 浮字數字 patterns |
| `$1A300–$1A7FF` | PCM 預載池，1280 bytes |
| `$1A800–$1B7FF` | L1 64×32 tilemap，僅前兩列不透明 |
| `$1B800–$1CC3F` | 透明 tile 0 + 80 個頂部背景 tiles |
| `$1CC40–$1D83F` | 3 個 32×32 綠色 hint 框 patterns |
| `$1D840–$1F03F` | PCM 預載池，6144 bytes |
| `$1F040–$1F0BF` | 原作手形滑鼠游標，16×16／4bpp（128 bytes） |
| `$1F100–$1F8FF` | PCM 預載池，2048 bytes；HUD 背景已移主 RAM |
| `$1F9C0–$1F9FF` | VERA PSG registers（16 聲道，每聲道 4 bytes） |
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
- Options 的 Sound 控制原作 PCM 音效，page3 `$03F3` 為 ON／OFF；Music `$03F2` 控制已接入的遊戲 PSG 背景音樂，Fullscreen 固定 ON。Sound／Music 互不連動，Esc 回 Title 前同時停止；R 重新開始音樂。PSG 頻率換算依 AppleWin 17-bit phase：`Hz × 131072 / (25000000 / 512)`，不要誤用16-bit phase造成八度跑調。

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

2026-09-30 音效裁切與完整 Raw PSG 記憶體預載（`optimize` 分支）：
1. `build_sound.mjs` 將 `match1.pcm`、`match2.pcm`、`match3.pcm` 直接在建置階段截斷為 6640 bytes（約 0.30 秒），五個 PCM 總計由 65672 bytes 降至 26912 bytes，完全塞入 VERA VRAM 的 109 頁預載池（27904 bytes），徹底釋放 Aux RAM，並移除 `sound.c` 的 Aux RAM 讀取邏輯與 `MUSIC.CRV`。
2. `music.c` 與 `music_aux.S` 改為直接載入並播放 `MUSIC.PSG`（由 `music_midi_pure_smooth.psg` 經 `build_music.py` 套用 +9dB 增益產生的 `generated/music_pure_gained.psg`，56675 bytes，約 222 pages），不再使用 FGM2／Huffman 曲線壓縮（同時釋放 Main RAM 的曲線表空間）：
   - Logical pages `$08..$BF`（184 pages，46 KB）存入 Aux 48K RAM `$0800..$BFFF`。讀取時必須透過 `music_aux_init` 鏡像在 Main/Aux `$0300` 的 18-byte `music_reader` 切換 `$C003`/`$C002`（`RAMRD` 會連同 CPU instruction fetch 一起切換，不可直接在 Main RAM `.text` 內開啟 `$C003`）。
   - Logical pages `$C0..$CF`（16 pages，4 KB）透過 `ALTZP`（`$C009`）映射至 Aux Language Card Bank 2 `$D000..$DFFF`（`$C083`）。
   - Logical pages `$D0..$FF`（最多 48 pages，12 KB）透過 `ALTZP`（`$C009`）映射至 Aux Language Card Bank 1 `$D000..$FFFF`（`$C08B`）。
   - 存取 Aux LC 期間禁止在 `STA $C009` 與 `STA $C008` 之間使用 `PHA`/`PLA`（因為 `ALTZP` 會連硬體 Stack `$0100` 一起切到 Aux），且結束後必須執行 `LDA $C081; LDA $C081; LDA $C082` 還原全域 LC 狀態為 Bank 2 + ROM read / write-protect，避免 ProDOS 與 Mouse firmware 崩潰。
   - 修復 1:38（第 5916 frame / page `$C0`）音樂切斷問題：原本在搬移 loop 內每 byte 切換一次 `ALTZP` 導致 Aux LC 寫入狀態錯亂，且讀取時多讀一次 `$C083` 變成讀寫模式；修正為搬移 256 bytes 期間僅在外層單次切換 `ALTZP`，確保 46KB 之後的資料正確寫入與讀出，曲子可完整播完 2 分 03 秒。
3. `build_music.py` 音量再調增 20%（`MUSIC_GAIN` = 3.394，約 +10.6 dB），提升遊戲內 PSG 音樂聽感。

2026-09-30 修復 Endless Mode 進入 Game Over 後，按 R (Reset) 不會畫出分數 `0` 的問題。原因為 `upload_scene()` 雖清除了 VRAM 畫面，但 HUD 快取 `displayed_digits` 並未失效，導致 `draw_score()` 以為畫面上仍有之前的 `0` 而略過繪製。在處理 R 鍵時將 `displayed_digits` 陣列全數標記為 `0xFF`，強迫 `draw_score()` 重繪即可解決。

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

音量追調：使用者表示遊戲音樂太小聲，`build_music.py` 的 `MUSIC_GAIN` 由2提高至2.828427（較前版約+3dB，較原始PSG約+9dB），按硬體LUT取最近音量，超過511上限則封頂，沒有改音高／tempo／編排。此後音樂完整寄存器比對依新映射。

2026-09-27 音效預載重整（取代下方舊串流／FGM1 記憶體描述）：五份 raw PCM 共65672 bytes，27904 bytes 放上述四段 VRAM，餘37768 bytes 放 aux `$2C00..$BFFF`；播放不讀磁碟，原始 PCM byte 不變。音樂 FGM2 事件9014 bytes 放 aux `$0800..$2BFF`（配置9216 bytes），共用 Huffman 音量曲線9167 bytes 放 MAIN `$0800..$0BFF`、`$0E00..$1FFF` 及3535-byte BSS；避開磁碟 buffer `$0C00..$0DFF`。`music_aux_top` 決定音效 aux 起點；必須先 `music_init` 再 `sound_init`。aux reader 的 source 與 destination operands 都需同步 MAIN／AUX 鏡像，音效 cache 不可覆蓋音樂 cache。Gem patterns 改由 `GEM.PAT` 載入，不再重複佔用主程式7KB。HUD 背景備份移主 RAM，取消 Game Over VRAM 備份；Game Over 按 R 才在靜音後重載場景，正常消除／R 不重載場景。起播先填滿約4KB FIFO，後續每 tick 最多補1024 bytes（FULL 就停），避免慢消除時512-byte補充不足。兩 slot 五份音效完整 FIFO byte 比對、零 runtime 磁碟讀取及音樂7398-frame全部寄存器比對通過；音樂解碼平均4652、最高17324 CPU cycles/tick。主程式 `__bss_end=$AFF9`。VERA 仍需 CPU 補 FIFO，不是自動從 VRAM 播放；不能僅因預載宣稱所有實機 lag 消失。下方早期測量保留作歷史，不代表目前效能。

- [ ] 忠實原作音效：使用者拒絕 PSG 合成音。已改五個原作 OGG → 16-bit mono PCM（rate 29／11062.622 Hz），沿用原作 gain 0.3／0.25，刪除自創 Hint／Reset／Game Over 音效。`build_sound.mjs` 使用 ffmpeg 解碼／高品質 SWR 重採樣，輸出五個 `generated/*.pcm`，試聽 WAV 在 `llvm/build/`；disk target 自動轉換／打包。`sound.c` 啟動快取每檔 sapling index（最多 48 blocks），runtime 讀 512-byte buffer，`pcm_feed.S` 補 VERA FIFO，不動 VRAM／PSG。`test_sound.py` 兩 slot 比對五條完整 FIFO stream 與生成 PCM byte-for-byte，覆蓋 FULL／EMPTY、OFF／ON、MLI ZP、swap／Esc。**仍非 100% 原作**：取樣率／stereo、同時混音、Title／Options select 音效尚未完成；目前新音效中斷舊音效。1 MHz CPU 初步動畫平均約 31.5k cycles/frame，比無音效慢，需優先降低串流成本／預載取樣；不能宣稱效能、實機聲音已驗證。
- [x] 遊戲背景音樂：採使用者核准的純音版音符／平滑包絡，無 bass／鼓模擬／額外泛音；`tools/build_music.py` 將 `generated/music_midi_pure_smooth.psg` 打包成 `music.fgm`（41139 bytes／7398 frames），原生 PSG volume LUT 增益2倍，非直接串流核准的 WAV。VERA 波形／gain 與線性 preview 不同，不能聲稱聽感／响度相同；實機試聽仍待確認。Options Music 真正控制遊戲音樂，R 從頭、Esc 靜音；Title／Options 尚無音樂。與 PCM 音效互不占用同一路徑。
- 音樂記憶體：Apple IIe aux `$0800` 起載入整首 packed stream，範圍不得超過 `$BFFF`；主 RAM 增加512-byte載入buffer、92個block索引、256-byte頁cache。遊戲期間音樂零磁碟讀取；缺aux RAM時安全停用。`music_aux.S` 把18-byte reader鏡像至MAIN／AUX `$0300..$0311`，RAMRD會連instruction fetch一起切換，必須鏡像！source page operand `$0307` 兩份同步，切換期間SEI，RAMWRT保持MAIN；stack/ZP留MAIN。loader下一次launch覆蓋MAIN `$0300`，所以Esc先music_stop，再回loader。不要改ProDOS vectors `$03D0`起或page3設定。
- `test_music.py` 兩slot逐frame比對7398 frames全部寄存器（除增益映射外相同音符），檢查loop／ON／OFF、graphics port保存、無aux保護與PCM互不干擾。模型音樂平均約2.8k cycles/tick、最高約14.9k；既有PCM disk refill仍使整體動畫超過1MHz 60Hz預算，不能宣稱全遊戲60fps或已消除所有音訊雜音。
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
python -m pip install py65
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
```

測試直接執行建置的 65C02 binaries，VERA／MLI 是 instrumented model；不是實機測試。游標更新 9 bytes，合法交換／連鎖棋盤 bitmap 寫入量 0；單個測試棋步動畫間平均約 14.9k cycles，但配對／補牌前仍有較長處理間隔，不宣稱全程 60fps。`applewin_probe.ps1` 是測試中的 AppleWin keyboard／debugger／capture helper；測試用 HDV 放 `llvm/build/`，合成高分不得寫入交付映像。
