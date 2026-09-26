# Apple II + VERA FPGA 建置工具鏈參考文件

> 本文件濃縮自 `C:\dev\veratest` 專案的完整原始碼，可直接照抄使用。
> 目標：**寫一個 6502 組語遊戲 → 編譯成 raw binary → 打包成可開機 ProDOS 140KB 映像 (`*.po`) → 由 `STARTUP` (Applesoft BASIC) 選單啟動**。

---

## 0. 一句話流程

```
game.asm ──(asm6502.mjs)──▶ raw bytes (Uint8Array, 無檔頭)
startup.bas ──(applebasic.mjs)──▶ Applesoft token stream (載入位址 $0801)
        │
        ▼
veratest.mjs ──▶ 讀入 assets/ProDOS 2.4.3.po 底稿 ──▶ addFile(...) ──▶ veratest.po (140KB 可開機)
        │
        └──▶ generatePreviewPng() ──▶ veratest.png (560x384 預覽圖)
```

**觸發方式**：`build.bat veratest`（或 `node src\veratest\veratest.mjs`）。
**輸出**：`veratest.po`（140KB 可開機 ProDOS 2.4.3 磁碟映像）＋ `veratest.png`（預覽圖）。

---

## 1. 6502 組譯器 API (`src/asm6502.mjs`)

這是自製的 **兩-pass 6502 組譯器**，零依賴、純 Node.js。對外暴露兩個函式。

### 1.1 `assemble6502(lines, startAddress = 0x2000, extraLabels = {})`

```js
import { assemble6502 } from "asm6502.mjs"
const bytes = assemble6502([
  "START:",
  "    LDA #$00",
  "    STA $C200",        // 直接用絕對位址
  "    RTS",
], 0x2000)
// bytes 是 Uint8Array（純 bytes，無 ProDOS 檔頭）
```

- `lines`：字串陣列，每行一條組語。
- `startAddress`：**組譯起始 PC**，預設 `$2000`。`ORG` 指令會被忽略（見 §1.3）。
- `extraLabels`：預先注入的 label 表（`{ NAME: value }`）。
- **回傳**：`Uint8Array`，純編譯後 bytes。

### 1.2 `assembleAsmFile(srcDir, filename, slot = 2, startAddress = 0x2000, extraLines = [])`

這是**真正用來組譯 `.asm` 檔**的函式（veratest.mjs 都用它）：

```js
import { assembleAsmFile } from "asm6502.mjs"
const code = assembleAsmFile(veratestDir, "game.asm", 2, 0x2000)
// 參數：源檔目錄, 檔名, slot(2或4), 載入位址
```

它做的事：
1. 讀檔、支援 `.include` / `include` 遞迴展開（`include "file.asm"`）。
2. **自動注入 `VERA_BASE`**：`VERA_BASE = $C000 + slot * $100`。
   - `slot = 2` → `VERA_BASE = $C200`
   - `slot = 4` → `VERA_BASE = $C400`
   - 並自動載入同目錄（或上層、`src/`）的 `vera.inc`。
3. 把注入行 + `vera.inc` + 源檔 + `extraLines` 合併後呼叫 `assemble6502`。

> **slot 與位址**：組譯時就鎖定 slot。要同時支援 Slot 2 與 Slot 4，需**組兩次**（slot=2 與 slot=4），產生兩個 binary（如 `SPRITE.BIN` / `SPRITE4.BIN`），由 BASIC 探測後擇一啟動。

### 1.3 支援的 Directive / 語法

