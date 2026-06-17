# Build Incite Vision

## Prerequisites

```bash
pip install -r requirements.txt
pip install pyinstaller
```

## Build Command

Use the root icon asset and build a clean one-file executable:

```bash
pyinstaller --clean --onefile --windowed --icon=logo-icon.ico incite_vision.py
```

Output:

```text
dist/incite_vision.exe
```

## Runtime Assets

The application uses root icon assets at runtime:

- `logo-icon.ico` for the app window and compiled exe icon
- `logo-icon.png` for tray/runtime image loading

The tracked `incite_vision.spec` bundles those assets for one-file builds.

## Release Rules

Every public build/release must increment the version.

- Do not overwrite an existing public release with a new binary
- Create a new tag for every release
- Recommended semantic versioning:
  - patch: bug fixes or small UI/runtime changes, e.g. `v1.1.10`
  - minor: new user-facing features, e.g. `v1.2.0`

Typical release flow:

```bash
git status
pyinstaller --clean --onefile --windowed --icon=logo-icon.ico incite_vision.py
git add .
git commit -m "Your release change"
git push origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
gh release create vX.Y.Z dist/incite_vision.exe --title "Incite Vision vX.Y.Z"
```

## Zoom / Video Conference Note

If the goal is crisp text in Zoom camera mode, use the app's `Zoom HD Preset` (`1280x720`) and enable Zoom `HD`. For the sharpest text, true screen share still beats a virtual camera feed.
