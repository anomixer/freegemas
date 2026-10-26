# Freegemas v1.0 - Apple IIGS Edition

We are excited to announce the **v1.0 release of Freegemas for the Apple IIGS**! 

This release is a complete, native **65816 assembly** port targeting **GS/OS**, built with Merlin32 and packaged as an auto-booting ProDOS/GS/OS 2MG disk image.

<p align="center">
  <img src="screenshots/screenshot1.png" alt="Freegemas Apple IIGS Title Screen" width="380">
  <img src="screenshots/screenshot2.png" alt="Freegemas Apple IIGS Gameplay" width="380">
</p>

---

## 🎮 What's Included

* **Bootable Disk Image**: Attach `freegemas.2mg` to your Apple IIGS emulator (GSSquared, GSplus, KEGS, Sweet16) or write it to real hardware (e.g., Floppy Emu, CFFA3000, MicroDrive). It auto-boots directly into `FREEGEM.S16`.
* **Game Modes**:
  * **Time Trial**: Race against the 120-second countdown. Active cascades finish before Game Over triggers.
  * **Endless**: Relaxed puzzle session with no time limits. The game ends when no valid moves remain.
* **Persistent Records**: High scores for both modes are saved automatically to `HISCORE.DAT` in `/FREEGEMAS/DATA`.

---

## 💎 Features & Technical Highlights

### 🎨 Graphics & Visuals
* **320×200 Super Hi-Res (4bpp)**: Features scanline-accurate palettes and an even 4×4 Bayer-dithered ray backdrop.
* **Symmetric Board Design**: Exact 8-column board layout ($x = 96 \sim 307$) framed by 2px symmetric borders and balanced 12px outer deep-blue margins.
* **Hand-crafted Pixel Art**: Authentic 24×20 2D square gem sprites preserved without algorithmic distortion.
* **Custom Assembly Blitters**: Optimized damage-rectangle restoring directly from background cache RAM (`dTitleSave`).

### 🎵 Ensoniq 5503 DOC Audio Engine
* **Sound Effects**: Native 8-bit unsigned PCM sound clips (`select`, `fall`, `match`) played through dedicated DOC oscillator pairs (0/1, 2/3, 4/5).
* **Soundtrack Streaming**: Complete ~126-second BGM (*Easy Lemon*) converted to 11,186 Hz DOC format, streamed via double-buffered 4 KiB wave tables synchronized to DOC end interrupts.
* **Smart Memory Handling**: Caches the full ~1.35 MiB song into locked RAM on systems with $\ge 2$ MB; automatically falls back to background GS/OS disk streaming on memory-constrained systems.

### 🕹️ Controls
* **Mouse**: Full mouse support. Click two adjacent gems or click-and-drag across adjacent cells.
* **Keyboard**:
  * `W` / `A` / `S` / `D` or Arrow keys: Move selector
  * `Space` / `Enter`: Select gem / Swap
  * `H`: Show Hint (highlights valid move; next match earns no points)
  * `R`: Reset game
  * `Esc`: Return to title
* **HUD**: Interactive on-screen buttons for *Show Hint*, *Reset Game*, and *Exit*.

---

## 💻 Hardware Requirements

* **Computer**: Apple IIGS (ROM 01 or ROM 03) or compatible emulator.
* **RAM**: 2 MB minimum recommended (4 MB or more preferred for full-soundtrack RAM caching).
* **Storage**: Bootable 2MG ProDOS/GS/OS disk image (`freegemas.2mg`, ~10 MB).

---

## 📦 Download Assets

* [`freegemas.2mg`](https://github.com/anomixer/freegemas/releases/download/v1.0/freegemas.2mg) — Bootable Apple IIGS 2MG Disk Image