| Directive | 用法 | 說明 |
|---|---|---|
| `* = $2000` / `ORG $2000` | `* = $2000` | **被忽略**（no-op）。載入位址由 addFile 的 aux 欄位指定，不在組語內生效。 |
| `LABEL EQU expr` / `LABEL = expr` | `VERA_BASE = $C200` | 常數定義。支援 `LABEL = VERA_BASE + $03`。 |
| `HEX` | `HEX 00 1F A0` | 十六進位 bytes（空格分隔）。支援 `$xx`、`0x`。 |
| `!BYTE` / `.BYTE` | `!BYTE 1,2,3` | 十進位 bytes。支援 label、`<`/`>`、`#` 前綴。 |
| `!WORD` / `.WORD` / `DW` / `DA` | `!WORD $2000` | 16-bit little-endian（低位在前）。 |
| `ASC` | `ASC "HELLO"` | ASCII 字串，**保留內部空白**（用於對齊表頭）。 |
| `label:` | `START:` | 標籤定義（可與指令同行）。 |
| 註解 | `;` 或 `//` | 行內註解（`//` 與 `;` 都會被剝掉）。 |

### 1.4 運算式求值（支援範圍有限）

`resolveVal` 支援：
- `$hex`、`0xhex`、十進位。
- label 名稱（在 labels 表內查詢）。
- `+` / `-` 一個二元運算（如 `VERA_BASE + $03`、`LABEL - $10`）。
- `<`（取低位 byte）、`>`（取高位 byte）、`#`（立即值）前綴。

**限制（重要）**：
- **不支援 16-bit 算術運算式**（只能 `+`/`-` 一個常數，不能 `A*2+B`、不能 `(expr)`、不能 `>>`）。
- **不支援 macro、條件組譯**（無 `IFDEF`/`IF`/`REPEAT`）。
- 分支（`BNE`/`BEQ`/`BPL`/`BMI`/`BCC`/`BCS`/`BVC`/`BVS`）**只支援 +-127 範圍內**，超出會 throw。
- `LDA/STA/LDX/...` 的定址模式由 operand 形式推斷：`#`=立即、`$xx`(≤3字元)=ZP、`$xxxx`=絕對、`,X`/`,Y`=絕對索引、`(xx),Y`=間接索引。
- **已知 bug（見 docs/vera-session.md §5.5.1/5.5.5）**：`CPX`/`CPY` 只有立即模式；`AND`/`ORA`/`EOR` 的 `label,Y` 定址模式可能被誤判（盡量避免用 `AND label,Y`）。

### 1.5 組譯輸出格式 —— 重要結論

- **純 bytes**：`Uint8Array`，**沒有 ProDOS 檔頭**（不像 llvm-mos 會輸出 `00 20 DC 09`）。
- **載入位址不內嵌在 binary 內**：由映像建置器 addFile 的 `aux` 欄位（見 §5）指定。
- **入口點**：binary 開頭即為 `START:` 的第一個指令。`BRUN` 會自動跳到載入位址（$2000）執行。**不需要**手寫 `JMP $2000`。

---

## 2. VERA 暫存器偏移（`src/vera.inc`）

`VERA_BASE` 由組譯器注入：Slot 2 = `$C200`、Slot 4 = `$C400`。以下全部以 `VERA_BASE + $xx` 表示。

| 偏移 | 常數 | 說明 |
|---|---|---|
| `+$00` | `VERA_ADDR_L` | VRAM 位址 [7:0] |
| `+$01` | `VERA_ADDR_M` | VRAM 位址 [15:8] |
| `+$02` | `VERA_ADDR_H` | VRAM 位址 [19:16] + Stride/Decr |
| `+$03` | `VERA_DATA0` | 資料埠 0（自動遞增） |
| `+$04` | `VERA_DATA1` | 資料埠 1（獨立指標） |
| `+$05` | `VERA_CTRL` | Bit0=埠選擇(0=Port0,1=Port1), Bit7=Reset |
| `+$06` | `VERA_IEN` | 中斷致能（bit0=VSYNC, bit1=Line, bit2=Sprite Collision） |
| `+$07` | `VERA_ISR` | 中斷狀態（bit0=VSYNC 等） |
| `+$08` | `VERA_IRQ_L` | 掃描線 IRQ 目標 [7:0] |
| `+$09` | `VERA_DC_VID` | Display Composer 視訊控制（見 §3.2） |
| `+$0A` | `VERA_DC_HSC` | 水平縮放（128=1.0x, 64=2.0x） |
| `+$0B` | `VERA_DC_VSC` | 垂直縮放（128=1.0x, 64=2.0x） |
| `+$0C` | `VERA_DC_BOR` | 邊框色索引 |
| `+$0D` | `VERA_L0_CFG` | Layer 0 設定與色深 |
| `+$0E` | `VERA_L0_MAP` | Layer 0 Tilemap 基底位址 |
| `+$0F` | `VERA_L0_TIL` | Layer 0 Tile/Bitmap 基底位址 |
| `+$10..$13` | `VERA_L0_HSC_L/H`, `VERA_L0_VSC_L/H` | Layer 0 捲動 |
| `+$14..$1A` | `VERA_L1_CFG/MAP/TIL/HSC/VSC` | Layer 1（同 Layer 0 結構） |

