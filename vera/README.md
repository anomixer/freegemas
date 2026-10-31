# Freegemas for Apple //e VERA

English | [繁體中文](README-tw.md)

An Apple //e VERA port of Freegemas, compiled to 65C02 code with LLVM-MOS. Graphics use a 320×240 8bpp bitmap, persistent hardware gem sprites, and a top-edge mask. A small resident ProDOS loader loads the title, game, instructions, and options as separate programs.

The bootable 2,048 KB disk image is [freegemas.hdv](freegemas.hdv).

## Requirements and build

You need Node.js, Python/NumPy, ffmpeg/ffprobe, CMake, the LLVM-MOS SDK, and Cadius. Windows uses the bundled `llvm/tools/cadius.exe`; other platforms need Cadius on `PATH` or can pass `-DCADIUS_EXECUTABLE=/path/to/cadius`. The ProDOS system files are included under `assets/prodos-system/`; a separate time-pilot checkout is not required.

Run from the repository root:

```powershell
node vera\tools\build_assets.mjs
cmake -S vera\llvm -B vera\llvm\build
cmake --build vera\llvm\build --target disk --parallel 4
```

The SDK defaults to `C:/dev/llvm-mos-sdk/install`. Configure CMake with `-DLLVM_MOS_SDK=...` to use another location. Assets come from the original `media/` directory. The build produces VERA slot 2 and slot 4 programs and packages them into `vera/freegemas.hdv`.

Use a 128 KB Apple IIe with VERA-enabled AppleWin or compatible hardware. No auxiliary RAM is needed: music is streamed from disk through a small main-RAM ring and effects are preloaded into VERA VRAM. Example for VERA-enabled AppleWin:

```powershell
AppleWin.exe -s2 vera -s7 hdc -h1 C:\dev\freegemas\vera\freegemas.hdv
```

Close or unmount the image before rebuilding if AppleWin has it locked.

## Install from ProDOS files

The HDV volume is named `FREEGEMAS`. To install on another ProDOS volume or in a subdirectory, copy all files from the HDV into the target volume or directory except `PRODOS`. Keep the `FREEGEMAS` marker file with the game files, set the ProDOS prefix to that location, and launch `FREEGEM.SYSTEM`. The loader and game open their programs, scenes, graphics, music, sound effects, and `HISCORE.DAT` by filename, so their block allocation can differ from the packaged HDV. Newly generated file entries include the local build date and time in ProDOS format.

Direct HDV boot and the game-to-title return were verified in AppleWin with the previous template-based image. The new Cadius-generated HDV has been built and its ProDOS catalog checked; booting this newly packaged image still needs verification. File-level installation on VeraSD was confirmed with the earlier image, including persistent high-score writes to `HISCORE.DAT`.

Startup checks for VERA in slot 2 or 4. If neither is detected, it still shows the full text introduction, author, URL, mouse status, and controls. It displays `STATUS: VERA NOT DETECTED` and `STOPPED: VERA REQUIRED IN SLOT 2 OR 4`, then halts without entering the title or game. Keys cannot bypass this stop.

## Controls

- Title: arrow keys select; Space/Enter opens an item. Mouse hover selects an item, and clicking opens it.
- How to Play: press any key or click to return to the title.
- Options: arrow keys select; Space/Enter or a click toggles Music/Sound or activates Back. Esc returns to the title. Fullscreen is always ON.
- Game: arrow keys move the board cursor; Space selects/swaps gems. With a mouse, click two adjacent gems, or hold the first gem and drag to an adjacent gem to attempt a swap. Each drag triggers only once.
- H shows a hint, R restarts, and Esc returns to the title. Show Hint, Reset Game, and Exit can also be clicked.
- Title EXIT saves pending high scores and returns to the ProDOS Bitsy Bye file menu.

Apple Mouse Cards are detected in slots 4 and 5. With VERA in slot 4, put the Mouse Card in slot 5. All graphical pages use the original hand-shaped pointer. Keyboard controls remain available.

The startup introduction shows ANOMIXER 2026, controls, and the detected mouse slot (or `MOUSE: NONE`). Press any key or wait approximately five seconds to continue; returning from a game does not replay it.

## Gameplay and high scores

Time Trial starts with a two-minute countdown. Endless hides the time panel. The port includes matches, cascades, scoring, hint penalties, sparkle effects, floating score text, and Game Over animations. A move already in progress finishes its cascades before a timed Game Over.

With no legal moves, Endless ends the game. Time Trial drops the old gems off-screen and supplies a new playable board, retaining the score and countdown. R instead starts a fresh game.

Gems remain hardware sprites after landing; ordinary moves do not redraw the whole bitmap. Only affected sprites and changed HUD digits are updated.

Options displays separate Time Trial and Endless high scores. Pending records are saved to `HISCORE.DAT` when returning through the loader. Closing the emulator before returning to the menu can lose unsaved scores. Disk rebuilds preserve valid existing records. Audio settings currently last only for the running session.

## Audio and loading

Sound effects come from the original `select.ogg`, `fall.ogg`, and `match1–3.ogg`. They are converted to signed 8-bit mono VERA PCM at rate 21 (8010.86 Hz) with the original gains, and the whole set totals 9,740 bytes. The five streams are preloaded into VERA VRAM starting at `$14800`, so playback needs no disk reads and no auxiliary RAM.

A single VERA PCM FIFO carries both music and effects, so the game mixes them in software: build-time normalization holds music peaks near ±61 and effects at ±37, so the signed 8-bit sum can never wrap. Keeping the music under half of full scale also keeps the web build's (apple2ts) doubled `(PSG + PCM)` mixer from clamping on peaks, which was audible as gritty noise when the track was normalized to 0.70 full scale; AppleWin sums the two without doubling, and only clips above 127. Staging an effect reads VRAM through port 0 and restores both address ports and the control register, so graphics state survives mixing. Effects replace each other but always add on top of the music.

