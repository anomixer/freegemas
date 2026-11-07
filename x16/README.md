# Freegemas for Commander X16

English | [繁體中文](README-tw.md)

A Commander X16 port of Freegemas, compiled to 65C02 code with the
[LLVM-MOS SDK](https://github.com/llvm-mos/llvm-mos-sdk). It reuses the
Apple //e VERA artwork and the original `media/` assets, but runs natively on
the X16: VERA at `$9F20`, KERNAL I/O, and the X16 keyboard/joystick APIs.

The game is split into a resident loader at `$2000` and overlays at `$3000`
for the intro, title, How to Play, Options, and the game. Graphics use a
320x240 8bpp VERA bitmap plus hardware sprites. Music is a **ZCM stream**:
8,011 Hz mono signed 16-bit PCM streamed from `hostfs/music.zcm` through the
KERNAL `MACPTR` block read. The five short sound effects are signed 16-bit PCM
samples preloaded in banked RAM and mixed into the same VERA FIFO.

## Requirements

- Windows with PowerShell 7 (`pwsh`), Python 3 with NumPy, and the
  LLVM-MOS SDK. The default SDK path is
  `C:\dev\llvm-mos-sdk\install`; override it with `-Sdk`.
- The tracked `assets/music.zcm` (2,024,422 bytes, 126.35 s). A normal build
  copies it into `hostfs/` and needs no audio conversion.
- Commander X16 emulator **r49 (Pyrite) or newer** for running the built
  `hostfs/` directory. The R49 `kbdbuf_get` extapi (A=18, `$FEAB`) is used
  for keyboard input.
- 512 KiB of banked RAM: scene chunks use banks 30-39, effects banks 24-28, and
  the HUD cache bank 20. The music never has to be loaded into banked RAM.

`ffmpeg` is not needed; the effect builder uses Python with `soundfile` and
`soxr`. The music regeneration path is described below.

## Build

From this directory:

```powershell
cd C:\dev\freegemas\x16
.\build.ps1
```

Or from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\x16\build.ps1
```

The build creates:

- `hostfs/` — the runnable HostFS directory (programs, scenes, PCM effects and
  `music.zcm`).
- `build/` — disposable `.bin`, `.map` and intermediate files.

`build.ps1` removes and recreates both output directories, so a clean build
does not inherit a previous `hiscore.dat`.

## Run

```powershell
C:\dev\emu\x16emu\x16emu.exe `
  -prg C:\dev\freegemas\x16\hostfs\boot.prg `
  -run `
  -capture `
  -fsroot C:\dev\freegemas\x16\hostfs `
  -scale 2
```

Add `-capture` to let x16emu receive the mouse, or press `Ctrl+M` after the
window opens. The game paints its own pointer, so the host cursor is hidden.

To capture the audio output as a WAV file, add `-wav C:\dev\freegemas\x16\out.wav`.
HostFS names are lower-case and case-sensitive.

## Browser web player

A standalone browser player is in [`web/`](web/). It uses the official
x16-emulator WebAssembly r49 build and the same `hostfs/` files, so it runs
the actual X16 KERNAL and `boot.prg` in the browser:

```powershell
cd C:\dev\freegemas\x16\web
.\build.ps1
python -m http.server 8123 --directory .\dist
```

Then open <http://127.0.0.1:8123/> (add `?auto=1` to boot immediately). See
[`web/README.md`](web/README.md) for requirements, the pinned emulator
checksum, offline caching and the session-only high-score note.

## Controls

- **Title:** arrow keys or the mouse move the pointer; Space, Enter or a left
  click opens an item.
- **How to Play:** any key or a left click returns to the title.
- **Options:** arrow keys or the mouse select; Space or a left click toggles
  Music (ZCM/Off), Sound (On/Off), or selects Back; Esc returns to the title.
- **Game:** arrow keys or the mouse move the cursor; Space/left click selects
  a gem, then an adjacent click/arrow key swaps it. Click the on-screen
  Show hint, Reset game and Exit buttons with the mouse. `H` shows a hint,
  `R` restarts the game, and Esc returns to the title.
- **Game Over:** `R` restarts; Esc returns to the title and saves a pending
  high score.

The same directions and the A/B buttons work through the X16 keyboard
joystick mapping (arrows, `X`/`Ctrl` and `Z`/`Alt` for A/B). The port polls
joystick 0.

## Music and audio path

- `media/music.ogg` is decoded and downmixed to mono, resampled to
  **8,010.864 Hz** with `soxr` VHQ, scaled by `0.55`, and stored as signed
  16-bit PCM inside a ZCM container. The eight-byte header is
  `00 00 00 <24-bit sample count> 2F 15`: geometry `0x2F` means 16-bit mono and
  VERA rate `21`. The resulting `assets/music.zcm` is 2,024,422 bytes and
  repeats smoothly at a 40-sample fade at each end.
- `music.c` opens the ZCM once after startup I/O and reads it with `MACPTR`,
  skipping the header, so the 2 MB track is never resident in banked RAM. The
  sample clock starts after an **8-frame prefill** (about 134 ms), not after
  filling the whole 4 KB FIFO. A frame then advances the stream by exactly
  268 bytes, matching the 8,010.864 Hz playback rate; if the FIFO has really
  emptied, one extra frame is fed immediately. This fixed both the long delay
  before effects and the underrun that used to leave the FIFO stuck on its
  last sample. At EOF the stream is closed and the channel is silenced (the
  track is longer than a Time Trial round).
- The five effects are built from the original OGGs by
  `tools/build_effects.py`: soxr VHQ to 8,010.864 Hz, mono, peak-normalised,
  and stored as little-endian signed 16-bit PCM. Each effect is preloaded at
  `$A000` in its own bank (24-28), so a 4,806-byte match effect no longer
  crosses the `$BFFF` bank boundary and truncates MATCH3. `mix_effect16()` in
  `music.c` performs a full 16-bit add and clip in the music RAM buffer;
  `pcm_copy` then writes the combined stream one byte at a time and retains the
  unsent tail for the next frame. VERA uses 16-bit mono at volume 10 (`0x2A`).
- The effect stage is **320 bytes / 160 samples at `$1000`**. One music frame can
  hand over up to 268 bytes / 134 samples, so the previous 80-byte (40-sample)
  stage mixed only the first part of each effect and left the rest music-only;
  that was the chopped, sandy match sound. The stage now covers a whole run.
- The fall sound is started **before** the 16-frame fall animation, so the
  landing cue is heard while the gems move rather than after they have already
  settled.
- The X16 scene patch also removes the decorative dark-blue `88:88` ghost from
  the timer panel and flattens the hard gradient rule across Show hint/Reset/
  Exit. The timer is drawn with a **12×18 glyph cell generated from
  `media/fuentelcd.ttf` at the original 62 px size**, with separate solid and
  anti-alias-bit masks (`time_glyphs` and `time_edge`). It is right-aligned to
  x=75, uses the original LCD ink colour index 10 with a dark blue anti-alias
  index 5, and no longer uses the heavy binary glyph masks that made the
  foreground look artificially bold against the LED ghost.
- **The audio-noise causes are fixed.** `MACPTR` returns the byte count in
  **X only**; the earlier code also treated **Y** as the count high byte, so
  stale staging bytes were played as samples. Separately, the old `pcm_copy`
  checked FIFO-full only once and then dropped bytes when the FIFO filled;
  it now checks every byte and retains the unsent tail for the next frame.
  The old effects were 8-bit at a low peak level, which left only a few
  effective bits and produced the sandy match sounds; they are now 16-bit.
  A native WAV correlates with `assets/music.zcm` at **1.0** over the first
  20 seconds and has no silent gaps, and a match run still correlates after
  the effect.
- Music On/Off is the Options setting. The stream is opened even when music is
  off but its samples are zeroed, so the same 16-bit effect mixer is used in
  both modes; with Music Off only effects are audible. `R` resets the board and
  effects but **keeps the stream open** (reopening the HostFS channel during
  play corrupts later reads); Escape/Exit stops it and removes the VSYNC IRQ.
- Keyboard input uses `kbdbuf_get`, so the KERNAL channel used for music never
  redirects keyboard reads. The game accepts both upper- and lower-case `H`
  and `R`.

To regenerate the music and effect assets:

```powershell
python .\tools\build_music_zcm.py
python .\tools\build_effects.py
```

Both builders require Python with `soundfile`, `soxr` and NumPy. The music
builder rewrites `assets/music.zcm`; the effect builder rewrites the five
16-bit `hostfs/*.pcm` files. Then run `.\build.ps1` to rebuild
`hostfs/`; `build.ps1` also calls both builders.

## High scores and files

High scores are stored in two little-endian `uint32` values in
`hostfs/hiscore.dat`, wrapped in a 12-byte `FGH` version-1 header. The file
is saved when returning to the title after a game over, and when exiting from
the title. A fresh build has no seeded high score.

The loader reads all assets by lower-case HostFS filename, so the directory
can be copied as-is to another HostFS root.

## Validation status

Verified in **x16emu r49 (Pyrite) only**, not on real Commander X16 hardware:

- mouse pointer rendering and KERNAL `mouse_scan`/`mouse_get` polling are
  present; synthetic host-pointer motion did **not** move the emulator pointer,
  so real/captured mouse movement is still unverified;
- boot, intro, title, How to Play, Options, Timetrial and Endless loading;
- the timer keeps running and the board remains interactive in the native
  x16emu game loop; the old FIFO pair-splitting path was replaced with whole
  16-bit sample-pair writes;
- a 33.7-second native WAV capture still contains **one 0.1-second broadband
  burst at 17.1 s** (peak 0.56). That is a large improvement over the previous
  continuous noise, but **the music stream is not yet clean for the whole
  track**;
- the 16-bit effect mixer remains wired, but it has **not been human-ear
  validated** and a synthetic pointer test did not exercise the effect path.
  Do not treat the remaining effect/timing claims below as a listening test.
- the timer digits now use the antialiased 12×18 `fuentelcd.ttf` masks; the
  native screenshot shows thin LCD strokes and no bold ghost silhouette.
- timer expiry, Game Over panel, high-score update, and the high-score file
  being written on return to the title;
- high-score readback: seeding `hiscore.dat` with 42 shows `Timetrial: 42`
  in Options;
- Title Exit restores the KERNAL text screen with `CINT ($FF81)` before
  `enter_basic`, so the emulator shows the `READY.` prompt instead of keeping
  the title bitmap;
- a clean bitmap after leaving/returning through the overlays;
- the standalone [`web/`](web/) player in headless Chrome with the official
  x16emu WebAssembly r49: title and Timetrial rendered from the same
  `hostfs/` files, including the new timer and button scene patch. This was
  browser/emulator testing, not real hardware.

`R` resetting the board and effects keeps the stream uninterrupted and was
exercised in native x16emu; the five effect triggers share the same audio path.
The full 126.35-second track was not played to its EOF in this pass; EOF closes
the stream and silences the channel.

Real-hardware validation is still required, especially for the 16-bit PCM
level, effect/music balance, audio timing, joystick/controller mapping, and the
full track loop. The port has only been exercised with **x16emu r49 and the
x16emu WebAssembly r49 build in a browser**, not on a physical Commander X16.