**Apple II softswitch**（vera.inc 內）：

| 位址 | 常數 | 說明 |
|---|---|---|
| `$C000` | `KBD_DATA` | 讀鍵盤（bit7=1 表示有鍵） |
| `$C010` | `KBD_STROBE` | 清除鍵盤 strobe |

---

## 3. VERA 暫存器驅動的組語慣用法（從 demo 提取）

### 3.1 設定 VRAM 位址（三個暫存器 + Data Port）

```
VERA_ADDR_L  = VRAM 位址 [7:0]
VERA_ADDR_M  = VRAM 位址 [15:8]
VERA_ADDR_H  = bits[3:0]=位址[19:16], bit[4]=DECR(遞減), bits[7:5]=自動遞增 Stride
```

寫資料到 VRAM：
```asm
LDA #$00
STA VERA_ADDR_L
STA VERA_ADDR_M        ; 例：位址 $00000
LDA #$10               ; Stride=+1, 位址[19:16]=0 (Bank 0)
STA VERA_ADDR_H
; ... 然後對 VERA_DATA0 連續寫入，每次自動 +1
STA VERA_DATA0
```

**Bank / Stride 速查**（寫入 `VERA_ADDR_H` 的值）：

| 值 | 效果 |
|---|---|
| `$10` | Bank 0（$00000..$0FFFF），Stride +1 |
| `$11` | Bank 1（$10000..$1FFFF），Stride +1 |
| `$01` | Bank 1，Stride 0（**單筆寫**，用於 PSG/暫存器寫入，不自動遞增） |

### 3.2 顯示合成器視訊控制 `VERA_DC_VID`

專案實際使用的編碼（demo 均以此運作）：

| 值 | 效果 |
|---|---|
| `$00` | **關閉 VERA 視訊**（切回 Apple II 原生文字螢幕；退出前必做） |
| `$01` | 開啟 VGA 輸出（僅輸出） |
| `$11` | VGA 輸出 + Layer 0（mode7 / mode4 用） |
| `$41` | VGA 輸出 + Sprites（sprite demo 用） |
| `$71` | VGA + Layer 0 + Layer 1 + Sprites（sonic 用） |

> 註：`vera.inc` 檔頭註解寫的是 X16 標準佈局（bit2=L0, bit3=L1, bit0=Sprites），但**本埠實際以 bit4=L0、bit5=L1、bit6=Sprites、bit0=VGA 輸出**運作；以 demo 使用的 `$11/$41/$71` 為準。

### 3.3 Palette 載入（VRAM `$1FA00`，512 bytes = 256 色 × 2 bytes）

每色 2 bytes little-endian 12-bit RGB：`[G4 B4] [0 R4]`。
```asm
LDA #$00
STA VERA_ADDR_L
LDA #$FA
STA VERA_ADDR_M
LDA #$11               ; Bank 1, Stride +1 ($1FA00)
STA VERA_ADDR_H
; 每色寫兩 bytes：低位 = 綠色高半+藍色高半，高位 = 紅色高半
LDA #$00
STA VERA_DATA0        ; 色0 黑
STA VERA_DATA0
LDA #$FF
STA VERA_DATA0        ; 色1 白 ($0FFF)
LDA #$0F
STA VERA_DATA0
; ... 依此寫滿 512 bytes
```

