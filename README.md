# Incite Vision

Incite Vision is a Windows virtual camera app for switching between a webcam, a monitor, or a fallback image and exposing that feed to Zoom, Teams, OBS, and similar software.

![Incite Vision Screenshot](screenshot.png)

## Current Release

- Current public release: `v1.1.9`
- Platform: Windows 10/11 x64
- Python runtime for source use: 3.12+

## Features

- Virtual camera output through UnityCapture or OBS Virtual Camera
- Source selection: `Webcam`, `Screen`, or `Image`
- Global hotkeys:
  - `Ctrl+Alt+1` webcam
  - `Ctrl+Alt+2` screen
  - `Ctrl+Alt+3` image
  - `Ctrl+Alt+S` toggle
- Webcam-only mirroring
- Screen scaling modes:
  - `Fit`
  - `Fill`
  - `Crop`
- Transition controls:
  - `Fade`
  - `Cut`
  - Adjustable fade time when fade is enabled
- Image picker with clear/remove button
- Auto fallback handling when webcam or screen is unavailable
- System tray support with show, start/stop, and quit
- Start with Windows, auto-start on load, and start minimized
- Live debug readout for actual input and output frame sizes
- Root icon assets used consistently:
  - `logo-icon.ico` for app/exe icon
  - `logo-icon.png` for tray/runtime image loading

## Known Video Conference Gotchas

These are the main issues we found while testing Zoom, and they may apply to other video conference apps too.

### Zoom camera input is softer than Zoom screen share

- Zoom treats a virtual camera like a webcam feed, not a true screen-share feed.
- That means Zoom may downscale and compress the image more aggressively.
- Text-heavy content often looks softer in Zoom camera mode than native Zoom screen share.

### Output resolution matters a lot

- If your monitor is higher resolution than the selected Incite Vision output, Incite Vision must scale it down.
- Example: `2560x1440` monitor to `1920x1080` output will soften small text.
- The in-app debug line shows this directly:
  - `Frames: in 2560x1440 -> out 1920x1080 (fit)`

### Best Zoom result we found

- Enable Zoom `HD`
- Set Incite Vision output to `1280x720` when using Zoom camera mode
- Use the `Zoom HD Preset` button in the app for that quickly

### If text fidelity matters most

- Prefer actual Zoom screen sharing over virtual camera mode
- Virtual camera mode is best when you need source switching, overlays, or a unified feed

## Usage

### Starting

1. Launch the app
2. Pick source, resolution, backend, and any optional screen/transition settings
3. Press `START`
4. Choose `Unity Video Capture` or `OBS Virtual Camera` inside your meeting/recording app

### Tray behavior

- Left click / default tray action: show window
- Right click: show tray menu
- The app can start minimized and live in the tray

### Runtime-adjustable settings

These can be changed while streaming is already active:

- Source selection
- Image selection / clear
- Mirror webcam
- Screen mode
- Transition style
- Fade duration

Settings that typically require restart/stop-start to fully take effect:

- Resolution
- Backend
- Physical webcam/monitor selection

## Configuration

Settings are stored in `settings.json` next to the executable or source file.

Current settings include:

- `resolution`
- `preferred_monitor_id`
- `preferred_webcam_index`
- `hotkey`
- `virtual_backend`
- `active_source`
- `preferred_image`
- `mirror_webcam`
- `screen_mode`
- `transition_style`
- `transition_duration`
- `start_with_windows`
- `auto_start_on_load`
- `start_minimized`

## Build From Source

See [`BUILD.md`](BUILD.md) for the current build and release workflow.

Quick local build:

```bash
pip install -r requirements.txt
pip install pyinstaller
pyinstaller --clean --onefile --windowed --icon=logo-icon.ico incite_vision.py
```

The built executable is written to `dist/incite_vision.exe`.

## Versioning And Releases

- Every public executable release must increment the version tag
- Do not overwrite an existing public release asset with a different build
- Use semantic versioning:
  - patch: fixes and small improvements, e.g. `v1.1.10`
  - minor: new features, e.g. `v1.2.0`
- The public version is the Git tag and GitHub release tag
- Update documentation when releasing so README versions and behavior stay accurate

## Project Structure

```text
Incite Vision/
├── incite_vision.py
├── incite_vision.spec
├── settings.json
├── requirements.txt
├── logo-icon.ico
├── logo-icon.png
├── screenshot.png
├── BUILD.md
├── DESIGN.md
├── docs/
├── driver/
└── dist/
```

## Attribution

- UnityCapture: https://github.com/schellingb/UnityCapture
- OBS Studio / OBS Virtual Camera: https://github.com/obsproject/obs-studio

## Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to merchantability, fitness for a particular purpose, and noninfringement. No support is expressed or implied.
