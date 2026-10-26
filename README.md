<p align="center">
    <img src="https://raw.githubusercontent.com/JoseTomasTocino/freegemas/static/images/header_logo.png"><br>
    <img src="https://raw.githubusercontent.com/JoseTomasTocino/freegemas/static/images/header_gems.png"><br>
</p>

__Freegemas__ is an open source version of the well known Bejeweled, for GNU/Linux, Windows, Mac and Playstation Vita. It's written in C++ using [SDL2](https://www.libsdl.org/). In the past it used Gosu instead of SDL2, and the old repository can be found at [Google Code](https://code.google.com/archive/p/freegemas/).

<p align="center">
    <img src="https://raw.githubusercontent.com/JoseTomasTocino/freegemas/static/images/screenshot_1.png">
</p>    
        


## Installation on Debian-based GNU/Linux systems

First, you need to install git and gcc:

    sudo apt-get install git build-essential cmake

Next, install SDL2 and JsonCpp from the repositories:

    sudo apt-get install libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-mixer-dev libjsoncpp-dev
    
After that, clone the repo:

    git clone https://github.com/JoseTomasTocino/freegemas.git
    
Do an out-of-source compilation and run the program:

    cd freegemas
    mkdir build
    cd build
    cmake ..
    make
    ./freegemas

## Installation on OS X

This assumes that you are already using [Homebrew](https://brew.sh/). You will need CMake and a few libraries to compile Freegemas:

    brew install cmake sdl2 sdl2_mixer sdl2_ttf sdl2_image gettext jsoncpp

Now run the following commands to setup your environment to use Homebrew as a backup location for libraries.

```
[[ -z "${LIBRARY_PATH}" ]] && export LIBRARY_PATH=/usr/local/lib
export LIBRARY_PATH="$LIBRARY_PATH:$(brew --prefix)/lib"
```

After that, clone the repo:

    git clone https://github.com/JoseTomasTocino/freegemas.git
    
Do an out-of-source compilation and run the program:

    cd freegemas
    mkdir build
    cd build
    cmake ..
    make
    ./freegemas

## Installation on Playstation Vita

For building for Vita, the [Vita SDK](https://vitasdk.org) should be installed.

After that, clone the repo:

    git clone https://github.com/JoseTomasTocino/freegemas.git

Do an out-of-source compilation:

    cd freegemas
    mkdir vita
    cd vita
    cmake -DCMAKE_TOOLCHAIN_FILE="${VITASDK}/share/vita.toolchain.cmake" ..
    make

Now ``freegemas.vpk`` can be tranfered and installed on Vita.

## WebAssembly (WASM) - Play in Browser

A WebAssembly port is maintained in [`wasm/`](wasm/). It compiles the native C++ SDL2 game directly to WebAssembly using [Emscripten](https://emscripten.org/), running at 60 FPS in any modern web browser with WebGL and Web Audio API.

Read [`wasm/README.md`](wasm/README.md) and [`wasm/README-tw.md`](wasm/README-tw.md) for architecture and local build instructions. Automated deployment to GitHub Pages is supported via [`.github/workflows/deploy-wasm.yml`](.github/workflows/deploy-wasm.yml).


## Music licensing

The music in the game is [Easy Lemon by Kevin MacLeod](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1200076)
Licensed under [Creative Commons: By Attribution 3.0](https://creativecommons.org/licenses/by/3.0/)


## Apple //e VERA port

An Apple //e VERA port is maintained in [`vera/`](vera/). Read [`vera/README.md`](vera/README.md) and [`vera/AGENTS.md`](vera/AGENTS.md) for build instructions and technical details.

- **Platform & Engine**: Compiled to 65C02 native code using the [LLVM-MOS SDK](https://github.com/llvm-mos/llvm-mos-sdk). Uses an 800 KB ProDOS HDV disk image ([`vera/freegemas.hdv`](vera/freegemas.hdv)).
- **Graphics**: 320×240 8bpp bitmap mode with persistent VERA hardware gem sprites and top-edge masking.
- **Audio & Features**: Background music and sound effects routed through VERA PSG; segmented loader for title, game, instructions, and options; full keyboard and mouse control support.
- **Requirements**: 128 KB Apple //e with a VERA card in Slot 2 or Slot 4, tested in VERA-enabled AppleWin and on real hardware (VeraSD).


## Apple IIGS port

An Apple IIGS port is maintained in [`iigs/`](iigs/). Read [`iigs/AGENTS.md`](iigs/AGENTS.md) for the current implementation notes and build instructions. The 320x200 Super Hi-Res game uses the same flat gem artwork in gameplay and the How to Play diagrams. The gameplay board uses source-aligned wood shading with its color and contrast tuned to the VERA port; the flat gem artwork remains unchanged. The 8-column board is framed with symmetric 2px black borders and 12px outer margins (`x=96..307`). Title, How to Play, and Options share the VERA-inspired blue ray backdrop, with screen-specific 12-bank palettes and an even 4×4 Bayer dither pattern. The How to Play gems and crisp menu artwork retain their dedicated colors. The Options screen credits the IIGS port to anomixer and uses the larger VERA-aligned menu text.

The bootable 2MG disk image is built at [`iigs/merlin32/build/freegemas.2mg`](iigs/merlin32/build/freegemas.2mg), including `README.TXT` V1.0.

The IIGS Finder icon uses the game's square red gem. The build streams its DOC music through alternating 4 KiB wave tables. Table changes are synchronized to the DOC end interrupt, while PCM preparation stays in the foreground. Sound effects use separate DOC oscillator pairs. The current audio IRQ build was tested in GSplus: after a continuous capture, the user played a full round and reported no music skips, including during gameplay. Exit with the callback installed, other emulators, and real IIGS hardware still need verification. See [`iigs/AGENTS.md`](iigs/AGENTS.md) for implementation details and the latest validation status.

### Apple IIgs hardware requirements

- Apple IIgs or a compatible emulator, GS/OS, and working Ensoniq DOC audio. The game uses 320x200 Super Hi-Res graphics.
- **Memory: 2 MB total is the minimum recommended target; 4 MB or more is preferred.** The 1,413,400-byte music track (about 1.35 MiB) is loaded into a locked RAM handle when music starts. GS/OS, the game, and its graphics banks also need memory, so a 2 MB system may not have enough free RAM to cache the whole song. Apple’s ROM 03 IIgs shipped with 1 MB and supports RAM expansion; see the [IIgs specifications](https://www.savagetaylor.com/TIL/TIL07889.pdf).
- If the full-song cache cannot be allocated, the game falls back to HD streaming. This fallback was exercised in GSSquared with the RAM cache deliberately disabled: a roughly 160-second audio capture had no clipping and the game reported no music read errors. GSSquared cannot model the requested 1.25 MB ROM 01 configuration through its profile, so this verifies the fallback path but does not replace testing on low-memory hardware.