### 3.4 Sprite 圖案上傳（4bpp 16x16 = 128 bytes，VRAM `$10000`）

```asm
LDA #$00
STA VERA_ADDR_L
STA VERA_ADDR_M
LDA #$11               ; Bank 1, Stride +1 ($10000)
STA VERA_ADDR_H
LDX #$00
LOAD_SHAPE:
    LDA SPR_PIXELS,X
    STA VERA_DATA0
    INX
    CPX #$80           ; 16x16 4bpp = 128 bytes
    BNE LOAD_SHAPE
```

### 3.5 Sprite Attribute Entry —— 8-byte 佈局（VRAM `$1FC00 + n*8`）

每個 sprite 佔 **8 bytes**，寫法依序如下：

| Byte | 欄位 | 內容 |
|---|---|---|
| `+0` | `ADDR_L` | 圖案位址 [7:0]（圖案基底通常 `$10000` → 此欄 `$00`） |
| `+1` | `ADDR_H` | bits[7:3]=位址[12:8]，**bit[2]=8bpp**(0=4bpp,1=8bpp)，bits[1:0]=0。4bpp 16x16 用 `$08`（`$10000>>5=$0800`） |
| `+2` | `X_LO` | X 座標 [7:0] |
| `+3` | `X_HI` | bits[1:0]=X[9:8]，bits[7:2]=0 |
| `+4` | `Y_LO` | Y 座標 [7:0] |
| `+5` | `Y_HI` | bits[1:0]=Y[9:8]，bits[7:2]=0 |
| `+6` | `ATTR` | bit7=VFLIP, bit6=HFLIP, bit5=2x高, bit4=2x寬, **bits[3:2]=Z-depth**(0=後..3=前), bits[1:0]=palette offset。**`$0C`=Z-depth 3(最前)** |
| `+7` | `DIM` | 尺寸/層（見下表） |

**Byte 7 (DIM) 在本埠的實際編碼**（由 demo 反推，可直接照抄）：

| 值 | 尺寸 | 來源 |
|---|---|---|
| `$50` | 16x16 | sprite.asm（16 個外星精靈） |
| `$A0` | 32x32 | sonic.asm Sprite 0（身體） |
| `$20` | 16x32 | sonic.asm Sprite 1（耳朵） |

對應規則：**bit7=寬度 32px(0=16px)、bit5=高度 32px(0=16px)**、bits[3:0]=Layer(0=Layer0)。bits[6]/[4] 為 16px 旗標，硬體實務上 bit7/bit5 已足夠（bits[6:4] 可視為 2-bit 尺寸碼：00/01=16px、10=32px）。

**初始化 16 個 sprite 的最小迴圈**：
```asm
LDA #$00
STA VERA_ADDR_L
LDA #$FC
STA VERA_ADDR_M
LDA #$11               ; Bank 1, Stride +1 ($1FC00)
STA VERA_ADDR_H
LDX #$00
INIT_SPR:
    LDA #$00           ; ADDR_L
    STA VERA_DATA0
    LDA #$08           ; ADDR_H (4bpp, $10000>>5)
    STA VERA_DATA0
    LDA SPR_X_LO,X     ; X_LO
    STA VERA_DATA0
    LDA SPR_X_HI,X     ; X_HI
    STA VERA_DATA0
    LDA SPR_Y_LO,X     ; Y_LO
    STA VERA_DATA0
    LDA SPR_Y_HI,X     ; Y_HI
    STA VERA_DATA0
    LDA #$0C           ; ATTR: Z-depth=3
    STA VERA_DATA0
    LDA #$50           ; DIM: 16x16
    STA VERA_DATA0
    INX
    CPX #$10
    BNE INIT_SPR
```

**更新單一 sprite 的 X/Y**（重設位址到該 sprite 的 `+2` 欄位）：
```asm
TXA
ASL
ASL
ASL                  ; X * 8 = sprite 偏移
CLC
ADC #$02             ; +2 = X_LO 欄位
STA VERA_ADDR_L
LDA #$FC
STA VERA_ADDR_M
LDA #$11
STA VERA_ADDR_H
LDA SPR_X_LO,X
STA VERA_DATA0
LDA SPR_X_HI,X
STA VERA_DATA0
LDA SPR_Y_LO,X
STA VERA_DATA0
LDA #$00
STA VERA_DATA0
```

