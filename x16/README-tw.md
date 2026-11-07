# Freegemas for Commander X16

[English](README.md) | 繁體中文

這是 Freegemas 的 Commander X16 移植版，使用
[LLVM-MOS SDK](https://github.com/llvm-mos/llvm-mos-sdk) 編譯成 65C02 原生
程式。畫面沿用 Apple //e VERA 版的素材與 `media/` 原始資產，但執行時使用
X16 的 VERA（`$9F20`）、KERNAL I/O 與鍵盤／搖桿 API。

程式分為常駐 `$2000` 的 loader，以及載入 `$3000` 的 intro、title、
How to Play、Options 與遊戲 overlay。畫面是 320x240、8bpp 的 VERA bitmap，
寶石與特效使用硬體 sprites。音樂是 **ZCM 串流**：8,011 Hz、單聲道、
signed 16-bit PCM，透過 KERNAL `MACPTR` 從 `hostfs/music.zcm` 讀取。五個短
音效是 signed 16-bit PCM，預載在 banked RAM，並與音樂混入同一個 VERA FIFO。

## 需求

- Windows PowerShell 7（`pwsh`）、Python 3 與 NumPy、LLVM-MOS SDK。
  SDK 預設在 `C:\dev\llvm-mos-sdk\install`，可用 `-Sdk` 指定其他位置。
- `assets/music.zcm`（2,024,422 bytes，126.35 秒），已納入版控；一般建置
  只需將它複製到 `hostfs/`，不需要重新轉檔。
- **x16emu r49（Pyrite）或更新版本**。鍵盤使用 R49 的 `kbdbuf_get`
  extapi（A=18，`$FEAB`），舊 ROM 不保證可用。
- 512 KiB banked RAM：場景 chunk 使用 bank 30-39，音效 bank 24-28，HUD 快取
  bank 20；音樂不需要載入 banked RAM。

不需要 `ffmpeg`；音效 builder 使用 Python 的 `soundfile` 與 `soxr`。音樂的
重新產生方式見下文。

## 建置

在這個目錄執行：

```powershell
cd C:\dev\freegemas\x16
.\build.ps1
```

或在 repo 根目錄執行：

```powershell
powershell -ExecutionPolicy Bypass -File .\x16\build.ps1
```

產物：

- `hostfs/`：可直接執行的 HostFS 目錄（程式、場景、PCM 音效、
  `music.zcm`）。
- `build/`：暫時性的 `.bin`、`.map` 與中介檔。

`build.ps1` 會先刪除並重建兩個輸出目錄，因此全新建置不會保留舊的
`hiscore.dat`。

## 執行

```powershell
C:\dev\emu\x16emu\x16emu.exe `
  -prg C:\dev\freegemas\x16\hostfs\boot.prg `
  -run `
  -capture `
  -fsroot C:\dev\freegemas\x16\hostfs `
  -scale 2
```

加上 `-capture`（或在視窗開啟後按 `Ctrl+M`）讓 x16emu 接收滑鼠；
遊戲會自己畫指標，因此宿主游標會隱藏。

要擷取聲音可加上 `-wav C:\dev\freegemas\x16\out.wav`。HostFS 檔名為小寫且
區分大小寫。

## 瀏覽器版 web player

[`web/`](web/) 是獨立的瀏覽器版播放頁。它使用官方 x16-emulator
WebAssembly r49，並載入同一份 `hostfs/`，因此瀏覽器裡跑的是真正的 X16
KERNAL 與 `boot.prg`：

```powershell
cd C:\dev\freegemas\x16\web
.\build.ps1
python -m http.server 8123 --directory .\dist
```

開啟 <http://127.0.0.1:8123/>；加上 `?auto=1` 會自動開機。建置需求、
固定的模擬器 checksum、離線快取與「瀏覽器內高分只存活於本次頁面」的
說明見 [`web/README.md`](web/README.md)。

## 操作

- **Title**：方向鍵或滑鼠移動指標；Space、Enter 或滑鼠左鍵開啟項目。
- **How to Play**：任意鍵或滑鼠左鍵返回 Title。
- **Options**：方向鍵或滑鼠選擇；Space／左鍵切換 Music（ZCM/Off）、
  Sound（On/Off）或選擇 Back；Esc 返回 Title。
- **遊戲**：方向鍵或滑鼠移動游標；Space／左鍵選取寶石，再以相鄰方向或左鍵交換。
  畫面上的 Show hint、Reset game、Exit 也可直接用滑鼠點擊。`H` 顯示提示，
  `R` 重新開始，Esc 返回 Title。
- **Game Over**：`R` 重新開始；Esc 返回 Title 並儲存待寫入的高分。

X16 鍵盤搖桿對應的方向鍵與 A/B 也可操作（方向鍵、`X`/`Ctrl` 與
`Z`/`Alt` 分別對應 A/B）。目前只輪詢 joystick 0。

## 音樂與音訊路徑

- `media/music.ogg` 先解碼、downmix 成單聲道，使用 `soxr` VHQ 重取樣為
  **8,010.864 Hz**，乘上 `0.55`，再存成 ZCM 內的 signed 16-bit PCM。8-byte
  標頭是 `00 00 00 <24-bit sample count> 2F 15`：geometry `0x2F` 代表
  16-bit mono，VERA rate `21`。輸出的 `assets/music.zcm` 是 2,024,422 bytes，
  頭尾各 40 samples 的 fade 讓循環不會爆音。
- `music.c` 在啟動 I/O 完成後開啟 ZCM，用 `MACPTR` 讀取（跳過 8-byte
  標頭），所以 2 MB 音樂從不佔用 banked RAM。VERA FIFO 先在 clock 暫停時
  預填到滿（4 KB），之後依照 FIFO 實際空位需求補資料，必要時混入音效；
  串流維持開啟。播到 EOF 時關閉串流並靜音（音樂長度超過一局 Timetrial）。
- 五個音效由 `tools/build_effects.py` 從原始 OGG 重建：soxr VHQ 轉成
  8,010.864 Hz、mono、峰值正規化，存成 little-endian signed 16-bit PCM。
  每個音效各自預載到 bank 24-28 的 `$A000`，所以 4,806 bytes 的 match 音效
  不會跨過 `$BFFF` 邊界而截斷 MATCH3。`music.c` 的 `mix_effect16()` 在
  音樂 RAM buffer 裡做完整 16-bit 相加與 clip；`pcm_copy` 再逐 byte 寫入
  FIFO，並保留沒送完的尾巴到下一 frame。VERA 使用 16-bit mono、volume 10
  （`0x2A`）。
- 音效 stage 改為 **`$1000` 的 320 bytes／160 samples**。每個 music frame
  最多會送來 268 bytes／134 samples；舊的 80-byte（40-sample）stage 只混到
  每個音效的前段，剩下的 sample 只有音樂，這正是 match 音效被切碎、沙啞的
  原因。現在一個 frame 的完整音效都會以 8,010.864 Hz 混入。
- X16 場景另外移除計時器面板的深藍色 `88:88` 殘影，並把 Show hint／
  Reset game／Exit 按鈕上那道硬的漸層橫線整平。計時器改用
  `media/fuentelcd.ttf` 產生的 12×18 LCD 字形，對齊到 x=75 的右緣；前景
  數字與 LED 高度一致，不會再留下比較大的黑色殘影。
- **音訊雜音原因都已修正。** `MACPTR` 只在 **X** 回傳實際讀到的 byte 數；
  舊程式把 **Y** 也當成 count 的高 byte，會播放 staging buffer 裡的殘留
  byte。舊 `pcm_copy` 只在開頭檢查一次 FIFO full，之後仍盲目寫入而丟 byte；
  現在每個 byte 都檢查，剩下的 byte 會保留到下一 frame 重送。舊音效是
  8-bit、峰值又低，只剩少數有效位元，聽起來沙啞；現在改成 16-bit。
  修正後擷取的原生 WAV 在前 20 秒與 `assets/music.zcm` 相關性為 **1.0**，
  沒有靜音斷點，match 後也仍與音樂相關。
- Music On/Off 是 Options 設定。即使 Music 關閉，串流仍會開啟但樣本清零，
  因此兩種模式共用同一套 16-bit 音效 mixer；Music Off 時只會聽到音效。
  按 `R` 只重設盤面與音效，**不重新開啟串流**（遊戲中重開 HostFS channel
  會讓後續讀取損壞）；Esc／Exit 會停止音樂並移除 VSYNC IRQ。
- 鍵盤使用 `kbdbuf_get`，因此音樂使用的 KERNAL channel 不會改寫鍵盤讀取。
  遊戲同時接受大寫與小寫的 `H`、`R`。

重新產生音樂與音效素材：

```powershell
python .\tools\build_music_zcm.py
python .\tools\build_effects.py
```

兩個 builder 都需要 Python 的 `soundfile`、`soxr` 與 NumPy。音樂 builder
覆寫 `assets/music.zcm`；音效 builder 覆寫 `hostfs/` 裡五個 16-bit
`*.pcm`。之後執行 `.\build.ps1` 重建 `hostfs/`；`build.ps1` 也會自動呼叫
兩個 builder。

## 高分與檔案

高分存在 `hostfs/hiscore.dat`：12 bytes 的 `FGH` version 1 標頭加上兩個
little-endian `uint32`。Game Over 後返回 Title，或從 Title 離開時寫入。
全新建置不會預設任何分數。

loader 以 HostFS 小寫檔名讀取所有素材，因此整個 `hostfs/` 目錄可直接
複製到其他 HostFS 根目錄。

## 驗證狀態

目前只在 **x16emu r49（Pyrite）** 驗證，**尚未在實機 Commander X16
測試**：

- 滑鼠指標可繪製，且已加入 KERNAL `mouse_scan`／`mouse_get` 輪詢；但
  合成宿主滑鼠移動**沒有**推動模擬器指標，實機／`-capture` 滑鼠移動仍待驗證；
- 開機、intro、title、How to Play、Options、Timetrial 與 Endless 載入；
- 原生 x16emu 遊戲迴圈可持續倒數、棋盤可互動；舊的 FIFO 半個 sample
  分裂路徑已改為一次寫入完整 16-bit sample pair；
- 33.7 秒原生 WAV 仍在 **17.1 秒出現一次 0.1 秒寬頻爆音**（peak 0.56）。
  這比先前連續爆音大幅改善，但**整首音樂尚未完全乾淨**；
- 16-bit 音效 mixer 仍有接上，但**尚未做真人耳朵驗證**；合成滑鼠測試
  也未實際觸發音效路徑。下面的音效／時間說明明確不算聽感驗證。
- 計時到 0、Game Over 面板、高分更新，以及返回 Title 時寫出高分檔；
- 高分讀回：以種子 `hiscore.dat` 寫入 42 後，Options 顯示
  `Timetrial: 42`；
- Title 的 Exit 先以 `CINT ($FF81)` 還原 KERNAL 文字畫面，再呼叫
  `enter_basic`，因此模擬器會顯示 `READY.`，不會停留在 title bitmap；
- 離開／返回各 overlay 後 bitmap 沒有殘影或錯色；
- 獨立 [`web/`](web/) player 已用 headless Chrome 搭配官方
  x16emu WebAssembly r49 驗證：以同一份 `hostfs/` 顯示 title 與
  Timetrial，並包含新的計時器／按鈕場景修正。這是瀏覽器／模擬器驗證，
  不是實機測試。

`R` 重設盤面與音效時串流維持不中斷，已在原生 x16emu 走過；五個音效共用
同一套音訊路徑。這一輪沒有把完整 126.35 秒播到 EOF；EOF 會關閉串流並
靜音。

實機仍需驗證，特別是 16-bit PCM 音量、音樂／音效平衡、音訊時序、
搖桿／手把對應與完整循環。本移植目前只在 **x16emu r49 與瀏覽器內的
x16emu WebAssembly r49** 驗證，**尚未在實體 Commander X16 上測試**。