Music is now one streamed PCM track on every VERA machine, IIgs style. `MUSIC.PCM` is 1,012,224 bytes (1,977 ProDOS blocks, 126.35 seconds). `tools/build_music_pcm.py` renders it with ffmpeg (linear-interp resample to 8,011 Hz, attenuation to about 0.48 full scale, 40-sample fade); the original track already peaks near full scale, so boosting it only pushed the limiter into hard clipping. The limiter at 0.70 is now a safety ceiling that never engages. The game streams it from disk through a 1 KB ring buffer, keeping the FIFO about 1,024 bytes deep and topping it up with 133/134 samples per VSYNC. A frame that overruns its VSYNC returns from `waitvsync` without waiting, so those feeds would fall behind the samples VERA drains in real time; while the audio-low flag (ISR bit 3, FIFO below 1,024) still reports a shallow queue, the tick keeps paying 128-sample catch-up chunks (`MUSIC_CATCHUP`) until the target depth is back, so the queue never drains to an underrun "bo~bo~" pop no matter how long the frame was. Long CPU-bound loops (the board scan, board generation) call `frame_pump()`, which pays the audio work in place when a VSYNC latch is already set. The number of samples actually queued is also the machine's real-time reference: `music_frames_elapsed()` turns it into whole VSYNC ticks (`133514` thousandths of a sample per frame) and the Time Trial countdown adds those ticks, so the two-minute timer now advances at wall-clock speed instead of once per loop iteration (a 1.6-frame cascade used to tick only 1.6 times for 2 frames of music). One SET_MARK per loop and sequential MLI reads up to 1 KB keep disk traffic low; short reads fall back to a 512-byte read. The track loops forever.

The YM2151 probe is informational only now: the intro prints `FM: YM2151 DETECTED (OPM)` or `FM: NONE`, but playback is identical either way. There is no FM or PSG music path, no `MUSIC.VZM` or `MUSIC.PSG` on the image, and no auxiliary-RAM music preload.

Music and PCM effects have independent ON/OFF settings. Music plays only during gameplay; R restarts it and Esc mutes, closes the file, and hands the disk back to the loader. Sound OFF does not stop the music.

After the game binary starts, `LOADING GAME...` shows an asset meter for gems, scene, and the five effects; it reaches 100% when the board is ready, with `GAME START` underneath. `MUSIC.PCM` is not part of that meter because it streams during play. The game binary itself loads with the text-only message.

## Project layout

- `llvm/src/`: loader, title/menu programs, game, graphics, mouse, and audio drivers.
- `llvm/tools/build_hdv.py`: ProDOS disk packager.
- `assets/prodos-system/`: ProDOS and CLOCK.SYSTEM source files added by Cadius to a newly created HDV volume.
- `llvm/tools/cadius.exe`: bundled Windows Cadius executable; other platforms can supply their own.
- `tools/build_assets.mjs`: original-media conversion for VERA graphics.
- `tools/build_mouse.mjs`: original hand-cursor conversion.
- `generated/`: palette, sprite, scene, and audio inputs needed for builds.
- [AGENTS.md](AGENTS.md): architecture, memory layout, development history, and pitfalls.

## Audio conversion experiments

`tools/build_music_pcm.py` and `tools/build_sound.mjs` are the only audio converters in the build now. Earlier WAV-to-PSG, MIDI, and YM2151 experiments (with their historical filenames) are documented in [music-conversion-research.md](docs/music-conversion-research.md); those tools and `MUSIC.PSG`/`MUSIC.VZM` no longer exist in the tree. Listening previews and analysis outputs go in `llvm/build/`.

## Regression tests

```powershell
python -m pip install py65 numpy
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
python -u vera\llvm\tools\test_music.py
python -u vera\llvm\tools\test_pcm_clock.py
python -u vera\llvm\tools\test_mouse.py
python -u vera\llvm\tools\test_vera_detect.py
```

Tests execute compiled 65C02 binaries against instrumented VERA, ProDOS, and Mouse Card firmware models. Coverage includes both VERA slots, cascades, local updates, hints, timing, high scores, audio streams, menus, and mouse swaps/drags. Private in-memory disk copies keep synthetic scores out of the delivered image. Model tests supplement, but do not replace, AppleWin and hardware testing.

`test_music.py` streams the whole 1,012,224-byte `MUSIC.PCM` byte-exactly on both slots, then checks disk reads, loop point, OFF/ON, effect mixing sample by sample, R restart, and silent Esc. `test_sound.py` verifies the five effects byte-exactly in VRAM, their table offsets, OFF/ON, replacement, drain, port preservation, and that an effect never reopens the disk. `test_pcm_clock.py` drains the FIFO per CPU cycle at 8,010.86 Hz and compares the rendered stream with the source PCM, including a 230 ms starvation gap and a mixed effect window.

The model also emulates the file-level ProDOS MLI calls the resident loader uses (`GET_PREFIX` `$C7`, `OPEN` `$C8`, `READ` `$CA`, `WRITE` `$CB`, `SET_MARK` `$CE`, `GET_EOF` `$D1`, `CLOSE` `$CC`, `QUIT` `$65`) on top of block reads/writes (`$80`/`$81`), so the full cold-boot, title and in-game paths run in the harness again. `test_loading_progress.py` counts the 186 asset blocks the disk actually carries. All of these are still model runs, not AppleWin or hardware verification.
