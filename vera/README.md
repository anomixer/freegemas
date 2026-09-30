# Freegemas for Apple //e VERA

English | [繁體中文](README-tw.md)

An Apple //e VERA port of Freegemas, compiled to 65C02 code with LLVM-MOS. Graphics use a 320×240 8bpp bitmap, persistent hardware gem sprites, and a top-edge mask. A small resident ProDOS loader loads the title, game, instructions, and options as separate programs.

The bootable 800 KB disk image is [freegemas.hdv](freegemas.hdv).

## Requirements and build

You need Node.js, Python/NumPy, ffmpeg/ffprobe, CMake, and the LLVM-MOS SDK. The ProDOS template is included at `assets/800kb.hdv`; a separate time-pilot checkout is not required.

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

Music uses the selected smooth, pure-melody PSG arrangement (+9 dB gain, `generated/music_pure_gained.psg`, 56,675 bytes across 7,398 frames, approximately 123.3 seconds) played as a direct raw `MUSIC.PSG` stream without runtime Huffman curve decompression. It is preloaded across Apple IIe auxiliary RAM (`$0800–$BFFF`, 46 KB) and Auxiliary Language Card Banks 1 and 2 (`$D000–$FFFF`, 16 KB), freeing main RAM and requiring no music disk reads during gameplay.

Music and PCM effects have independent ON/OFF settings. Music plays only during gameplay; R restarts it and Esc stops audio.

After the game binary starts, `LOADING GAME...` shows an asset-loading progress bar for gems, scene, music, and effects. It reaches 100% when the board is ready, with `GAME START` underneath. The game binary itself loads with the text-only message.

## Project layout

- `llvm/src/`: loader, title/menu programs, game, graphics, mouse, and audio drivers.
- `llvm/tools/build_hdv.py`: ProDOS disk packager.
- `assets/800kb.hdv`: included ProDOS/Bitsy Bye template, originally copied from TimePilot-IIvera.
- `tools/build_assets.mjs`: original-media conversion for VERA graphics.
- `tools/build_mouse.mjs`: original hand-cursor conversion.
- `generated/`: palette, sprite, scene, and audio inputs needed for builds.
- [AGENTS.md](AGENTS.md): architecture, memory layout, development history, and pitfalls.

## Audio conversion experiments

Earlier WAV-to-PSG and MIDI experiments are documented in [music-conversion-research.md](docs/music-conversion-research.md). `tools/wav2psg.py` approximates notes/percussion from the original OGG; it is not a lossless recording conversion or the arrangement shipped in the game. `tools/midi_psg_arrange.py` contains other experimental arrangements. Listening previews and analysis outputs go in `llvm/build/`.

## Regression tests

```powershell
python -m pip install py65 numpy
python -u vera\llvm\tools\test_mos.py
python -u vera\llvm\tools\test_sound.py
python -u vera\llvm\tools\test_music.py
python -u vera\llvm\tools\test_mouse.py
python -u vera\llvm\tools\test_vera_detect.py
```

Tests execute compiled 65C02 binaries against instrumented VERA, ProDOS, and Mouse Card firmware models. Coverage includes both VERA slots, cascades, local updates, hints, timing, high scores, audio streams, menus, and mouse swaps/drags. Private in-memory disk copies keep synthetic scores out of the delivered image. Model tests supplement, but do not replace, AppleWin and hardware testing.
