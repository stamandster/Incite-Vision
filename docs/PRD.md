# Product Requirements Document (PRD)

## Incite Vision - Virtual Camera Manager

### 1. Product Overview

**Incite Vision** is a Windows desktop application providing a virtual camera feed with hotkey-switchable source switching between webcam and screen capture.

### 2. User Requirements

#### 2.1 Core Features

| Priority | Feature | Description |
|----------|---------|------------|
| P0 | Virtual Camera | System-wide webcam visible to all applications |
| P0 | Webcam Capture | Live webcam feed at configurable resolution |
| P0 | Screen Capture | Full screen or monitor selection |
| P0 | Source Switch | Toggle between webcam/screen via hotkey |
| P1 | Auto-Install Drivers | UnityCapture/OBS driver installation |
| P1 | System Tray | Minimize to tray, background operation |
| P1 | Auto-Start | Launch with Windows |
| P2 | Resolution Config | 720p, 1080p, 1440p, 4K |
| P2 | Letterbox Fit | Preserve aspect ratio |

#### 2.2 User Interactions

- **Main Window**: Status display, source selection, toggle button
- **System Tray**: Left-click to show, right-click for menu
- **Tray Menu**: Show Window, Start/Stop Streaming, Quit
- **Toggle Button**: Green START / Red STOP with state indicator

#### 2.3 Data Requirements

Settings stored in `settings.json`:
- Resolution (default: 1920x1080)
- Preferred webcam index
- Preferred monitor ID
- Hotkey binding
- Virtual backend (auto/unity/obs)
- Active source (webcam/screen)
- Start with Windows (bool)
- Auto-start on load (bool)
- Start minimized (bool)

### 3. Technical Requirements

#### 3.1 Runtime Dependencies

- Python 3.12+
- OpenCV (cv2)
- MSS (screen capture)
- pyvirtualcam
- pystray
- customtkinter
- keyboard
- Pillow

#### 3.2 System Requirements

- Windows 10/11 (64-bit)
- Admin rights for driver installation
- Webcam or screen for capture source

#### 3.3 Performance Targets

- 60 FPS output
- <100ms hotkey response
- <50MB RAM usage

### 4. Functional Specification

#### 4.1 Startup Flow

1. Check for settings.json, create if missing
2. Detect available webcams and monitors
3. Detect virtual camera driver (registry + file)
4. Create system tray icon
5. If auto_start_on_load: begin streaming
6. If start_minimized: hide to tray

#### 4.2 Streaming Flow

1. User clicks START or Tray > Start
2. Initialize capture threads (webcam + screen)
3. Open virtual camera device
4. Begin frame loop at 60 FPS
5. Handle hotkey for source toggle
6. On stop: release all resources

#### 4.3 Source Fallback

If active source becomes unavailable:
- Webcam → fall back to screen
- Screen → fall back to webcam
- Both unavailable → show offline frame

### 5. Acceptance Criteria

- [ ] App launches without errors
- [ ] Webcam feed visible in video apps as virtual camera
- [ ] Screen capture works and shows correct monitor
- [ ] Hotkey toggles sources instantly
- [ ] Tray icon appears and responds to click
- [ ] Tray menu items work correctly
- [ ] Settings persist across restarts
- [ ] Auto-start with Windows works
- [ ] Double-click tray icon shows window
- [ ] X button minimizes to tray (when enabled)

---

*Document Version: 1.0*
*Last Updated: 2026-04-17*