### 3.6 Tilemap Entry —— 2-byte 佈局（mode4 8bpp）

每格 **2 bytes**：
```asm
CLR_MAP:
    LDA #$00            ; 低 byte = tile 編號
    STA VERA_DATA0
    LDA #$00            ; 高 byte = 屬性 ($00)
    STA VERA_DATA0
```

- **byte 0**：tile 編號（8bpp 8x8 tile）。
- **byte 1**：屬性。bit0=水平翻轉、bit1=垂直翻轉、bits[3:2]=palette offset（僅 4bpp 用）。8bpp 全彩模式通常 `$00`。

**Layer 0 設定**（mode4 8bpp 256 色）：
```asm
LDA #$13            ; 8bpp 色深
STA VERA_L0_CFG
LDA #$00            ; Map base $00000
STA VERA_L0_MAP
LDA #$80            ; Tile base $10000（8x8 tile → 暫存器存位址>>9）
STA VERA_L0_TIL
```

### 3.7 PSG Voice Register —— 4-byte 佈局（VRAM `$1F9C0 + n*4`）

16 voices，每 voice 4 bytes。Voice 基底：V1=`$1F9C0`, V2=`$1F9C4`, V3=`$1F9C8`, V4=`$1F9CC`。

| Byte | 欄位 | 內容 |
|---|---|---|
| `+0` | `freq_lo` | 頻率低 byte（12-bit 頻率）。`freq = round(f × 131072 / 48828.125)` |
| `+1` | `freq_hi` | 頻率高 byte（bits[3:0]=freq[11:8]） |
| `+2` | `ctrl` | **bit7=Right 致能, bit6=Left 致能, bits[5:0]=音量(0..63)**。`$7F`=左聲道最大音量、`$BB`=右聲道、`$FE`=立體聲 |
| `+3` | `wave` | **bits[7:6]=波形**：`00`=Pulse(脈衝, 佔空比在 bits[5:0])、`01`=Sawtooth、`10`=Triangle、`11`=Noise |

**寫一個 voice**（PSG 用 `Stride 0` 單筆寫）：
```asm
LDA #$C0
STA VERA_ADDR_L
LDA #$F9
STA VERA_ADDR_M
LDA #$01               ; Bank 1, Stride 0（單筆寫, 不自動遞增）
STA VERA_ADDR_H
LDA LEAD_LO,Y          ; freq_lo
STA VERA_DATA0
LDA LEAD_HI,Y          ; freq_hi
STA VERA_DATA0
LDA #$7F               ; ctrl: Left 致能 + 音量 63
STA VERA_DATA0
LDA #$10               ; wave: Pulse, 佔空比 16/64 = 25%
STA VERA_DATA0
```

**波形值速查**：

| `wave` byte | 波形 |
|---|---|
| `$10` | Pulse 25% 佔空比 |
| `$40` | Sawtooth |
| `$80` | Triangle |
| `$C0` | Noise |

**清除 PSG（退出前必做）**：對 `$1F9C0` 連續寫 4×N 個 `$00`，或對每個 voice 寫 4 個 `$00`（見 spritesnd.asm 退出段）。

### 3.8 60Hz VSYNC IRQ 設定

**關鍵**：Apple II 的 6502 硬體 IRQ 向量在 `$FFFE/$FFFF`（指向 ROM IRQ handler）。ROM handler 會 **經由 `$03FE/$03FF` 間接跳轉**（`JMP ($03FE)`）。所以軟體要 hook 的是 **`$03FE/$03FF`**，不是 `$FFFE`。

