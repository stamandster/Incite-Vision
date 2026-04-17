# Functional Requirements Document (FRD)

## Incite Vision - Virtual Camera Manager

### 1. System Architecture

```
┌─────────────────────────────────────────────────────┐
│                 Incite Vision App                    │
├─────────────────────────────────────────────────────┤
│  GUI Layer (CustomTkinter)                         │
│  ├── Main Window                               │
│  ├── Sidebar (Settings)                       │
│  └── Status Display                           │
├─────────────────────────────────────────────────────┤
│  VirtualCameraManager                          │
│  ├── WebcamThread (capture)                   │
│  ├── ScreenCaptureThread (capture)            │
│  └── pyvirtualcam (output)                │
├─────────────────────────────────────────────────────┤
│  Platform Integration                        │
│  ├── System Tray (pystray)               │
│  ├── Hotkey (keyboard)                   │
│  └── Registry (auto-start)               │
└─────────────────────────────────────────────────────┘
```

### 2. Module Design

#### 2.1 Settings (Lines 89-109)

```python
@dataclass
class Settings:
    resolution: list          # [1920, 1080]
    preferred_monitor_id: int
    preferred_webcam_index: int
    hotkey: str          # "ctrl+alt+s"
    virtual_backend: str  # "auto"
    active_source: str  # "webcam" | "screen"
    start_with_windows: bool
    auto_start_on_load: bool
    start_minimized: bool
```

**Methods**:
- `load()` - Load from settings.json
- `save()` - Write to settings.json

#### 2.2 VirtualCameraManager (Lines 448-708)

**Public Methods**:
- `initialize()` - Setup capture threads and virtual camera
- `run()` - Main streaming loop
- `shutdown()` - Release resources
- `handle_hotkey()` - Trigger source switch

**Internal Methods**:
- `_get_frame_for_source(source)` - Get frame from thread
- `_resize(frame)` - Letterbox fit to target resolution
- `_blend_frames(a, b, alpha)` - Crossfade transition
- `_process_transition()` - Handle animated switches
- `_check_fallback()` - Handle source loss

#### 2.3 WebcamThread (Lines 358-404)

**Public Methods**:
- `get_frame()` - Get current frame
- `stop()` - Stop capture

#### 2.4 ScreenCaptureThread (Lines 406-447)

**Public Methods**:
- `get_frame()` - Get current frame
- `stop()` - Stop capture

### 3. User Interface Design

#### 3.1 Main Window Layout

```
┌──────────────────────────────────────────┐
│ ┌──────────┬──────────────────────────┐  │
│ │          │                       │  │
│ │ Sidebar  │     Status Area       │  │
│ │ (280px) │                     │  │
│ │          │  RUNNING/STOPPED    │  │
│ │ SOURCE  │  Detail Text       │  │
│ │ [Cam]   │                     │  │
│ │         │  Source: webcam     │  │
│ │ MONITOR │  FPS: 60          │  │
│ │ [Mon]   │  Backend: OBS     │  │
│ │         │                     │  │
│ │ [START] │  [Activity Log]      │  │
│ │          │                     │  │
│ └──────────┴──────────────────────────┘  │
└──────────────────────────────────────────┘
```

#### 3.2 Color Scheme

| Element | Color |
|---------|-------|
| Background Dark | #171717 |
| Background Deep | #0f0f0f |
| Border | #2e2e2e |
| Text Primary | #fafafa |
| Text Secondary | #b4b4b4 |
| Text Muted | #898989 |
| Accent Green | #3ecf8e |
| Running (Red) | #ef4444 |

#### 3.3 Tray Icon

- **V shape**: Green when stopped, Red when running
- **Menu Items**:
  1. Show Window (double-click)
  2. ─────────────
  3. Start/Stop Streaming
  4. ─────────────
  5. Quit

### 4. Data Flow

```
User Click START
    │
    ▼
VirtualCameraManager.initialize()
    │
    ├── WebcamThread.start() ──► CV2 capture @ 60fps
    └── ScreenCaptureThread.start() ──► MSS capture @ 60fps
    │
    ▼
pyvirtualcam.Camera.open()
    │
    ▼
while running:
    frame = _get_frame_for_source(current)
    frame = _resize(frame)  # letterbox if needed
    vcam.send(frame)
    vcam.sleep_until_next_frame()
```

### 5. Error Handling

| Scenario | Handling |
|----------|---------|
| No webcam | Fall back to screen |
| No screen | Fall back to webcam |
| Neither available | Show offline frame |
| Driver not installed | Show install button |
| Driver install fail | Open browser to URL |

### 6. CLI Arguments

```bash
InciteVision.exe              # Normal launch
InciteVision.exe --silent  # Start minimized
```

### 7. Configuration Files

| File | Location | Purpose |
|------|---------|---------|
| settings.json | APP_DIR/ | User preferences |
| app.log | APP_DIR/ | Activity logs (max 1MB) |
| driver/ | APP_DIR/ | UnityCapture/OBS files |

---

*Document Version: 1.0*
*Last Updated: 2026-04-17*