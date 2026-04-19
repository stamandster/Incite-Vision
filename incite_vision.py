#!/usr/bin/env python3
"""
Incite Vision - Virtual Camera Feed Manager
High-performance virtual camera with multi-source switching,
OpenCL-accelerated compositing, and intelligent fallback.
GUI built with CustomTkinter + pystray system tray.
"""

from __future__ import annotations
import sys
import os
os.environ["OPENCV_LOG_LEVEL"] = "ERROR"
os.environ["OPENCV_VIDEOIO_DEBUG"] = "0"
import json
import time
import threading
import logging
import subprocess
import winreg
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Callable
from datetime import datetime

np = None
cv2 = None
mss = None
pyvirtualcam = None
keyboard = None
pystray = None
Image = None
ctk = None

if getattr(sys, "frozen", False):
    APP_DIR = Path(sys.executable).parent.resolve()
else:
    APP_DIR = Path(__file__).parent.resolve()

SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "incite_vision.log"
DRIVER_DIR = APP_DIR / "driver"

# Create default settings.json if not exists
if not SETTINGS_FILE.exists():
    default_settings = {
        "resolution": [1920, 1080],
        "preferred_monitor_id": 1,
        "preferred_webcam_index": 0,
        "hotkey": "ctrl+alt+s",
        "virtual_backend": "auto",
        "active_source": "webcam",
        "preferred_image": "",
        "start_with_windows": False,
        "auto_start_on_load": False,
        "start_minimized": False,
    }
    with open(SETTINGS_FILE, "w") as f:
        json.dump(default_settings, f, indent=2)
APP_NAME = "Incite Vision"
TARGET_FPS = 60
TRANSITION_DURATION = 0.5
WIN_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

BG_DARK = "#171717"
BG_DEEPER = "#0f0f0f"
BORDER_STD = "#2e2e2e"
BORDER_LIGHT = "#363636"
TEXT_PRIMARY = "#fafafa"
TEXT_SECONDARY = "#b4b4b4"
TEXT_MUTED = "#898989"
ACCENT_GREEN = "#3ecf8e"
ACCENT_GREEN_LINK = "#00c573"

def setup_logging():
    logger = logging.getLogger(APP_NAME)
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(formatter)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

logger = setup_logging()

@dataclass
class Settings:
    resolution: list = field(default_factory=lambda: [1920, 1080])
    preferred_monitor_id: int = 1
    preferred_webcam_index: int = 0
    hotkey: str = "ctrl+alt+s"
    virtual_backend: str = "auto"
    active_source: str = "webcam"
    preferred_image: str = ""
    start_with_windows: bool = False
    auto_start_on_load: bool = False
    start_minimized: bool = False

    @classmethod
    def load(cls) -> "Settings":
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning("Corrupted settings, creating defaults: %s", e)
        settings = cls()
        settings.save()
        return settings

    def save(self):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, indent=2)

def ensure_dependencies():
    global np, cv2, mss, pyvirtualcam, keyboard, pystray, Image, ctk
    required = {
        "pyvirtualcam": "pyvirtualcam",
        "cv2": "opencv-python",
        "mss": "mss",
        "keyboard": "keyboard",
        "customtkinter": "customtkinter",
        "pystray": "pystray",
        "PIL": "Pillow",
        "win32gui": "pywin32",
    }
    missing = []
    for module, pkg in required.items():
        try:
            __import__(module)
        except ImportError:
            missing.append(pkg)
    if missing:
        logger.info("Installing: %s", ", ".join(missing))
        for pkg in missing:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
        logger.info("All dependencies installed")
    import numpy as _np; np = _np
    import cv2 as _cv2; cv2 = _cv2
    import mss as _mss; mss = _mss
    import pyvirtualcam as _vcam; pyvirtualcam = _vcam
    import keyboard as _kb; keyboard = _kb
    import pystray as _tray; pystray = _tray
    from PIL import Image as _Image; Image = _Image
    import customtkinter as _ctk; ctk = _ctk

def discover_webcams() -> Dict[int, str]:
    cameras = {}
    for i in range(16):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ret, frame = cap.read()
            if ret and frame is not None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                cameras[i] = f"Camera {i} ({w}x{h})"
            cap.release()
    return cameras

def discover_monitors() -> Dict[int, dict]:
    with mss.mss() as sct:
        return {i: mon for i, mon in enumerate(sct.monitors)}

def verify_virtual_camera_driver(backend: str = "auto") -> str:
    results = {}
def verify_virtual_camera_driver(backend: str = "auto") -> str:
    results = {}

    def check_key(hkey, path):
        try:
            k = winreg.OpenKey(hkey, path, 0, winreg.KEY_READ)
            winreg.CloseKey(k)
            return True
        except FileNotFoundError:
            return False

    unity_paths = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\UnityCapture"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\UnityCapture"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\UnityCapture"),
        (winreg.HKEY_CLASSES_ROOT, r"UnityCapture"),
    ]
    for hkey, path in unity_paths:
        if check_key(hkey, path):
            results["unity"] = "Unity Video Capture"
            break

    if "unity" not in results:
        dll64 = DRIVER_DIR / "UnityCapture" / "Install" / "UnityCaptureFilter64.dll"
        dll32 = DRIVER_DIR / "UnityCapture" / "Install" / "UnityCaptureFilter32.dll"
        if dll64.exists() or dll32.exists():
            results["unity"] = "Unity Video Capture"

    obs_clsid_paths = [
        r"CLSID\{A35EF1D8-06D0-4A22-BDFD-1E3D1EE0C128}",
        r"CLSID\{B38F332A-58C9-4F5D-88CD-78996A86C7B1}",
        r"CLSID\{B575F9DB-8E5B-4FCB-9A4D-4E5E6F4A5B6C}",
    ]
    for path in obs_clsid_paths:
        if check_key(winreg.HKEY_CLASSES_ROOT, path):
            results["obs"] = "OBS Virtual Camera"
            break

    if "obs" not in results:
        obs_software_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\OBS Studio"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\OBS Studio"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\OBS Studio"),
        ]
        for hkey, path in obs_software_paths:
            if check_key(hkey, path):
                results["obs"] = "OBS Virtual Camera"
                break

    if "obs" not in results or "unity" not in results:
        try:
            clsid_key = winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, r"CLSID", 0, winreg.KEY_READ)
            i = 0
            while i < 200:
                try:
                    subkey = winreg.EnumKey(clsid_key, i)
                    try:
                        sub = winreg.OpenKey(clsid_key, subkey, 0, winreg.KEY_READ)
                        name, _ = winreg.QueryValueEx(sub, "")
                        lname = str(name).lower()
                        if "unity" not in results and (("unity" in lname and "capture" in lname) or "unity video capture" in lname):
                            results["unity"] = str(name)
                        if "obs" not in results and "obs" in lname and "virtual" in lname:
                            results["obs"] = str(name)
                        winreg.CloseKey(sub)
                    except (FileNotFoundError, OSError):
                        pass
                    i += 1
                except OSError:
                    break
            winreg.CloseKey(clsid_key)
        except (FileNotFoundError, OSError):
            pass

    if backend == "auto":
        if "unity" in results:
            return "unity"
        if "obs" in results:
            return "obs"
    elif backend in results:
        return backend
    return ""