**開啟 IRQ（sonic.asm / slideshow.asm）**：
```asm
START_MUSIC_IRQ:
    SEI
    LDA $03FE
    STA OLD_IRQ_L
    LDA $03FF
    STA OLD_IRQ_H
    LDA #<SONIC_IRQ_HANDLER
    STA $03FE
    LDA #>SONIC_IRQ_HANDLER
    STA $03FF
    LDA #$01
    STA VERA_ISR          ; 清除/回應待處理 VSYNC
    STA VERA_IEN          ; 致能 bit0 = VSYNC
    CLI
    RTS
```

**關閉 IRQ（退出前）**：
```asm
STOP_MUSIC_IRQ:
    SEI
    LDA #$00
    STA VERA_IEN          ; 關 VSYNC
    LDA OLD_IRQ_L
    STA $03FE
    LDA OLD_IRQ_H
    STA $03FF
    CLI
    RTS
```

**IRQ handler（必須保存/還原暫存器與 VERA 位址暫存器）**：
```asm
SONIC_IRQ_HANDLER:
    PHA
    TXA
    PHA
    TYA
    PHA
    LDA VERA_ISR
    AND #$01
    BEQ IRQ_EXIT          ; 非 VSYNC
    LDA #$01
    STA VERA_ISR          ; 回應 VSYNC
    ; 保存 foreground 用的 VERA 位址暫存器
    LDA VERA_ADDR_L
    STA IRQ_ADDR_L
    LDA VERA_ADDR_M
    STA IRQ_ADDR_M
    LDA VERA_ADDR_H
    STA IRQ_ADDR_H
    JSR TICK_MUSIC        ; 你的 60Hz 工作
    ; 還原 VERA 位址暫存器
    LDA IRQ_ADDR_L
    STA VERA_ADDR_L
    LDA IRQ_ADDR_M
    STA VERA_ADDR_M
    LDA IRQ_ADDR_H
    STA VERA_ADDR_H
IRQ_EXIT:
    PLA
    TAY
    PLA
    TAX
    PLA
    RTI
```

> 注意：handler 內**不能呼叫 ProDOS MLI**（disk I/O），且必須保存/還原 `VERA_ADDR_L/M/H`，避免與主迴圈的 VRAM 寫入互相干擾。

### 3.9 各 demo「初始化 → 畫一幀」最小骨架

**Sprite（sprite.asm）**：
```
START:
  VERA_CTRL=0 (Port0)
  DC_VID=0 (先關視訊) ; DC_BOR=0 ; L0_CFG=0 ; L1_CFG=0
  DC_HSC=$40 ; DC_VSC=$40          ; 2x 縮放
  CLR_64K (Bank0 與 Bank1)          ; 清空全部 VRAM
  載入 Palette @$1FA00
  初始化 16 個 sprite attribute @$1FC00
  上傳 16x16 圖案 @$10000
  DC_VID=$41                        ; 開啟 VGA+Sprites
LOOP:
  更新每個 sprite 的 X/Y（重設位址到 +2）
  檢查鍵盤 $C000 → 有鍵則 DC_VID=0 ; RTS
  延遲迴圈 ; JMP LOOP
```

**Mode 7 全彩 bitmap（mode7.asm）**：
```
START:
  VERA_CTRL=0
  DC_VID=$11 ; DC_HSC=$40 ; DC_VSC=$40
  L0_CFG=$07 (8bpp bitmap) ; L0_MAP=0 ; L0_TIL=0 ; 捲動全 0
  載入 palette @$1FA00 (32 bytes)
  設 VRAM 位址 $00000, Stride+1
  RLE 解壓縮迴圈 → 寫入 VERA_DATA0
  等鍵 → DC_VID=0 ; RTS
```

**Mode 4 tilemap（mode4.asm）**：
```
START:
  VERA_CTRL=0 ; DC_VID=$11 ; DC_HSC=$40 ; DC_VSC=$40
  載入 256 色 palette @$1FA00
  清 tilemap @$00000 (4096 bytes, 每格寫 tile+attr)
  載入 tilemap 資料 @$00300
  載入 tiles @$10000
  L0_CFG=$13 (8bpp) ; L0_MAP=0 ; L0_TIL=$80
  設捲動暫存器=0
LOOP:
  更新 H/V scroll（INC/比較）→ 寫 VERA_L0_HSC_L/H
  延遲 ; JMP LOOP
```

