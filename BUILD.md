# Build Incite Vision

## Prerequisites

```bash
pip install -r requirements.txt
pip install pyinstaller
```

## Build Command

```bash
pyinstaller --onefile --windowed ^
  --name "Incite Vision" ^
  --icon=NONE ^
  --add-data "settings.json;." ^
  --add-data "driver;driver" ^
  --hidden-import cv2 ^
  --hidden-import mss ^
  --hidden-import keyboard ^
  --hidden-import pystray ^
  --hidden-import customtkinter ^
  --hidden-import PIL ^
  --hidden-import win32gui ^
  --hidden-import win32con ^
  incite_vision.py
```

The built `.exe` will be in `dist/`. Copy `settings.json` and `driver/` alongside it if you want portable config.

## Run Without Building

```bash
python incite_vision.py          # Open GUI
python incite_vision.py --silent # Start minimized to system tray
```