def trigger_driver_install(backend: str = "unity"):
    if backend == "unity":
        target = DRIVER_DIR / "UnityCapture"
        if not target.exists():
            logger.info("Installing UnityCapture...")
            git_available = subprocess.run(["git", "--version"], capture_output=True).returncode == 0
            if git_available:
                subprocess.run(["git", "clone", "https://github.com/schellingb/UnityCapture.git", str(target)],
                             capture_output=True)
            else:
                zip_path = DRIVER_DIR / "UnityCapture.zip"
                logger.info("Git not found, downloading ZIP...")
                try:
                    import urllib.request
                    urllib.request.urlretrieve(
                        "https://github.com/schellingb/UnityCapture/archive/refs/heads/master.zip",
                        str(zip_path))
                    import zipfile
                    with zipfile.ZipFile(zip_path, "r") as z:
                        z.extractall(DRIVER_DIR)
                    target = DRIVER_DIR / "UnityCapture-master"
                    (DRIVER_DIR / "UnityCapture").rename(target)
                    zip_path.unlink()
                except Exception as e:
                    logger.error("ZIP download failed: %s", e)
                    import webbrowser
                    webbrowser.open("https://github.com/schellingb/UnityCapture")
                    return
        if not target.exists():
            logger.error("UnityCapture not found at %s", target)
            import webbrowser
            webbrowser.open("https://github.com/schellingb/UnityCapture")
            return
        installer = target / "Install" / "Install.bat"
        if not installer.exists():
            logger.error("Install.bat not found at %s", installer)
            return
        install_dir = target / "Install"
        logger.info("Running UnityCapture installer from %s (admin may be required)...", install_dir)
        try:
            import ctypes
            result = ctypes.windll.shell32.ShellExecuteW(
                None, "runas", str(installer), None, str(install_dir), 1)
            if result <= 32:
                raise RuntimeError(f"ShellExecuteW returned {result}")
        except Exception as e:
            logger.warning("Elevated launch failed (%s), trying normal launch", e)
            subprocess.Popen(["cmd", "/c", "start", "cmd", "/k", str(installer)], shell=True)
    else:
        logger.info("Installing OBS Virtual Camera...")
        obs_dir = DRIVER_DIR / "OBS-Studio"
        obs_installer = obs_dir / "obs-installer.exe"
        if not obs_installer.exists():
            obs_dir.mkdir(exist_ok=True)
            logger.info("Downloading OBS Studio installer...")
            try:
                import urllib.request, zipfile, os as _os
                obs_url = "https://github.com/obsproject/obs-studio/releases/download/30.1.2/obs-studio-30.1.2-fullstaller-x64.exe"
                urllib.request.urlretrieve(obs_url, str(obs_installer))
                logger.info("OBS Studio downloaded")
            except Exception as e:
                logger.error("OBS download failed: %s", e)
                import webbrowser
                webbrowser.open("https://obsproject.com")
                return
        if obs_installer.exists():
            logger.info("Running OBS Studio installer (admin may be required)...")
            try:
                import ctypes
                result = ctypes.windll.shell32.ShellExecuteW(
                    None, "runas", str(obs_installer),
                    "/S /NORESTART /CLOSEAPPLICATIONS /RESTARTAPPLICATIONS", str(obs_dir), 1)
                if result <= 32:
                    raise RuntimeError(f"ShellExecuteW returned {result}")
            except Exception as e:
                logger.warning("Elevated launch failed (%s), trying normal launch", e)
                subprocess.Popen([str(obs_installer), "/S"], shell=True)

def set_start_with_windows(enabled: bool):
    try:
        import win32gui, win32con
        exe_path = sys.executable if getattr(sys, "frozen", False) else sys.argv[0]
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, WIN_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}" --silent')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        logger.error("Failed to set startup entry: %s", e)

def letterbox_fit(frame, target_w: int, target_h: int):
    h, w = frame.shape[:2]
    src_aspect = w / h
    dst_aspect = target_w / target_h
    if abs(src_aspect - dst_aspect) < 0.001:
        try:
            return cv2.resize(cv2.UMat(frame), (target_w, target_h)).get()
        except cv2.error:
            return cv2.resize(frame, (target_w, target_h))
    if src_aspect > dst_aspect:
        new_w, new_h = target_w, int(target_w / src_aspect)
    else:
        new_h, new_w = target_h, int(target_h * src_aspect)
    try:
        resized = cv2.resize(cv2.UMat(frame), (new_w, new_h)).get()
    except cv2.error:
        resized = cv2.resize(frame, (new_w, new_h))
    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    y_off = (target_h - new_h) // 2
    x_off = (target_w - new_w) // 2
    canvas[y_off:y_off+new_h, x_off:x_off+new_w] = resized
    return canvas