**Sprite + PSG 音樂（spritesnd.asm）**：初始化同 sprite，另加：
```
初始化 music 狀態 (zero page $EB=step, $EC=tick, $ED=env)
LOOP:
  DEC tick → 到 0 時：設位址 $1F9C0 (Stride 0) → 寫 4 voices 各 4 bytes
  DEC env → 衰減音量 → 寫 VERA_DATA1 (音量)
  更新 sprites（同 sprite.asm）
  檢查鍵盤 → 有鍵：清除 4 voices、DC_VID=0、RTS
  JMP LOOP
```

---

## 4. Applesoft BASIC 編譯器 API（`src/applebasic.mjs`）

```js
import { compileApplesoftBasic } from "applebasic.mjs"
const startup = compileApplesoftBasic(veratestDir, "startup.bas")
// 回傳 Uint8Array：原生 Apple II memory-linked token stream（載入位址 $0801）
```

**功能**：把純文字 `startup.bas`（每行 `10 TEXT: SPEED=255`）編譯成 Apple II 原生二進位格式：
```
每行 = NextPtr[2] + LineNo[2] + tokens... + 0x00
結尾 = 0x00 0x00 (program end marker)
```
- 載入位址固定 **`$0801`**（BASIC 程式起點）。
- 自動 token 化（`PRINT`→`$BA`、`POKE`→`$B9`、`IF`→`$AD`、`GOTO`→`$AB`、`BRUN`→`$B6`…）。
- 字串內保留空白；字串外空白被剝掉（符合 Apple II ROM tokenizer 行為）。
- `;`/`//` 開頭行視為註解跳過；非 `數字+空白+內容` 格式的行跳過。

**啟動方式**：`PRINT CHR$(4);"BRUN GAME.BIN"`（`CHR$(4)` = Ctrl-D，ProDOS 命令前綴）。`BRUN` 會把 BIN 載入 aux 位址並執行。

**Token 表**：`src/applebasic.inc` 提供 `TOK_END=$80`…`TOK_MID=$EA` 對照；組語可直接 `include applebasic.inc` 引用（雖本埠 BASIC 由 JS 端編譯，非組語端）。

---

## 5. ProDOS 140KB 映像建置器（`src/veratest/veratest.mjs`）

### 5.1 流程

1. 讀入底稿 `assets/ProDOS 2.4.3.po`（140KB ProDOS 2.4.3 已格式化磁碟）成 `Uint8Array`。
2. **格式化/重寫磁碟**：掃描既有目錄鏈（block 2 起），把已存在檔案標成 free，再重新分配 block。
   - Block allocation bitmap 在 `disk[6*512 .. 7*512]`（bitmap 區），`isBlockFree`/`markBlockUsed`/`markBlockFree` 操作 bit 7-(b%8)。
   - `allocateBlock()` 從 block 7 起找 free block，填入 `0` 並回傳 block 號。
3. **寫檔案**：`addFile(filename, type, aux, data)`。
4. 更新 block 2 的檔案計數（`disk[2*512+$25]` = fileCount）。
5. 寫出 `veratest.po`（若檔案被 emulator 鎖住，會改存 `.new` 並提示）。
6. 呼叫 `generatePreviewPng()` 產生 `veratest.png`（560x384 PNG，純 JS 手刻，含 CRC32 + zlib）。

### 5.2 `addFile(filename, type, aux, data)` 參數

| 參數 | 說明 |
|---|---|
| `filename` | 檔名（≤15 字元）。 |
| `type` | **ProDOS 檔案類型**。BIN 用 **`0x06`**；STARTUP 用 **`0xFC`**（BASIC.SYSTEM 啟動檔）；一般資料用 `0x00`。 |
| `aux` | **載入位址（BIN 的 load address，little-endian）**。BIN 一律 `0x2000`；STARTUP 用 `0x0801`。 |
| `data` | `Uint8Array` 內容。 |

