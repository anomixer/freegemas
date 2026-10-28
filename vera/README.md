# Freegemas for Apple //e VERA

English | [繁體中文](README-tw.md)

An Apple //e VERA port of Freegemas, compiled to 65C02 code with LLVM-MOS. Graphics use a 320×240 8bpp bitmap, persistent hardware gem sprites, and a top-edge mask. A small resident ProDOS loader loads the title, game, instructions, and options as separate programs.

The bootable 800 KB disk image is [freegemas.hdv](freegemas.hdv).

## Requirements and build

You need Node.js, Python/NumPy, ffmpeg/ffprobe, CMake, the LLVM-MOS SDK, and Cadius. Windows uses the bundled `llvm/tools/cadius.exe`; other platforms need Cadius on `PATH` or can pass `-DCADIUS_EXECUTABLE=/path/to/cadius`. The ProDOS system files are included under `assets/prodos-system/`; a separate time-pilot checkout is not required.

Run from the repository root:

```powershell
node vera\tools\build_assets.mjs
cmake -S vera\llvm -B vera\llvm\build
cmake --build vera\llvm\build --target disk --parallel 4
```

The SDK defaults to `C:/dev/llvm-mos-sdk/install`. Configure CMake with `-DLLVM_MOS_SDK=...` to use another location. Assets come from the original `media/` directory. The build produces VERA slot 2 and slot 4 programs and packages them into `vera/freegemas.hdv`.

Use a 128 KB Apple IIe with VERA-enabled AppleWin or compatible hardware. Without auxiliary RAM, music and sound effects are safely disabled. Example for VERA-enabled AppleWin:

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

Sound effects come from the original `select.ogg`, `fall.ogg`, and `match1–3.ogg`, converted to 16-bit mono VERA PCM at rate 29 (approximately 11062.622 Hz), retaining original gains of 0.3/0.25. No extra Hint, Reset, or Game Over sounds are added.

All five converted effects (with `match1–3` truncated at build time to the first 6,640 bytes / ~0.30 seconds, totaling 26,912 bytes) fit entirely into the 27,904-byte VERA VRAM preload pool. Playback performs no disk reads and uses no auxiliary RAM. The CPU still refills the fixed approximately 4 KB FIFO, so preloading does not eliminate every possible processing delay. Underrun recovery restores 16-bit sample alignment before resuming playback.

New effects interrupt old ones; overlapping mixing and title/options navigation sounds are not implemented. This is **not a 100% reproduction of the original audio**: sample rate, channels, mixing, and match tails differ.

Music has two paths. On a machine with the A2VERA FM daughterboard the boot intro probes the YM2151 and reports `FM: YM2151 DETECTED (OPM)`; the game then loads `MUSIC.VZM` (a packed ZSM stream, 22,974 bytes, 7,582 VSYNC ticks, about 126.4 seconds) and plays melodic parts on eight FM channels with PSG percussion. Without the chip, or when `MUSIC.VZM` is missing, it reports `FM: NONE, PSG MUSIC ONLY` and keeps the PSG stream below. `tools/build_music_vzm.py` transcribes the original `media/music.ogg` into the stream at build time (FFT pitch/onset analysis, then part assignment and register de-duplication); the 71-byte BUSY probe used by both the intro and the player lives in `llvm/src/fm_probe.h`. The whole VZM is preloaded into auxiliary RAM (90 logical pages), so playback performs no disk reads, and both `MUSIC.PSG` and `MUSIC.VZM` ship on the HDV.

The fallback path uses the selected smooth, pure-melody PSG arrangement (+9 dB gain, `generated/music_pure_gained.psg`, 56,675 bytes across 7,398 frames, approximately 123.3 seconds) played as a direct raw `MUSIC.PSG` stream without runtime Huffman curve decompression. It is preloaded across Apple IIe auxiliary RAM (`$0800–$BFFF`, 46 KB) and Auxiliary Language Card Bank 1 (`$D000–$FFFF`, 12 KB continuous), freeing main RAM and requiring no music disk reads during gameplay.

Music and PCM effects have independent ON/OFF settings. Music plays only during gameplay; R restarts it and Esc stops audio. `MUSIC.VZM` reaches the FM chip with key-off and zeroed operator registers on start and on every loop, which is a one-time ~45 kcycle (about 44 ms) cost on those two ticks; ordinary ticks average a few hundred cycles.

After the game binary starts, `LOADING GAME...` shows an asset-loading progress bar for gems, scene, music, and effects. It reaches 100% when the board is ready, with `GAME START` underneath. The game binary itself loads with the text-only message.

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

Earlier WAV-to-PSG and MIDI experiments are documented in [music-conversion-research.md](docs/music-conversion-research.md). `tools/wav2psg.py` approximates notes/percussion from the original OGG; it is not a lossless recording conversion. `tools/midi_psg_arrange.py` contains other experimental arrangements. `tools/build_music_vzm.py` builds the shipped `MUSIC.VZM` from the same analysis and is described in the research document as well. Listening previews and analysis outputs go in `llvm/build/`.

## Regression tests

```powershell
python -m pip install py65 numpy
python -u vera\llvm\tools\test_music_vzm.py
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
python -u vera\llvm\tools\test_music.py
python -u vera\llvm\tools\test_mouse.py
python -u vera\llvm\tools\test_vera_detect.py
```

Tests execute compiled 65C02 binaries against instrumented VERA, ProDOS, and Mouse Card firmware models. Coverage includes both VERA slots, cascades, local updates, hints, timing, high scores, audio streams, menus, and mouse swaps/drags. Private in-memory disk copies keep synthetic scores out of the delivered image. Model tests supplement, but do not replace, AppleWin and hardware testing.

`test_music_vzm.py` is self-contained: it drives the intro probe, `music_init()` file selection, and the whole VZM decoder on the model for both slots, checking the PSG register image, the exact YM2151 write order, the loop, and stop/OFF silence. It compares 7,583 ticks byte-exactly and does not prove how the FM chip sounds.

The model now emulates the file-level ProDOS MLI calls the resident loader uses (`GET_PREFIX` `$C7`, `OPEN` `$C8`, `READ` `$CA`, `WRITE` `$CB`, `SET_MARK` `$CE`, `GET_EOF` `$D1`, `CLOSE` `$CC`, `QUIT` `$65`) on top of block reads/writes (`$80`/`$81`), so the full cold-boot, title and in-game paths run in the harness again. `test_music.py` now plays the shipped raw `MUSIC.PSG` fallback and checks 7,398 frames byte-exactly; `test_sound.py` checks the five PCM streams in the four VRAM preload pools; `test_loading_progress.py` counts the assets the disk actually carries. All of these are still model runs, not AppleWin or hardware verification.
