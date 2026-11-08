# Freegemas browser landing page

This directory builds the GitHub Pages landing page for Freegemas and the two
players served from this repository:

- **Native WebAssembly** — the original C++/SDL2 game compiled with Emscripten,
  built from [`wasm/`](../wasm/).
- **Commander X16** — the 65C02/VERA port booted by the official X16Community
  WebAssembly emulator r49, built from [`x16/web/`](../x16/web/).

The landing page also links two external browser emulators:

- **Apple //e + VERA** — [Apple2TS](https://apple2ts.com/) streaming
  [`vera/freegemas.hdv`](../vera/freegemas.hdv).
- **Apple IIgs** — [a2gsemu-ia](https://a2gsemu-ia.pages.dev/) booting the IIgs
  release from this repository.

## Layout

| Path | Purpose |
| --- | --- |
| `index.html` | the landing page source and card layout |
| `assets/freegemas-logo.png` | local copy of the Freegemas logo used in the hero |
| `assets/gems/` | the seven gem icons used in the hero strip |
| `build-site.mjs` | assembles `_site/` from the landing page, `wasm/dist/` and `x16/web/dist/` |
| `_site/` | generated output, gitignored |

## Build

Node.js 20 or newer is required. The landing page is assembled from already
built port outputs; it does not compile them.

```powershell
# 1. Native WebAssembly player (needs the Emscripten SDK on PATH)
.\wasm\build.ps1

# 2. Commander X16 browser player (Node 20+; downloads the pinned r49 emulator)
node .\x16\web\build.mjs

# 3. Landing site
node .\web\build-site.mjs
```

On Linux/macOS, use `./wasm/build.sh` and the same `build-site.mjs` command.
`build-site.mjs` fails with a clear error if either port has not been built.

Serve the result over HTTP rather than opening it from `file://`:

```powershell
python -m http.server 8123 --directory C:\dev\freegemas\web\_site
# <http://127.0.0.1:8123/>
```

The generated site contains:

```text
_site/
  index.html              landing page
  assets/                 logo and gem icons
  wasm/index.html         native WebAssembly player
  x16/index.html          Commander X16 browser player
  players.json            machine-readable link list
  .nojekyll
```

## Deploy

[`.github/workflows/deploy-wasm.yml`](../.github/workflows/deploy-wasm.yml)
builds the WASM player, the X16 player and this landing page on pushes to
`master`, then publishes `web/_site` to GitHub Pages. GitHub Pages must be set
to **Source: GitHub Actions** once in the repository settings.

The public paths become:

- landing: <https://anomixer.github.io/freegemas/>
- native WebAssembly: <https://anomixer.github.io/freegemas/wasm/>
- Commander X16: <https://anomixer.github.io/freegemas/x16/>

The A2VERA and IIgs cards use their external emulator URLs directly, so those
players do not need a local copy in `web/_site`.

## Verification status

The landing-page layout and build flow are local/static-site work. The native
WebAssembly build and the X16 WebAssembly player are built by the GitHub
Actions workflow; they are not vendored into the repository. A2VERA and IIgs
are served by their respective external browser emulators, and this page only
links to them; no full emulator playthrough is performed by the site build. No
real-hardware testing is implied by the landing page.