- `size <= 512` → 單一 block（stType=1）；否則多 block（stType=2，用 index block + data blocks）。
- 目錄項目寫入 block 2 起的目錄鏈，39-byte 格式，13 entries/block。
- **access 欄位設 `$C3`**（完全解鎖）。

**典型呼叫**（veratest.mjs 內）：
```js
const sprite2 = assembleAsmFile(veratestDir, "sprite.asm", 2, 0x2000)
addFile("SPRITE.BIN", 0x06, 0x2000, sprite2)
const startup = compileApplesoftBasic(veratestDir, "startup.bas")
addFile("STARTUP", 0xFC, 0x0801, startup)
```

### 5.3 檔案類型速查

| type | 意義 |
|---|---|
| `$06` | BIN（binary，載入 aux 位址並執行） |
| `$FC` | BASIC.SYSTEM 啟動檔（STARTUP） |
| `$00` | 一般資料檔（如 SONIC.DAT） |

---

## 6. 新增一個遊戲的完整步驟

### 6.1 寫組語 `game.asm`

```
* = $2000            ; 被組譯器忽略；載入位址由 addFile 的 aux=0x2000 決定

START:
    LDA #$00
    STA VERA_CTRL
    ; ... 初始化（見 §3 骨架）
    ; 載入 palette / tilemap / sprites / 設 L0_CFG 等
    LDA #$11           ; 或 $41 / $71 依需求
    STA VERA_DC_VID
LOOP:
    ; ... 每幀更新
    LDA $C000          ; 檢查鍵
    BPL NO_KEY
    STA $C010
    LDA #$00
    STA VERA_DC_VID    ; 關視訊回 BASIC
    RTS
NO_KEY:
    ; 延遲
    JMP LOOP

; 資料表（HEX / !BYTE / ASC）
SPR_PIXELS:
    HEX ...
```

> **入口**：binary 開頭即 `START:`。`BRUN` 自動跳載入位址執行，**不用寫 JMP $2000**。結尾 `RTS` 回到 BASIC 選單。

### 6.2 寫 `startup.bas` 加一個選單項

```
140 IF A$ = "3" AND S = 2 THEN PRINT CHR$(4);"BRUN GAME.BIN"
145 IF A$ = "3" AND S = 4 THEN PRINT CHR$(4);"BRUN GAME4.BIN"
```
（`S=2/4` 是 startup.bas 的 slot 探測結果。）

### 6.3 在 `veratest.mjs` 加一行

```js
const game2 = assembleAsmFile(veratestDir, "game.asm", 2, 0x2000)
const game4 = assembleAsmFile(veratestDir, "game.asm", 4, 0x2000)
addFile("GAME.BIN",  0x06, 0x2000, game2)
addFile("GAME4.BIN", 0x06, 0x2000, game4)
```

### 6.4 建置

```
build.bat veratest     # 或 node src\veratest\veratest.mjs
```
產出 `veratest.po`（140KB 可開機）＋ `veratest.png`。

---

## 7. 重要限制與注意事項

- **組譯器**：無 macro、無條件組譯、無 16-bit 算術運算式（只能 `+`/`-` 一個常數）；分支僅 ±127。
- **每 slot 需組一次**（slot=2 與 slot=4 各產生一個 binary），由 BASIC 探測 slot 後擇一啟動。
- **載入位址**：BIN 一律 `$2000`（aux=0x2000），binary 內不含 ProDOS 檔頭。
- **退出必做**：`DC_VID=0`（關 VERA 視訊回 Apple II 文字螢幕）＋ 清除 PSG（若有用聲音）＋ 還原 IRQ 向量（若 hook 過）。
- **VRAM 128KB**：Bank 0 = `$00000..$0FFFF`，Bank 1 = `$10000..$1FFFF`。PSG=`$1F9C0`、Palette=`$1FA00`、Sprite attributes=`$1FC00`。
- **IRQ 內禁止 ProDOS MLI**，且必須保存/還原 `VERA_ADDR_L/M/H`。
