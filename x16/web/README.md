# Freegemas Commander X16 web player

A static browser player for the X16 port. It boots the real X16 KERNAL and
`boot.prg` in the official x16-emulator WebAssembly build (r49), then loads the
generated `x16/hostfs/` files into the emulator's in-memory drive.

The page is a separate static site; the existing `wasm/` site remains the
native C++ WebAssembly build.

## Build

Requirements:

- Node.js 20 or newer (the build uses `fetch`, `AbortSignal.timeout`, and the
  built-in `zlib`).
- A populated `x16/hostfs/`. Run `x16/build.ps1` first if it is missing.

```powershell
cd C:\dev\freegemas\x16\web
.\build.ps1
```

Or from the repository root:

```powershell
node .\x16\web\build.mjs
```

The build:

- downloads `x16emu_wasm-r49.zip` into the gitignored `build-cache/`, verifies
  its SHA-256 (`9711036c...628f`), and extracts `x16emu.js`, `x16emu.wasm` and
  `x16emu.data`;
- copies every file from `x16/hostfs/` into `dist/game/` under lower-case
  names, excluding local test state such as `hiscore.dat`;
- writes `dist/game/manifest.json` for the runtime loader;
- copies the page and licence files.

For an offline build, put `x16emu_wasm-r49.zip` at
`x16/web/build-cache/x16emu_wasm-r49.zip` first.

The output directory is `x16/web/dist/`. Both `dist/` and `build-cache/` are
gitignored.

## Run

Serve the output over HTTP; opening `index.html` from `file://` will fail
because the browser cannot fetch the manifest and game files.

```powershell
python -m http.server 8123 --directory C:\dev\freegemas\x16\web\dist
```

Then open <http://127.0.0.1:8123/>. Add `?auto=1` to start without pressing the
boot button. Any static host can serve `dist/`; all references are relative.

The first boot may take several seconds while about 5 MB of HostFS files are
copied into the emulator. Music is an 8,011 Hz mono 16-bit **ZCM** stream from
`music.zcm`, mixed with five short 16-bit PCM effects; browser audio starts
suspended until a user gesture, so use the Sound button. High scores are
written to the emulator's in-memory filesystem, so they persist only for the
page session.

## Controls

Same as the native game:

- mouse: move the game pointer and left-click menu items, gems and the
  Show hint / Reset game / Exit buttons; the player starts with `-capture`
  enabled, so clicking the canvas grabs the pointer for the emulator;
- arrows: move/select;
- Space: select a gem, then swap with an adjacent gem; confirm menu items;
- Enter: confirm a menu item;
- `H`: hint;
- `R`: reset/reshuffle;
- Esc: return to the title;
- Title → Exit: quit to the X16 BASIC `READY.` prompt.

The X16 keyboard joystick mapping also accepts a gamepad (D-pad, A/B, Start,
Select).

## Verification

The page has been tested in headless Chrome against the local static server
with x16emu WebAssembly r49: it reaches the title and Timetrial from the same
`hostfs/` files. A synthetic pointer move did **not** move the emulator
pointer, so mouse movement and click handling are **not yet verified** in the
browser. This is browser/emulator testing, not real Commander X16 hardware
testing. The same ZCM music and PCM effect path is used in the native
`hostfs/` build; only native x16emu and the browser emulator have been
exercised, not real hardware.