def generate_offline_frame(width: int, height: int):
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (30, 30, 30)
    cv2.putText(frame, "INCITE VISION OFFLINE", (width // 5, height // 2 - 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3, cv2.LINE_AA)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cv2.putText(frame, ts, (width // 3, height // 2 + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 200, 200), 2, cv2.LINE_AA)
    return frame

def generate_black_frame(width: int, height: int):
    return np.zeros((height, width, 3), dtype=np.uint8)

def load_image_file(filepath: str, width: int, height: int):
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        img = cv2.imread(filepath)
        if img is None:
            return None
        return letterbox_fit(img, width, height)
    except Exception as e:
        logger.warning("Failed to load image %s: %s", filepath, e)
        return None

class WebcamThread(threading.Thread):
    def __init__(self, camera_index: int, width: int, height: int):
        super().__init__(daemon=True)
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.cap = None
        self._frame = None
        self._lock = threading.Lock()
        self._running = False
        self.available = False

    def run(self):
        self._running = True
        self.cap = cv2.VideoCapture(self.camera_index)
        if not self.cap.isOpened():
            self.available = False
            return
        ret, frame = self.cap.read()
        if not ret or frame is None:
            self.cap.release()
            self.cap = None
            self.available = False
            return
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self.cap.set(cv2.CAP_PROP_FPS, TARGET_FPS)
        self.available = True
        logger.info("Webcam %d opened at %dx%d", self.camera_index, self.width, self.height)
        while self._running:
            ret, frame = self.cap.read()
            if ret:
                with self._lock:
                    self._frame = frame
            else:
                self.available = False
                time.sleep(0.01)

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self):
        self._running = False
        if self.cap:
            self.cap.release()

class ScreenCaptureThread(threading.Thread):
    def __init__(self, monitor_id: int, width: int, height: int):
        super().__init__(daemon=True)
        self.monitor_id = monitor_id
        self.target_width = width
        self.target_height = height
        self._frame = None
        self._lock = threading.Lock()
        self._running = False

    def run(self):
        self._running = True
        with mss.mss() as sct:
            monitors = sct.monitors
            if self.monitor_id >= len(monitors):
                self.monitor_id = 1
            monitor = monitors[self.monitor_id]
            frame_interval = 1.0 / TARGET_FPS
            while self._running:
                loop_start = time.time()
                try:
                    screenshot = sct.grab(monitor)
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    if frame.shape[1] != self.target_width or frame.shape[0] != self.target_height:
                        frame = letterbox_fit(frame, self.target_width, self.target_height)
                    with self._lock:
                        self._frame = frame
                except Exception as e:
                    logger.error("Screen capture error: %s", e)
                    time.sleep(0.01)
                elapsed = time.time() - loop_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

    def get_frame(self):
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    def stop(self):
        self._running = False

class VirtualCameraManager:
    def __init__(self, settings: Settings, backend: str, on_status: Callable = None):
        self.settings = settings
        self.backend = backend
        self.width, self.height = settings.resolution
        self.current_source = settings.active_source
        self.target_source = settings.active_source
        self.transitioning = False
        self.transition_start = 0.0
        self.webcam_thread = None
        self.screen_thread = None
        self.vcam = None
        self._running = False
        self._lock = threading.Lock()
        self.on_status = on_status
        self._warmup_end = 0.0
        self._image_frame = None
        self._load_image_frame()

    def _load_image_frame(self):
        if self.settings.preferred_image:
            self._image_frame = load_image_file(self.settings.preferred_image, self.width, self.height)
            if self._image_frame is not None:
                logger.info("Loaded image %s (%dx%d)", self.settings.preferred_image, self._image_frame.shape[1], self._image_frame.shape[0])
            else:
                logger.warning("Failed to load image from %s, will use black", self.settings.preferred_image)

    def reload_image(self):
        self._load_image_frame()

    def initialize(self):
        logger.info("Initializing at %dx%d", self.width, self.height)
        webcams = discover_webcams()
        monitors = discover_monitors()
        webcam_index = self.settings.preferred_webcam_index
        if webcam_index not in webcams and webcams:
            webcam_index = list(webcams.keys())[0]
        monitor_id = self.settings.preferred_monitor_id
        if monitor_id >= len(monitors):
            monitor_id = 1
        self.webcam_thread = WebcamThread(webcam_index, self.width, self.height)
        self.webcam_thread.start()
        self.screen_thread = ScreenCaptureThread(monitor_id, self.width, self.height)
        self.screen_thread.start()
        
        # Wait for the selected source to become available
        wait_start = time.time()
        source_ready = False
        while time.time() - wait_start < 5.0:
            if self.current_source == "webcam":
                # Check if webcam is ready
                if self.webcam_thread.get_frame() is not None:
                    source_ready = True
                    break
                # If webcam not ready but screen is, check if webcam thread is still alive
                elif self.screen_thread.get_frame() is not None:
                    if not self.webcam_thread.is_alive():
                        # Webcam thread died, fall back to screen
                        logger.warning("Webcam thread failed, falling back to screen")
                        self.current_source = "screen"
                        self.target_source = "screen"
                        self.settings.active_source = "screen"
                        self.settings.save()
                        source_ready = True
                        break
                # Both not ready yet, continue waiting
                time.sleep(0.1)
            else:  # current_source == "screen"
                # Check if screen is ready
                if self.screen_thread.get_frame() is not None:
                    source_ready = True
                    break
                # If screen not ready but webcam is, check if screen thread is still alive
                elif self.webcam_thread.get_frame() is not None:
                    if not self.screen_thread.is_alive():
                        # Screen thread died, fall back to webcam
                        logger.warning("Screen thread failed, falling back to webcam")
                        self.current_source = "webcam"
                        self.target_source = "webcam"
                        self.settings.active_source = "webcam"
                        self.settings.save()
                        source_ready = True
                        break
                # Both not ready yet, continue waiting
                time.sleep(0.1)
        
        # If still not ready after timeout, check what's available
        if not source_ready:
            webcam_frame = self.webcam_thread.get_frame()
            screen_frame = self.screen_thread.get_frame()
            if webcam_frame is not None:
                logger.warning("Timeout waiting for selected source, falling back to webcam")
                self.current_source = "webcam"
                self.target_source = "webcam"
                self.settings.active_source = "webcam"
                self.settings.save()
            elif screen_frame is not None:
                logger.warning("Timeout waiting for selected source, falling back to screen")
                self.current_source = "screen"
                self.target_source = "screen"
                self.settings.active_source = "screen"
                self.settings.save()
            else:
                logger.error("No source available after initialization timeout")
                self.current_source = "offline"
                self.target_source = "offline"
                self.settings.save()
        vcam_kwargs = dict(width=self.width, height=self.height, fps=TARGET_FPS, fmt=pyvirtualcam.PixelFormat.BGR)
        if self.backend == "unity":
            vcam_kwargs["device"] = "Unity Video Capture"
        elif self.backend == "obs":
            vcam_kwargs["device"] = "OBS Virtual Camera"
        self.vcam = pyvirtualcam.Camera(**vcam_kwargs)
        logger.info("Virtual camera opened: %s @ %d FPS", self.vcam.device, TARGET_FPS)
        if self.on_status:
            self.on_status("running", f"Streaming @ {TARGET_FPS} FPS via {self.vcam.device}")

    def _get_frame_for_source(self, source: str):
        if source == "webcam" and self.webcam_thread and self.webcam_thread.available:
            return self.webcam_thread.get_frame()
        elif source == "screen" and self.screen_thread:
            screen_frame = self.screen_thread.get_frame()
            if screen_frame is not None:
                return screen_frame
        elif source == "image":
            if self._image_frame is not None:
                return self._image_frame
            return generate_black_frame(self.width, self.height)
        return None

    def switch_to_source(self, source: str):
        with self._lock:
            if self.transitioning:
                return
            if source not in ("webcam", "screen", "image"):
                return
            if source == "webcam" and (not self.webcam_thread or not self.webcam_thread.available):
                if self.on_status:
                    self.on_status("warning", "Webcam not available")
                return
            self.target_source = source
            self.transitioning = True
            self.transition_start = time.time()
            logger.info("Switching to '%s'", source)
            if self.on_status:
                self.on_status("transition", f"Switching to {source}")

    def _resize(self, frame):
        if frame.shape[1] == self.width and frame.shape[0] == self.height:
            return frame
        return letterbox_fit(frame, self.width, self.height)

    def _blend_frames(self, frame_a, frame_b, alpha: float):
        try:
            umat_a = cv2.UMat(frame_a.astype(np.float32))
            umat_b = cv2.UMat(frame_b.astype(np.float32))
            blended = cv2.addWeighted(umat_a, 1.0 - alpha, umat_b, alpha, 0)
            return blended.get().astype(np.uint8)
        except cv2.error:
            return (frame_a * (1.0 - alpha) + frame_b * alpha).astype(np.uint8)

    def handle_hotkey(self):
        with self._lock:
            if self.transitioning:
                return
            if self.current_source == "webcam":
                self.target_source = "screen"
            elif self.current_source == "screen":
                if self.webcam_thread and self.webcam_thread.available:
                    self.target_source = "webcam"
                else:
                    return
            else:
                if self.webcam_thread and self.webcam_thread.available:
                    self.target_source = "webcam"
                elif self.screen_thread:
                    self.target_source = "screen"
                else:
                    return
            self.transitioning = True
            self.transition_start = time.time()
            logger.info("Transitioning '%s' -> '%s'", self.current_source, self.target_source)
            if self.on_status:
                self.on_status("transition", f"Switching {self.current_source} -> {self.target_source}")

    def _process_transition(self):
        if not self.transitioning:
            return None
        elapsed = time.time() - self.transition_start
        progress = min(elapsed / TRANSITION_DURATION, 1.0)
        frame_from = self._get_frame_for_source(self.current_source)
        frame_to = self._get_frame_for_source(self.target_source)
        if frame_from is None or frame_to is None:
            self.transitioning = False
            self.current_source = self.target_source
            return None
        frame_from = self._resize(frame_from)
        frame_to = self._resize(frame_to)
        blended = self._blend_frames(frame_from, frame_to, progress)
        if progress >= 1.0:
            self.current_source = self.target_source
            self.settings.active_source = self.current_source
            self.settings.save()
            self.transitioning = False
            logger.info("Transition complete: '%s'", self.current_source)
            if self.on_status:
                self.on_status("running", f"Source: {self.current_source}")
        return blended

    def _check_fallback(self):
        if self.current_source == "webcam":
            if not self.webcam_thread or not self.webcam_thread.available:
                if self.screen_thread:
                    logger.warning("Webcam unplugged -> screen capture")
                    self.current_source = "screen"
                    self.target_source = "screen"
                    self.settings.active_source = "screen"
                    self.settings.save()
                    if self.on_status:
                        self.on_status("warning", "Webcam unplugged, switched to screen")
                else:
                    self.current_source = "offline"
                    if self.on_status:
                        self.on_status("offline", "All sources failed")

    def send_offline_frame(self):
        if self.vcam:
            offline = generate_offline_frame(self.width, self.height)
            try:
                self.vcam.send(offline)
                self.vcam.sleep_until_next_frame()
            except Exception:
                pass

    def run(self):
        self._running = True
        self._warmup_end = time.time() + 3.0
        keyboard.add_hotkey(self.settings.hotkey, self.handle_hotkey, suppress=True)
        keyboard.add_hotkey("ctrl+alt+1", lambda: self.switch_to_source("webcam"), suppress=True)
        keyboard.add_hotkey("ctrl+alt+2", lambda: self.switch_to_source("screen"), suppress=True)
        keyboard.add_hotkey("ctrl+alt+3", lambda: self.switch_to_source("image"), suppress=True)
        logger.info("Hotkeys registered: %s, Ctrl+Alt+1/2/3", self.settings.hotkey)
        frame_interval = 1.0 / TARGET_FPS
        try:
            while self._running:
                loop_start = time.time()
                if time.time() > self._warmup_end:
                    self._check_fallback()
                frame = self._process_transition()
                if frame is None:
                    frame = self._get_frame_for_source(self.current_source)
                if frame is None:
                    if self.current_source == "webcam" and self.screen_thread:
                        self.current_source = "screen"
                        frame = self._get_frame_for_source("screen")
                    elif self.current_source == "screen" and self.webcam_thread and self.webcam_thread.available:
                        self.current_source = "webcam"
                        frame = self._get_frame_for_source("webcam")
                    elif self.current_source in ("webcam", "screen") and self._image_frame is not None:
                        self.current_source = "image"
                        frame = self._image_frame
                if frame is None:
                    frame = generate_offline_frame(self.width, self.height)
                    if self.current_source != "offline":
                        self.current_source = "offline"
                        if self.on_status:
                            self.on_status("offline", "No source available")
                else:
                    frame = self._resize(frame)
                if self.vcam:
                    try:
                        self.vcam.send(frame)
                    except Exception:
                        time.sleep(0.1)
                elapsed = time.time() - loop_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        except KeyboardInterrupt:
            pass
        finally:
            self.shutdown()

    def shutdown(self):
        logger.info("Shutting down...")
        self._running = False
        try:
            keyboard.remove_hotkey(self.settings.hotkey)
            keyboard.remove_hotkey("ctrl+alt+1")
            keyboard.remove_hotkey("ctrl+alt+2")
            keyboard.remove_hotkey("ctrl+alt+3")
        except Exception:
            pass
        self.send_offline_frame()
        if self.webcam_thread:
            self.webcam_thread.stop()
            self.webcam_thread.join(timeout=2.0)
        if self.screen_thread:
            self.screen_thread.stop()
            self.screen_thread.join(timeout=2.0)
        if self.vcam:
            try:
                self.vcam.close()
            except Exception:
                pass
        if self.on_status:
            self.on_status("stopped", "Stopped")
        logger.info("All resources released")

def create_tray_icon(image_data, on_quit, on_show, on_click):
    def get_menu(app):
        is_running = app._running if app else False
        return pystray.Menu(
            pystray.MenuItem("Show Window", on_click, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start Streaming" if not is_running else "Stop Streaming", 
                         lambda i, it: (app.after(0, app._on_toggle), app.after(0, lambda: app.tray_icon and app.tray_icon.update_menu()))),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", on_quit),
        )
    icon = pystray.Icon("incite_vision", image_data, APP_NAME)
    icon._on_quit = on_quit
    icon._on_show = on_show
    icon._get_menu = get_menu
    return icon

def create_tray_image(color, size=64):
    from PIL import ImageDraw
    img = Image.new("RGB", (size, size), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)
    points = [(size*0.25, size*0.15), (size*0.5, size*0.85), (size*0.75, size*0.15)]
    draw.polygon(points, fill=color, outline=color)
    return img

def create_app_class():
    """Factory: build the GUI class after ctk is loaded."""

    class InciteVisionApp(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.manager = None
            self.manager_thread = None
            self.tray_icon = None
            self.tray_thread = None
            self.settings = Settings.load()
            self._running = False
            self._webcam_map = {}
            self._monitor_map = {}
            self._minimized_to_tray = False

            ctk.set_appearance_mode("dark")
            ctk.set_default_color_theme("dark-blue")

            self.title(APP_NAME)
            self.geometry("800x750")
            self.minsize(750, 700)
            self.configure(fg_color=BG_DARK)
            self.protocol("WM_DELETE_WINDOW", self.on_window_close)
            self._build_layout()
            self._load_hardware()
            self._apply_settings()
            self._update_status("stopped", "Ready")
            if self.settings.start_minimized:
                self._minimized_to_tray = True
                self.withdraw()
            if self.settings.auto_start_on_load:
                self._minimized_to_tray = True
                self.after(500, self._on_start)

        def _build_layout(self):
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)

            sidebar = ctk.CTkFrame(self, width=220, fg_color=BG_DEEPER, corner_radius=0, border_color=BORDER_STD, border_width=1)
            sidebar.grid(row=0, column=0, sticky="nsew")
            sidebar.grid_columnconfigure(0, weight=1)

            logo_label = ctk.CTkLabel(sidebar, text=APP_NAME, font=ctk.CTkFont(size=16, weight="bold"), text_color=ACCENT_GREEN)
            logo_label.grid(row=0, column=0, padx=16, pady=(16, 4), sticky="w")
            subtitle = ctk.CTkLabel(sidebar, text="Virtual Camera", font=ctk.CTkFont(size=10), text_color=TEXT_MUTED)
            subtitle.grid(row=1, column=0, padx=16, pady=(0, 12), sticky="w")
            sep = ctk.CTkFrame(sidebar, height=1, fg_color=BORDER_STD)
            sep.grid(row=2, column=0, padx=16, pady=(0, 8), sticky="ew")

            r = 3
            def add_label(text):
                nonlocal r
                lbl = ctk.CTkLabel(sidebar, text=text, font=ctk.CTkFont(size=10), text_color=TEXT_SECONDARY, anchor="w")
                lbl.grid(row=r, column=0, padx=16, pady=(6, 1), sticky="ew")
                r += 1
                return lbl

            def add_dropdown(var, values, command=None):
                nonlocal r
                dd = ctk.CTkOptionMenu(sidebar, variable=var, values=values, command=command,
                                       fg_color=BG_DARK, button_color=BG_DARK, button_hover_color=BORDER_LIGHT,
                                       dropdown_fg_color=BG_DEEPER, dropdown_hover_color=BORDER_STD,
                                       text_color=TEXT_PRIMARY, corner_radius=4)
                dd.grid(row=r, column=0, padx=16, pady=(1, 2), sticky="ew")
                r += 1
                return dd

            def add_entry(var, placeholder=""):
                nonlocal r
                ent = ctk.CTkEntry(sidebar, textvariable=var, placeholder_text=placeholder,
                                   fg_color=BG_DARK, border_color=BORDER_STD, corner_radius=4,
                                   text_color=TEXT_PRIMARY)
                ent.grid(row=r, column=0, padx=16, pady=(1, 2), sticky="ew")
                r += 1
                return ent

            add_label("SOURCE")
            self.var_source = ctk.StringVar(value=self.settings.active_source.title())
            self.dd_source = add_dropdown(self.var_source, ["Webcam", "Screen", "Image"], self._on_source_change)

            add_label("IMAGE")
            img_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
            img_frame.grid(row=r, column=0, padx=16, pady=(1, 2), sticky="ew")
            img_frame.grid_columnconfigure(0, weight=1)
            self.var_image = ctk.StringVar(value=self.settings.preferred_image or "No image selected")
            img_entry = ctk.CTkEntry(img_frame, textvariable=self.var_image, placeholder_text="No image selected",
                                     fg_color=BG_DARK, border_color=BORDER_STD, corner_radius=4,
                                     text_color=TEXT_PRIMARY)
            img_entry.grid(row=0, column=0, sticky="ew")
            btn_browse = ctk.CTkButton(img_frame, text="...", width=30, command=self._on_browse_image,
                                       fg_color=BG_DARK, hover_color=BORDER_STD, text_color=TEXT_PRIMARY, corner_radius=4)
            btn_browse.grid(row=0, column=1, padx=(4, 0))
            r += 1

            add_label("RESOLUTION")
            self.var_resolution = ctk.StringVar(value=f"{self.settings.resolution[0]}x{self.settings.resolution[1]}")
            add_dropdown(self.var_resolution, ["1920x1080", "1280x720", "2560x1440", "3840x2160", "640x480"])

            add_label("MONITOR")
            self.var_monitor = ctk.StringVar(value="Loading...")
            self.dd_monitor = add_dropdown(self.var_monitor, ["Loading..."])

            add_label("WEBCAM")
            self.var_webcam = ctk.StringVar(value="Loading...")
            self.dd_webcam = add_dropdown(self.var_webcam, ["Loading..."])

            add_label("BACKEND")
            self.var_backend = ctk.StringVar(value="Detecting...")
            self.dd_backend = add_dropdown(self.var_backend, ["Detecting..."], command=self._on_backend_change)

            add_label("HOTKEY")
            self.var_hotkey = ctk.StringVar(value=self.settings.hotkey)
            add_entry(self.var_hotkey, "e.g. ctrl+alt+s")

            r += 1
            self.var_startup = ctk.BooleanVar(value=self.settings.start_with_windows)
            cb_startup = ctk.CTkCheckBox(sidebar, text="Start with Windows", variable=self.var_startup,
                                         fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_LINK,
                                         text_color=TEXT_PRIMARY, corner_radius=4,
                                         command=self._on_startup_changed)
            cb_startup.grid(row=r, column=0, padx=16, pady=(8, 2), sticky="w")

            r += 1
            self.var_autostart = ctk.BooleanVar(value=self.settings.auto_start_on_load)
            cb_autostart = ctk.CTkCheckBox(sidebar, text="Auto-start on load", variable=self.var_autostart,
                                           fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_LINK,
                                           text_color=TEXT_PRIMARY, corner_radius=4,
                                           command=self._on_autostart_changed)
            cb_autostart.grid(row=r, column=0, padx=16, pady=(2, 2), sticky="w")

            r += 1
            self.var_minimized = ctk.BooleanVar(value=self.settings.start_minimized)
            cb_minimized = ctk.CTkCheckBox(sidebar, text="Start minimized", variable=self.var_minimized,
                                           fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_LINK,
                                           text_color=TEXT_PRIMARY, corner_radius=4,
                                           command=self._on_minimized_changed)
            cb_minimized.grid(row=r, column=0, padx=16, pady=(2, 2), sticky="w")

            r += 1
            sep2 = ctk.CTkFrame(sidebar, height=1, fg_color=BORDER_STD)
            sep2.grid(row=r, column=0, padx=16, pady=(8, 8), sticky="ew")
            r += 1

            self.btn_install = ctk.CTkButton(sidebar, text="Install Driver", command=self._on_install_driver,
                                            fg_color="transparent", border_color=ACCENT_GREEN, border_width=2,
                                            hover_color=BORDER_STD, text_color=ACCENT_GREEN,
                                            font=ctk.CTkFont(size=12, weight="bold"), corner_radius=9999, height=30)
            self.btn_install.grid(row=r, column=0, padx=16, pady=(2, 2), sticky="ew")
            r += 1

            self.btn_toggle = ctk.CTkButton(sidebar, text="START", command=self._on_toggle,
                                            fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_LINK,
                                            text_color=BG_DEEPER, font=ctk.CTkFont(size=13, weight="bold"),
                                            corner_radius=9999, height=34)
            self.btn_toggle.grid(row=r, column=0, padx=16, pady=(4, 8), sticky="ew")

            main = ctk.CTkFrame(self, fg_color=BG_DARK, corner_radius=0)
            main.grid(row=0, column=1, sticky="nsew")
            main.grid_columnconfigure(0, weight=1)
            main.grid_rowconfigure(5, weight=1)

            status_box = ctk.CTkFrame(main, fg_color="transparent")
            status_box.grid(row=0, column=0, pady=(20, 0))
            status_box.grid_columnconfigure(0, weight=1)

            self.status_title = ctk.CTkLabel(status_box, text="Ready", font=ctk.CTkFont(size=18, weight="bold"), text_color=ACCENT_GREEN)
            self.status_title.grid(row=0, column=0, pady=(0, 2))
            self.status_detail = ctk.CTkLabel(status_box, text="Configure settings and press START", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED)
            self.status_detail.grid(row=1, column=0, pady=(0, 8))

            info_box = ctk.CTkFrame(status_box, fg_color=BG_DEEPER, corner_radius=4)
            info_box.grid(row=2, column=0, padx=20, ipady=4)
            info_grid = ctk.CTkFrame(info_box, fg_color="transparent")
            info_grid.grid(row=0, column=0, padx=12, pady=4)

            self.status_source = ctk.CTkLabel(info_grid, text="Source: --", font=ctk.CTkFont(size=10, family="Consolas"), text_color=TEXT_SECONDARY)
            self.status_source.grid(row=0, column=0, padx=(0, 16))
            self.status_fps = ctk.CTkLabel(info_grid, text="FPS: --", font=ctk.CTkFont(size=10, family="Consolas"), text_color=TEXT_SECONDARY)
            self.status_fps.grid(row=0, column=1, padx=(0, 16))
            self.status_backend = ctk.CTkLabel(info_grid, text="Backend: --", font=ctk.CTkFont(size=10, family="Consolas"), text_color=TEXT_SECONDARY)
            self.status_backend.grid(row=0, column=2)

            log_frame = ctk.CTkFrame(main, fg_color=BG_DEEPER, corner_radius=4, border_color=BORDER_STD, border_width=1)
            log_frame.grid(row=5, column=0, padx=12, pady=(8, 12), sticky="nsew")
            log_frame.grid_columnconfigure(0, weight=1)
            log_frame.grid_rowconfigure(1, weight=1)

            log_label = ctk.CTkLabel(log_frame, text="ACTIVITY LOG", font=ctk.CTkFont(size=9, family="Consolas"), text_color=TEXT_MUTED)
            log_label.grid(row=0, column=0, padx=8, pady=(4, 0), sticky="w")
            self.log_text = ctk.CTkTextbox(log_frame, font=ctk.CTkFont(size=9, family="Consolas"), text_color=TEXT_SECONDARY, fg_color=BG_DEEPER, border_width=0)
            self.log_text.grid(row=1, column=0, padx=8, pady=(2, 4), sticky="nsew")
            self.log_text.configure(state="disabled")

        def _log(self, msg):
            self.log_text.configure(state="normal")
            self.log_text.insert("end", msg + "\n")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        def _load_hardware(self):
            self._log("[CONFIG] Loading settings...")
            webcams = discover_webcams()
            monitors = discover_monitors()
            
            # Build webcam maps: index <-> label
            self._webcam_map = dict(webcams)
            self._webcam_map_reverse = {v: k for k, v in webcams.items()}
            cam_values = list(webcams.values()) if webcams else ["No webcam detected"]
            self.dd_webcam.configure(values=cam_values)
            
            # Try to restore saved webcam index
            saved_idx = self.settings.preferred_webcam_index
            saved_cam = webcams.get(saved_idx)
            self.var_webcam.set(saved_cam if saved_cam else (cam_values[0] if cam_values else "No webcam detected"))

            # Build monitor maps: index <-> label  
            mon_values = []
            self._monitor_map = {}
            self._monitor_map_reverse = {}
            for i, mon in monitors.items():
                if i == 0:
                    label = f"Monitor {i} - All screens ({mon['width']}x{mon['height']})"
                else:
                    label = f"Monitor {i} - {mon['width']}x{mon['height']}"
                mon_values.append(label)
                self._monitor_map[i] = label
                self._monitor_map_reverse[label] = i
            self.dd_monitor.configure(values=mon_values)
            
# Try to restore saved monitor index  
            saved_idx = self.settings.preferred_monitor_id
            saved_mon = monitors.get(saved_idx)
            label = None
            if saved_mon:
                if saved_idx == 0:
                    label = f"Monitor {saved_idx} - All screens ({saved_mon['width']}x{saved_mon['height']})"
                else:
                    label = f"Monitor {saved_idx} - {saved_mon['width']}x{saved_mon['height']}"
            self.var_monitor.set(label if label else (mon_values[0] if mon_values else "No monitor detected"))
            self._log(f"[CONFIG] Webcam: {self.var_webcam.get()}")
            self._log(f"[CONFIG] Monitor: {self.var_monitor.get()}")
            self._log(f"[CONFIG] Auto-start on load: {'enabled' if self.settings.auto_start_on_load else 'disabled'}")
            self._log(f"[CONFIG] Start with Windows: {'enabled' if self.settings.start_with_windows else 'disabled'}")
 
        def _apply_settings(self):
            self._backend_map = {
                "Unity Video Capture": "unity",
                "OBS Virtual Camera": "obs",
                "Auto-detect": "auto",
            }
            self._detected_drivers = set()
            for b in ["unity", "obs"]:
                r = verify_virtual_camera_driver(b)
                if r:
                    self._detected_drivers.add(b)
            options = ["Unity Video Capture", "OBS Virtual Camera", "Auto-detect"]
            self.dd_backend.configure(values=options)
            if "unity" in self._detected_drivers:
                self.var_backend.set("Unity Video Capture")
            elif "obs" in self._detected_drivers:
                self.var_backend.set("OBS Virtual Camera")
            else:
                self.var_backend.set("Unity Video Capture")
            self._on_backend_change(self.var_backend.get())
            self.var_startup.set(self.settings.start_with_windows)

        def _on_backend_change(self, value):
            key = self._backend_map.get(value, "auto")
            if key == "auto":
                self.btn_install.configure(state="disabled", text="Auto-detect (select a driver)")
                return
            actual = verify_virtual_camera_driver(key)
            if actual:
                self.btn_install.configure(state="disabled", text=f"{value} (installed)")
            else:
                self.btn_install.configure(state="normal", text=f"Install {value} Driver")

        def _on_install_driver(self):
            display = self.var_backend.get()
            backend = self._backend_map.get(display, "auto")
            self._log(f"[INFO] Installing {backend} -- check for UAC prompt...")
            trigger_driver_install(backend)
            self.var_backend.set("Install triggered -- restart app after install")
            self.btn_install.configure(state="disabled", text="Restart app after install")

        def _update_status(self, state: str, detail: str):
            prev_running = self._running
            if state == "running":
                self.status_title.configure(text="RUNNING", text_color="#ef4444")
                self.status_detail.configure(text=detail)
                self.btn_toggle.configure(text="STOP", fg_color="#ef4444", hover_color="#dc2626")
                self._running = True
            elif state == "stopped":
                self.status_title.configure(text="STOPPED", text_color=ACCENT_GREEN)
                self.status_detail.configure(text=detail)
                self.btn_toggle.configure(text="START", fg_color=ACCENT_GREEN, hover_color=ACCENT_GREEN_LINK)
                self._running = False
            else:
                colors = {"transition": "#facc15", "warning": "#f97316", "offline": "#ef4444"}
                color = colors.get(state, TEXT_SECONDARY)
                self.status_title.configure(text=state.upper(), text_color=color)
                self.status_detail.configure(text=detail)
            self._log(f"[{state.upper()}] {detail}")
            if self.tray_icon:
                self.tray_icon.title = f"{APP_NAME} - {state.upper()}"
                if prev_running != self._running:
                    try:
                        self.tray_icon.menu = self.tray_icon._get_menu(self)
                    except Exception:
                        pass

        def _on_startup_changed(self):
            self.settings.start_with_windows = self.var_startup.get()
            self.settings.save()
            set_start_with_windows(self.settings.start_with_windows)
            self._log(f"[CONFIG] Start with Windows: {'enabled' if self.settings.start_with_windows else 'disabled'}")

        def _on_autostart_changed(self):
            self.settings.auto_start_on_load = self.var_autostart.get()
            self.settings.save()
            self._log(f"[CONFIG] Auto-start on load: {'enabled' if self.settings.auto_start_on_load else 'disabled'}")

        def _on_minimized_changed(self):
            self.settings.start_minimized = self.var_minimized.get()
            self.settings.save()
            self._log(f"[CONFIG] Start minimized: {'enabled' if self.settings.start_minimized else 'disabled'}")

        def _on_source_change(self, value):
            self.settings.active_source = value.lower()
            self.settings.save()
            self._log(f"[CONFIG] Source: {value}")

        def _on_browse_image(self):
            from tkinter import filedialog
            filepath = filedialog.askopenfilename(title="Select Image",
                                                  filetypes=[("Image files", "*.png *.jpg *.jpeg *.bmp *.gif"), ("All files", "*.*")])
            if filepath:
                self.settings.preferred_image = filepath
                self.var_image.set(filepath)
                self.settings.save()
                if self.manager:
                    self.manager.reload_image()
                self._log(f"[CONFIG] Image: {filepath}")

        def _on_start(self):
            if self._running:
                return
            res_str = self.var_resolution.get()
            w, h = res_str.split("x")
            self.settings.resolution = [int(w), int(h)]
            mon_label = self.var_monitor.get()
            self.settings.preferred_monitor_id = self._monitor_map_reverse.get(mon_label, 1)
            cam_label = self.var_webcam.get()
            self.settings.preferred_webcam_index = self._webcam_map_reverse.get(cam_label, 0)
            self.settings.hotkey = self.var_hotkey.get() or "ctrl+alt+s"
            self.settings.virtual_backend = self._backend_map.get(self.var_backend.get(), "auto")
            self.settings.active_source = self.var_source.get().lower()
            self.settings.preferred_image = self.var_image.get() if self.var_image.get() != "No image selected" else ""
            self.settings.start_with_windows = self.var_startup.get()
            self.settings.auto_start_on_load = self.var_autostart.get()
            set_start_with_windows(self.settings.start_with_windows)
            self.settings.save()

            backend = verify_virtual_camera_driver(self.settings.virtual_backend)
            if not backend:
                self._update_status("warning", "No virtual camera driver found. Install UnityCapture or OBS.")
                trigger_driver_install(self.settings.virtual_backend)
                return

            self.status_source.configure(text=f"Source: {self.settings.active_source}")
            self.status_fps.configure(text=f"FPS: {TARGET_FPS}")
            self.status_backend.configure(text=f"Backend: {backend}")

            self.manager = VirtualCameraManager(self.settings, backend, on_status=self._update_status)
            self.manager.initialize()
            self.manager_thread = threading.Thread(target=self.manager.run, daemon=True)
            self.manager_thread.start()
            self._update_status("running", f"Streaming @ {TARGET_FPS} FPS via {backend}")

        def _on_toggle(self):
            if self._running:
                self._on_stop()
            else:
                self._on_start()

        def _on_stop(self):
            if self.manager:
                self.manager.shutdown()
                self.manager = None
            self._update_status("stopped", "Stopped")

        def _on_toggle_source(self):
            if self.manager:
                self.manager.handle_hotkey()

        def on_window_close(self):
            if self.settings.start_minimized:
                self.withdraw()
                return
            if not self._minimized_to_tray:
                self._minimized_to_tray = True
                self.withdraw()
                return
            if self._running:
                self._on_stop()
            if self.tray_icon:
                self.tray_icon.stop()
            self.quit()
            self.destroy()

        def _force_quit(self):
            if self._running:
                self._on_stop()
            if self.tray_icon:
                self.tray_icon.stop()
            self.quit()
            self.destroy()

        def start_tray(self):
            try:
                img = create_tray_image(ACCENT_GREEN)
                self.tray_icon = create_tray_icon(
                    img,
                    on_quit=lambda icon, item: self.after(0, self._force_quit),
                    on_show=lambda icon, item: (
                        self.after(0, self.deiconify),
                        self.after(0, lambda: self.state("normal")),
                        self.after(0, lambda: setattr(self, "_minimized_to_tray", False)),
                    ),
                    on_click=lambda icon, item: (
                        self.after(0, self.deiconify),
                        self.after(0, lambda: self.state("normal")),
                        self.after(0, lambda: setattr(self, "_minimized_to_tray", False)),
                    ),  # Left-click shows window
                )
                self.tray_icon.menu = self.tray_icon._get_menu(self)
                self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
                self.tray_thread.start()
                self.after(200, self._update_status, "ready", "Ready")
            except Exception as e:
                logger.warning("System tray unavailable: %s", e)

    return InciteVisionApp

def main():
    import argparse
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--silent", action="store_true", help="Start minimized to tray")
    args = parser.parse_args()

    # Rotate log file if > 1MB
    MAX_LOG_SIZE = 1024 * 1024
    if LOG_FILE.exists() and LOG_FILE.stat().st_size > MAX_LOG_SIZE:
        LOG_FILE.unlink()
    LOG_FILE.touch()

    try:
        ensure_dependencies()
        AppClass = create_app_class()
        app = AppClass()
        if args.silent:
            app.withdraw()
        app.after(100, app.start_tray)
        app.mainloop()
    except Exception as e:
        import traceback
        print(f"FATAL: {e}")
        traceback.print_exc()
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()
