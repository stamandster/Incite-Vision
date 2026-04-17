# Business Requirements Document (BRD)

## Incite Vision - Virtual Camera Manager

### 1. Executive Summary

**Incite Vision** is a Windows desktop application that provides high-performance virtual camera management with seamless switching between webcam and screen capture sources. It targets content creators, streamers, and professionals who need reliable virtual camera functionality for video conferencing, streaming, and recording applications.

### 2. Business Context

- **Problem**: Many video conferencing and streaming applications only support physical webcams, limiting users who want to share screen content or use multiple video sources.
- **Solution**: A virtual camera driver with a GUI manager that allows hotkey-based switching between webcam and screen capture at 60 FPS.
- **Target Market**: Content creators, educators, streamers, remote workers

### 3. Business Objectives

1. Provide a reliable virtual camera driver (UnityCapture/OBS) auto-installation
2. Enable instant source switching via global hotkey
3. Minimize system tray footprint for always-available access
4. Support auto-start with Windows for hands-free operation

### 4. Success Metrics

- Virtual camera appears in all major video applications (Zoom, Teams, OBS, etc.)
- <100ms source switch latency
- 60 FPS steady performance
- Single portable executable distribution

### 5. Competitive Analysis

| Feature | Incite Vision | OBS Virtual Camera | UnityCapture |
|---------|-------------|----------------|-----------|
| GUI Manager | Yes | No | No |
| Hotkey Switch | Yes | Manual | Manual |
| Auto-Install | Yes | Manual | Manual |
| Portable | Yes | No | No |

### 6. Business Risks

- Driver installation requires admin privileges
- May conflict with existing virtual camera drivers
- Some apps cache device list on startup

---

*Document Version: 1.0*
*Last Updated: 2026-04-17*