import asyncio
import io
import queue
from album_colors import AlbumArtworkWorker
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk, colorchooser

import numpy as np
import soundcard as sc
import mss

from lotus_lamp import LotusLamp, DeviceConfig


# ============================================================
# GLOBAL SETTINGS
# ============================================================

APP_NAME = "Olive RGB"
APP_VERSION = "1.3.0-preview"

import os
import json
import re

# Semantic GUI colors; lighting colors are independent of appearance.
THEMES = {
    "Tickets": dict(background="#F4EEE9", surface="#FFF9F5", text="#171417", log_background="#292329", muted="#756A72", accent_soft="#F08AB6", accent="#F34D9B", border="#D7C9D0", button="#FFFFFF", on_accent="#FFFFFF", hover="#FBE3EE", pressed="#C93679", log_text="#F8EEF2"),
    "Sakura": dict(background="#21151F", surface="#342330", text="#F7EAF3", log_background="#190F18", muted="#C9AFC0", accent_soft="#D898BC", accent="#FF77B7", border="#75506B", button="#49313F", on_accent="#21151F", hover="#604253", pressed="#D898BC", log_text="#F7EAF3"),
    "Blackout": dict(background="#111111", surface="#202020", text="#F5F5F5", log_background="#080808", muted="#B8B8B8", accent_soft="#BBBBBB", accent="#EEEEEE", border="#555555", button="#303030", on_accent="#111111", hover="#444444", pressed="#BBBBBB", log_text="#F5F5F5"),
    "Cyberpunk": dict(background="#140B26", surface="#25143D", text="#F4EAFF", log_background="#0C0618", muted="#C0A9DA", accent_soft="#00DDEB", accent="#FF48CC", border="#705098", button="#382052", on_accent="#140B26", hover="#52316F", pressed="#00DDEB", log_text="#00DDEB"),
}
DEFAULT_MUSIC_COLORS = {"bass": "#FF0A46", "mids": "#9614FF", "treble": "#00D2FF", "beat": "#FFFFFF"}

def validated_music_colors(value):
    value = value if isinstance(value, dict) else {}
    return {key: value[key].upper() if isinstance(value.get(key), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value[key]) else default
            for key, default in DEFAULT_MUSIC_COLORS.items()}

def color_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))



APP_DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "OliveRGB"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"

def load_app_settings():
    try:
        if SETTINGS_FILE.exists():
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_app_settings(data):
    try:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(data, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass



AUDIO_SAMPLE_RATE = 48000
AUDIO_FRAMES = 4096

# Protect our poor Bluetooth lamp from command spam.
LIGHT_UPDATE_INTERVAL = 0.25

BASS_RANGE = (40, 250)
MID_RANGE = (250, 2000)
TREBLE_RANGE = (2000, 12000)


# ============================================================
# BLUETOOTH WORKER
# SACRED GROUND. WE KNOW THIS WORKS.
# ============================================================

class BluetoothWorker:
    def __init__(self, status_callback, log_callback):
        self.status_callback = status_callback
        self.log_callback = log_callback

        self.loop = None
        self.lamp = None
        self.connected = False

        self.ready = threading.Event()

        self.last_rgb = None
        self.last_send_time = 0
        # Serialize BLE writes. Reactive modes can request colors faster than
        # the underlying GATT client finishes a write/discovery operation.
        self.rgb_lock = None

        self.thread = threading.Thread(
            target=self._start_loop,
            daemon=True
        )

        self.thread.start()

    def _debug(self, message):
        # Console output is intentional in v1.0.2 Debug.  It bypasses
        # Tkinter so we can see worker-thread failures even if GUI callbacks
        # are the thing that is broken in a frozen PyInstaller executable.
        try:
            print(f"[BLE DEBUG] {message}", flush=True)
        except Exception:
            pass

    def _start_loop(self):
        self._debug(f"worker thread started: {threading.current_thread().name}")
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self.rgb_lock = asyncio.Lock()
            self._debug(f"event loop created; closed={self.loop.is_closed()}")

            self._debug("constructing LotusLamp with explicit device config")
            device_config = DeviceConfig(
                name="MELK-OA10   7F",
                address="BE:28:87:00:08:7F",
            )
            self.lamp = LotusLamp(device_config=device_config)
            self._debug(f"LotusLamp constructed: {type(self.lamp).__name__}")

            self.ready.set()
            self._debug("ready set; entering run_forever")
            self.loop.run_forever()
            self._debug("run_forever returned")

        except Exception as e:
            self.ready.set()
            self._debug(f"worker exception: {type(e).__name__}: {e!r}")
            try:
                self.log_callback(f"Bluetooth worker error: {type(e).__name__}: {e}")
            except Exception as callback_error:
                self._debug(f"log callback also failed: {callback_error!r}")

    def _future_done(self, future):
        try:
            exc = future.exception()
            if exc is None:
                self._debug("submitted coroutine completed normally")
            else:
                self._debug(f"submitted coroutine exception: {type(exc).__name__}: {exc!r}")
                self.log_callback(f"Bluetooth task error: {type(exc).__name__}: {exc}")
        except Exception as e:
            self._debug(f"future inspection failed: {type(e).__name__}: {e!r}")

    def _submit(self, coroutine):
        self._debug(f"submit requested; ready={self.ready.is_set()} loop={self.loop!r}")
        if not self.ready.wait(timeout=5):
            self._debug("ready wait timed out")
            self.log_callback("Bluetooth worker failed to start")
            try:
                coroutine.close()
            except Exception:
                pass
            return None

        if self.loop is None:
            self._debug("event loop is None")
            self.log_callback("Bluetooth event loop unavailable")
            try:
                coroutine.close()
            except Exception:
                pass
            return None

        self._debug(
            f"before submit: running={self.loop.is_running()} closed={self.loop.is_closed()} "
            f"thread_alive={self.thread.is_alive()}"
        )
        try:
            future = asyncio.run_coroutine_threadsafe(coroutine, self.loop)
            self._debug(f"coroutine submitted: {future!r}")
            future.add_done_callback(self._future_done)
            return future
        except Exception as e:
            self._debug(f"run_coroutine_threadsafe failed: {type(e).__name__}: {e!r}")
            try:
                coroutine.close()
            except Exception:
                pass
            self.log_callback(f"Bluetooth submit error: {type(e).__name__}: {e}")
            return None

    async def _connect(self):
        self._debug("_connect coroutine ENTERED")
        try:
            self.status_callback(
                "🟡 CONNECTING..."
            )

            self.log_callback(
                "Connecting to Corner Lamp..."
            )

            await self.lamp.connect()

            # Give Windows/Bleak a brief settling window after GATT connect.
            # This prevents reactive modes from racing service discovery.
            await asyncio.sleep(0.75)

            self.connected = True

            self.status_callback(
                "🟢 CONNECTED"
            )

            self.log_callback(
                "✓ Corner Lamp connected"
            )

        except Exception as e:
            self.connected = False

            self.status_callback(
                "🔴 ERROR"
            )

            self.log_callback(
                f"Bluetooth connection error: {e}"
            )

    def connect(self):
        self._debug("connect() called from GUI")
        if not self.ready.wait(timeout=5):
            self.status_callback(
                "🔴 NOT READY"
            )

            self.log_callback(
                "Bluetooth worker failed to initialize"
            )

            return

        self._submit(
            self._connect()
        )

    async def _set_rgb(self, r, g, b):
        if not self.connected:
            return

        try:
            # Only one GATT color write may be in flight at a time.
            # This keeps Music/Movie/Gaming from racing Bleak service setup.
            if self.rgb_lock is None:
                return
            async with self.rgb_lock:
                await self.lamp.set_rgb(
                    int(r),
                    int(g),
                    int(b)
                )

        except Exception as e:
            self.log_callback(
                f"RGB error: {e}"
            )

    def set_rgb(self, r, g, b, force=False):
        if not self.connected:
            return

        rgb = (
            max(0, min(255, int(r))),
            max(0, min(255, int(g))),
            max(0, min(255, int(b)))
        )

        now = time.monotonic()

        if not force:
            elapsed = now - self.last_send_time

            # Never send faster than the lamp's conservative BLE limit.
            if elapsed < LIGHT_UPDATE_INTERVAL:
                return

            if self.last_rgb is not None:
                difference = max(
                    abs(rgb[i] - self.last_rgb[i])
                    for i in range(3)
                )

                # Ignore tiny screen fluctuations. Still refresh periodically
                # so the lamp cannot get stranded on an old color.
                if difference < 10 and elapsed < 1.5:
                    return

        self.last_rgb = rgb
        self.last_send_time = now

        self._submit(
            self._set_rgb(
                rgb[0],
                rgb[1],
                rgb[2]
            )
        )

    async def _disconnect(self):
        try:
            if self.connected:
                await self.lamp.disconnect()

        except Exception:
            pass

        self.connected = False

        self.status_callback(
            "⚪ DISCONNECTED"
        )

    def disconnect(self):
        if self.ready.is_set():
            self._submit(
                self._disconnect()
            )


# ============================================================
# MUSIC ENGINE
# ============================================================

class MusicEngine:

    PROFILES = {
        "Smooth": {
            "smoothing": 0.86,
            "sensitivity": 2.0,
            "beat_strength": 0.20,
            "dominance": 1.25,
            "minimum": 0.10
        },

        "Reactive": {
            "smoothing": 0.68,
            "sensitivity": 2.8,
            "beat_strength": 0.45,
            "dominance": 1.45,
            "minimum": 0.08
        },

        "Hyperpop": {
            "smoothing": 0.48,
            "sensitivity": 3.4,
            "beat_strength": 0.70,
            "dominance": 1.65,
            "minimum": 0.10
        },

        "MGK": {
            "smoothing": 0.65,
            "sensitivity": 2.8,
            "beat_strength": 0.62,
            "dominance": 1.50,
            "minimum": 0.09
        }
    }

    def __init__(
        self,
        rgb_callback,
        meter_callback,
        beat_callback,
        log_callback
    ):
        self.rgb_callback = rgb_callback
        self.meter_callback = meter_callback
        self.beat_callback = beat_callback
        self.log_callback = log_callback

        self.running = False
        self.thread = None

        self.profile_name = "Reactive"
        self.colors = validated_music_colors({})

        self.user_sensitivity = 1.0
        self.user_smoothing = 1.0

        self.baselines = np.array(
            [1.0, 1.0, 1.0],
            dtype=float
        )

        self.previous_rgb = np.array(
            [20.0, 0.0, 20.0],
            dtype=float
        )

        self.smoothed_brightness = 0.15

        self.energy_history = []
        self.last_beat = 0.0

    def start(self):
        if self.running:
            return

        self.reset_analysis()

        self.running = True

        self.thread = threading.Thread(
            target=self._run,
            daemon=True
        )

        self.thread.start()

    def stop(self):
        if self.running:
            self.running = False
            self.log_callback(
                "Music mode stopped"
            )

    def reset_analysis(self):
        self.baselines = np.array(
            [1.0, 1.0, 1.0],
            dtype=float
        )

        self.previous_rgb = np.array(
            [20.0, 0.0, 20.0],
            dtype=float
        )

        self.smoothed_brightness = 0.15

        self.energy_history = []
        self.last_beat = 0.0

    def set_profile(self, name):
        if name in self.PROFILES:
            self.profile_name = name
            self.reset_analysis()

            self.log_callback(
                f"Music profile → {name}"
            )

    @staticmethod
    def _band_mean(
        spectrum,
        frequencies,
        low,
        high
    ):
        mask = (
            (frequencies >= low) &
            (frequencies < high)
        )

        if not np.any(mask):
            return 0.0

        return float(
            np.mean(spectrum[mask])
        )

    def _detect_beat(self, energy):
        self.energy_history.append(
            energy
        )

        if len(self.energy_history) > 18:
            self.energy_history.pop(0)

        if len(self.energy_history) < 8:
            return False

        history = np.array(
            self.energy_history[:-1],
            dtype=float
        )

        average = float(
            np.mean(history)
        )

        deviation = float(
            np.std(history)
        )

        threshold = (
            average +
            max(
                deviation * 1.15,
                average * 0.18
            )
        )

        now = time.monotonic()

        beat = (
            energy > threshold
            and energy > 0.0005
            and now - self.last_beat > 0.18
        )

        if beat:
            self.last_beat = now

        return beat

    def _palette(self, relative):

        dominant = int(
            np.argmax(relative)
        )

        profile = self.PROFILES[
            self.profile_name
        ]

        sorted_values = np.sort(
            relative
        )

        if sorted_values[-2] <= 0:
            dominance_ratio = 99
        else:
            dominance_ratio = (
                sorted_values[-1] /
                sorted_values[-2]
            )

        palette = self.colors  # One immutable-by-convention snapshot per analysis frame.
        colors = [np.array(color_rgb(palette[key]), dtype=float)
                  for key in ("bass", "mids", "treble")]

        color = colors[dominant]

        if (
            dominance_ratio
            < profile["dominance"]
        ):
            weights = relative / (
                np.sum(relative) + 1e-9
            )

            color = (
                colors[0] * weights[0] +
                colors[1] * weights[1] +
                colors[2] * weights[2]
            )

        return color, dominant

    def _run(self):
        try:
            last_speaker_name = None
            self.log_callback(
                f"🎵 {self.profile_name} music mode started"
            )

            while self.running:
                speaker = sc.default_speaker()
                if speaker.name != last_speaker_name:
                    if last_speaker_name is not None:
                        self.log_callback(
                            f"Audio output changed: {last_speaker_name} → {speaker.name}"
                        )
                        self.log_callback("Reconnecting audio capture...")
                    self.log_callback(f"Listening to: {speaker.name}")
                    last_speaker_name = speaker.name

                loopback = sc.get_microphone(
                    speaker.name,
                    include_loopback=True
                )

                with loopback.recorder(
                    samplerate=AUDIO_SAMPLE_RATE,
                    channels=2
                ) as recorder:

                    next_device_check = time.monotonic() + 0.5
                    while self.running:
                        now = time.monotonic()
                        if now >= next_device_check:
                            current_speaker = sc.default_speaker()
                            if current_speaker.name != speaker.name:
                                break
                            next_device_check = now + 0.5

                        data = recorder.record(
                            numframes=AUDIO_FRAMES
                        )

                        mono = np.mean(
                            data,
                            axis=1
                        )

                        mono -= np.mean(mono)

                        rms = float(
                            np.sqrt(
                                np.mean(
                                    mono ** 2
                                )
                            )
                        )

                        window = np.hanning(
                            len(mono)
                        )

                        spectrum = np.abs(
                            np.fft.rfft(
                                mono * window
                            )
                        )

                        frequencies = (
                            np.fft.rfftfreq(
                                len(mono),
                                1 / AUDIO_SAMPLE_RATE
                            )
                        )

                        bands = np.array([
                            self._band_mean(
                                spectrum,
                                frequencies,
                                *BASS_RANGE
                            ),

                            self._band_mean(
                                spectrum,
                                frequencies,
                                *MID_RANGE
                            ),

                            self._band_mean(
                                spectrum,
                                frequencies,
                                *TREBLE_RANGE
                            )
                        ])

                        if np.all(
                            self.baselines == 1.0
                        ):
                            self.baselines = (
                                np.maximum(
                                    bands,
                                    0.000001
                                )
                            )

                        baseline_speed = 0.035

                        self.baselines = (
                            self.baselines *
                            (1 - baseline_speed)
                            +
                            np.maximum(
                                bands,
                                0.000001
                            )
                            * baseline_speed
                        )

                        relative = bands / (
                            self.baselines +
                            1e-9
                        )

                        relative = np.clip(
                            relative,
                            0.15,
                            4.0
                        )

                        target_color, dominant = (
                            self._palette(
                                relative
                            )
                        )

                        profile = self.PROFILES[
                            self.profile_name
                        ]

                        sensitivity = (
                            profile["sensitivity"]
                            *
                            self.user_sensitivity
                        )

                        brightness = np.clip(
                            rms *
                            sensitivity *
                            10.0,
                            profile["minimum"],
                            1.0
                        )

                        beat = self._detect_beat(
                            rms
                        )

                        if beat:
                            brightness = min(
                                1.0,
                                brightness +
                                profile[
                                    "beat_strength"
                                ]
                            )

                            target_color = (
                                target_color * 0.55
                                + np.array(color_rgb(self.colors["beat"]), dtype=float) * 0.45
                            )

                        if (
                            brightness >
                            self.smoothed_brightness
                        ):
                            brightness_alpha = 0.45
                        else:
                            brightness_alpha = 0.82

                        self.smoothed_brightness = (
                            self.smoothed_brightness
                            * brightness_alpha
                            +
                            brightness
                            * (1 - brightness_alpha)
                        )

                        smoothing = np.clip(
                            profile["smoothing"]
                            *
                            self.user_smoothing,
                            0.05,
                            0.96
                        )

                        if beat:
                            smoothing *= 0.45

                        output_color = (
                            self.previous_rgb
                            * smoothing
                            +
                            target_color
                            * (1 - smoothing)
                        )

                        self.previous_rgb = (
                            output_color
                        )

                        rgb = np.clip(
                            output_color
                            *
                            self.smoothed_brightness,
                            0,
                            255
                        )

                        self.rgb_callback(
                            int(rgb[0]),
                            int(rgb[1]),
                            int(rgb[2])
                        )

                        normalized = (
                            relative /
                            (
                                np.sum(relative)
                                + 1e-9
                            )
                        )

                        self.meter_callback(
                            float(normalized[0]),
                            float(normalized[1]),
                            float(normalized[2]),
                            rms,
                            rgb,
                            dominant
                        )

                        if beat:
                            self.beat_callback()

                        time.sleep(0.015)

        except Exception as e:
            self.log_callback(
                f"Audio error: {e}"
            )

            self.running = False


# ============================================================
# SCREEN ENGINE
# MOVIE + GAMING
# ============================================================

class ScreenEngine:
    """Known-good MSS capture path for Movie and Gaming modes."""

    def __init__(self, rgb_callback, preview_callback, log_callback):
        self.rgb_callback = rgb_callback
        self.preview_callback = preview_callback
        self.log_callback = log_callback
        self.running = False
        self.thread = None
        self.mode = "Movie"
        self.monitor_number = 1
        self.intensity = 1.0
        self.saturation = 1.25
        self.previous_rgb = np.array([0.0, 0.0, 0.0], dtype=float)
        self.previous_luma = 0.0
        self.generation = 0
        self.lock = threading.Lock()

    def start(self, mode, monitor_number):
        self.stop()
        with self.lock:
            self.generation += 1
            generation = self.generation
            self.mode = mode
            self.monitor_number = monitor_number
            self.previous_rgb = np.array([0.0, 0.0, 0.0], dtype=float)
            self.previous_luma = 0.0
            self.running = True
        self.thread = threading.Thread(
            target=self._run,
            args=(generation, mode, monitor_number),
            daemon=True
        )
        self.thread.start()

    def stop(self):
        was_running = self.running
        with self.lock:
            self.running = False
            self.generation += 1
        if was_running:
            self.log_callback(f"{self.mode} mode stopped")

    def _still_active(self, generation):
        with self.lock:
            return self.running and generation == self.generation

    @staticmethod
    def _boost_saturation(rgb, amount):
        rgb = np.asarray(rgb, dtype=float)
        gray = 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
        return np.clip(gray + (rgb - gray) * amount, 0, 255)

    def _run(self, generation, mode, monitor_number):
        try:
            self.log_callback(f"🖥 {mode} mode started on Monitor {monitor_number}")

            # Same capture API and averaging path as the screen_test.py
            # that was verified to work on this computer.
            with mss.MSS() as capture:
                monitors = capture.monitors

                if monitor_number < 1 or monitor_number >= len(monitors):
                    self.log_callback(
                        f"Screen capture error: Monitor {monitor_number} does not exist. "
                        f"Found {len(monitors) - 1} monitor(s)."
                    )
                    with self.lock:
                        if generation == self.generation:
                            self.running = False
                    return

                monitor = monitors[monitor_number]
                self.log_callback(
                    f"✓ Capturing Monitor {monitor_number}: "
                    f"{monitor['width']}x{monitor['height']}"
                )

                first_frame = True

                while self._still_active(generation):
                    shot = capture.grab(monitor)
                    frame = np.asarray(shot)[:, :, :3]   # BGR
                    rgb_frame = frame[:, :, ::-1]        # RGB
                    sample = rgb_frame[::20, ::20]

                    target = np.mean(
                        sample.reshape(-1, 3),
                        axis=0
                    ).astype(float)

                    target = self._boost_saturation(target, self.saturation)

                    luma = float(
                        0.2126 * target[0]
                        + 0.7152 * target[1]
                        + 0.0722 * target[2]
                    )

                    if mode == "Movie":
                        smoothing = 0.78
                        scene_brightness = np.clip(
                            0.30 + (luma / 255.0) * 0.90,
                            0.25, 1.0
                        )
                        target_output = target * scene_brightness * self.intensity
                        sleep_time = 0.08
                    else:
                        smoothing = 0.35
                        scene_brightness = np.clip(
                            0.45 + (luma / 255.0) * 0.85,
                            0.35, 1.0
                        )
                        luma_jump = luma - self.previous_luma
                        impact = 1.30 if luma_jump > 30 else (1.15 if luma_jump > 15 else 1.0)
                        target_output = (
                            target * scene_brightness * self.intensity * impact
                        )
                        sleep_time = 0.04

                    self.previous_luma = luma
                    target_output = np.clip(target_output, 0, 255)

                    if first_frame:
                        output = target_output
                        first_frame = False
                    else:
                        output = (
                            self.previous_rgb * smoothing
                            + target_output * (1.0 - smoothing)
                        )

                    self.previous_rgb = output
                    output = np.clip(output, 0, 255)
                    rgb = tuple(int(v) for v in output)

                    # Exact same value goes to preview and physical lamp.
                    self.preview_callback(rgb, mode)
                    self.rgb_callback(*rgb)

                    time.sleep(sleep_time)

        except Exception as e:
            self.log_callback(f"Screen capture error: {type(e).__name__}: {e}")
            with self.lock:
                if generation == self.generation:
                    self.running = False


# ============================================================
# GUI
# ============================================================

class LampGUI:

    def __init__(self, root):
        self.root = root
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1080x760")
        self.root.minsize(920, 680)

        self.settings = load_app_settings()
        selected_theme = self.settings.get("ui_theme", "Tickets")
        self.theme_var = tk.StringVar(value=selected_theme if selected_theme in THEMES else "Tickets")
        self.music_colors = validated_music_colors(self.settings.get("music_colors"))
        self.manual_music_colors = dict(self.music_colors)
        self.music_color_source = tk.StringVar(value=("Album cover" if self.settings.get("music_color_source") == "Album cover" else "Custom"))
        self.closing = False
        self.style = ttk.Style()
        self.apply_theme()
        theme = THEMES[self.theme_var.get()]
        PAPER = theme["background"]
        PAPER_2 = theme["surface"]
        INK = theme["text"]
        INK_2 = theme["log_background"]
        MUTED = theme["muted"]
        PINK = theme["accent_soft"]
        HOT = theme["accent"]
        LINE = theme["border"]
        WHITE = theme["button"]
        self.bluetooth = None
        self.music = None
        self.screen = None
        self.active_mode = None

        # Header — intentionally spacious, like a record sleeve rather than a dashboard.
        header = ttk.Frame(root)
        header.pack(fill="x", padx=34, pady=(25, 10))
        title_block = ttk.Frame(header)
        title_block.pack(side="left")
        ttk.Label(title_block, text="OLIVE RGB", style="Title.TLabel").pack(anchor="w")
        ttk.Label(title_block, text=f"LIGHT IT UP  /  v{APP_VERSION}", style="Kicker.TLabel").pack(anchor="w", pady=(1, 0))

        self.status_label = ttk.Label(header, text="● DISCONNECTED", style="Status.TLabel")
        self.status_label.pack(side="right", padx=(14, 0))
        ttk.Button(header, text="CONNECT", command=self.connect_lamp, style="Accent.TButton").pack(side="right")

        # Three large mode controls. No box around them; they are the hierarchy.
        modes = ttk.Frame(root)
        modes.pack(fill="x", padx=34, pady=(10, 14))
        self.music_button = ttk.Button(modes, text="MUSIC", style="Mode.TButton", command=self.toggle_music)
        self.music_button.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.movie_button = ttk.Button(modes, text="MOVIE", style="Mode.TButton", command=lambda: self.toggle_screen_mode("Movie"))
        self.movie_button.pack(side="left", fill="x", expand=True, padx=6)
        self.game_button = ttk.Button(modes, text="GAMING", style="Mode.TButton", command=lambda: self.toggle_screen_mode("Gaming"))
        self.game_button.pack(side="left", fill="x", expand=True, padx=(6, 0))

        notebook = ttk.Notebook(root)
        notebook.pack(fill="both", expand=True, padx=34, pady=(0, 14))
        light_tab = ttk.Frame(notebook, style="Paper.TFrame")
        music_tab = ttk.Frame(notebook, style="Paper.TFrame")
        screen_tab = ttk.Frame(notebook, style="Paper.TFrame")
        system_tab = ttk.Frame(notebook, style="Paper.TFrame")
        notebook.add(light_tab, text="LIGHT")
        notebook.add(music_tab, text="MUSIC")
        notebook.add(screen_tab, text="SCREEN")
        notebook.add(system_tab, text="SYSTEM")

        # LIGHT tab — swatches on left, oversized live output on right.
        light_left = ttk.Frame(light_tab, style="Paper.TFrame")
        light_left.pack(side="left", fill="both", expand=True, padx=(24, 12), pady=24)
        light_right = ttk.Frame(light_tab, style="Paper.TFrame")
        light_right.pack(side="right", fill="both", expand=True, padx=(12, 24), pady=24)
        ttk.Label(light_left, text="STATIC COLORS", style="Section.TLabel").pack(anchor="w", pady=(0, 12))
        presets = [
            ("PINK", (255, 20, 120)), ("PURPLE", (150, 30, 255)),
            ("CYAN", (0, 200, 255)), ("RED", (255, 0, 0)),
            ("WARM", (255, 90, 20)), ("WHITE", (255, 255, 255)),
            ("MGK", (255, 0, 70)), ("OFF", (0, 0, 0))
        ]
        grid = ttk.Frame(light_left, style="Paper.TFrame")
        grid.pack(fill="x")
        for i, (name, rgb) in enumerate(presets):
            ttk.Button(grid, text=name, command=lambda c=rgb: self.set_manual_color(c)).grid(row=i//2, column=i%2, sticky="ew", padx=(0 if i%2==0 else 6, 6 if i%2==0 else 0), pady=5)
        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)
        ttk.Button(light_left, text="CUSTOM COLOR  +", command=self.choose_color, style="Accent.TButton").pack(fill="x", pady=(10, 0))

        ttk.Label(light_right, text="NOW GLOWING", style="Section.TLabel").pack(anchor="w", pady=(0, 12))
        self.preview = tk.Canvas(light_right, height=260, bg=INK, highlightthickness=0)
        self.preview.pack(fill="both", expand=True)
        self.rgb_label = ttk.Label(light_right, text="RGB  0 / 0 / 0", style="Card.TLabel", font=("Cascadia Mono", 10, "bold"))
        self.rgb_label.pack(anchor="e", pady=(10, 0))

        # MUSIC tab
        music_controls = ttk.Frame(music_tab, style="Paper.TFrame")
        music_controls.pack(side="left", fill="both", expand=True, padx=(24, 16), pady=16)
        music_live = ttk.Frame(music_tab, style="Paper.TFrame")
        music_live.pack(side="right", fill="both", expand=True, padx=(16, 24), pady=24)
        ttk.Label(music_controls, text="MUSIC REACTIVE", style="Section.TLabel").pack(anchor="w")
        ttk.Label(music_controls, text="Choose the feel, then tune how hard the room reacts.", style="Muted.Card.TLabel").pack(anchor="w", pady=(3, 10))
        self.profile_var = tk.StringVar(value=self.settings.get("music_profile", "Reactive"))
        profile_box = ttk.Combobox(music_controls, textvariable=self.profile_var, values=["Smooth", "Reactive", "Hyperpop", "MGK"], state="readonly")
        profile_box.pack(fill="x", pady=(0, 10)); profile_box.bind("<<ComboboxSelected>>", lambda _: self.change_profile())
        self.music_sensitivity = tk.DoubleVar(value=float(self.settings.get("music_sensitivity", 1.0)))
        ttk.Label(music_controls, text="SENSITIVITY", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Scale(music_controls, from_=0.4, to=2.5, variable=self.music_sensitivity, command=self.update_music_settings).pack(fill="x", pady=(5, 10))
        self.music_smoothing = tk.DoubleVar(value=float(self.settings.get("music_smoothing", 1.0)))
        ttk.Label(music_controls, text="SMOOTHING", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Scale(music_controls, from_=0.5, to=1.35, variable=self.music_smoothing, command=self.update_music_settings).pack(fill="x", pady=(5, 0))

        ttk.Label(music_controls, text="MUSIC COLORS", style="Section.TLabel").pack(anchor="w", pady=(14, 4))
        source_box = ttk.Combobox(music_controls, textvariable=self.music_color_source,
                                  values=["Custom", "Album cover"], state="readonly")
        source_box.pack(fill="x", pady=(2, 5))
        source_box.bind("<<ComboboxSelected>>", self.change_music_color_source)
        self.music_swatches = {}
        for key in DEFAULT_MUSIC_COLORS:
            row = ttk.Frame(music_controls, style="Paper.TFrame")
            row.pack(fill="x", pady=3)
            ttk.Button(row, text=key.upper(), style="Palette.TButton", command=lambda k=key: self.choose_music_color(k)).pack(side="left", fill="x", expand=True)
            swatch = tk.Label(row, text=self.music_colors[key], bg=self.music_colors[key], width=10, cursor="hand2", relief="flat")
            swatch.pack(side="right", padx=(10, 0))
            swatch.bind("<Button-1>", lambda event, k=key: self.choose_music_color(k))
            self.music_swatches[key] = swatch
        self.refresh_music_swatches()

        ttk.Label(music_live, text="LIVE SIGNAL", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        self.bass_meter = self.make_meter(music_live, "BASS")
        self.mid_meter = self.make_meter(music_live, "MIDS")
        self.treble_meter = self.make_meter(music_live, "TREBLE")
        self.volume_meter = self.make_meter(music_live, "VOLUME")
        self.analysis_label = ttk.Label(music_live, text="Mode: Static", style="Card.TLabel", font=("Segoe UI", 11, "bold"))
        self.analysis_label.pack(anchor="w", pady=(20, 4))
        self.beat_label = ttk.Label(music_live, text="○ BEAT", style="Beat.Card.TLabel", font=("Segoe UI Variable Display", 22, "bold"))
        self.beat_label.pack(anchor="w")
        self.album_status = ttk.Label(music_live, text="Custom music colors", style="Muted.Card.TLabel", wraplength=340)
        self.album_status.pack(anchor="w", pady=(14, 6))
        self.album_cover = ttk.Label(music_live, style="Card.TLabel")
        self.album_cover.pack(anchor="w")
        self.album_photo = None

        # SCREEN tab
        screen_controls = ttk.Frame(screen_tab, style="Paper.TFrame")
        screen_controls.pack(fill="both", expand=True, padx=24, pady=24)
        ttk.Label(screen_controls, text="SCREEN REACTIVE", style="Section.TLabel").pack(anchor="w")
        ttk.Label(screen_controls, text="Movie and Gaming sample your display and send the color to the lamp.", style="Muted.Card.TLabel").pack(anchor="w", pady=(3, 22))
        self.monitor_var = tk.StringVar(value=str(self.settings.get("monitor", "1")))
        ttk.Label(screen_controls, text="MONITOR", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        self.monitor_box = ttk.Combobox(screen_controls, textvariable=self.monitor_var, values=self.get_monitors(), state="readonly")
        self.monitor_box.pack(fill="x", pady=(5, 20))
        self.screen_intensity = tk.DoubleVar(value=float(self.settings.get("screen_intensity", 1.0)))
        ttk.Label(screen_controls, text="INTENSITY", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Scale(screen_controls, from_=0.25, to=2.0, variable=self.screen_intensity, command=self.update_screen_settings).pack(fill="x", pady=(5, 20))
        self.screen_saturation = tk.DoubleVar(value=float(self.settings.get("screen_saturation", 1.25)))
        ttk.Label(screen_controls, text="COLOR SATURATION", style="Card.TLabel", font=("Segoe UI", 9, "bold")).pack(anchor="w")
        ttk.Scale(screen_controls, from_=0.5, to=2.5, variable=self.screen_saturation, command=self.update_screen_settings).pack(fill="x", pady=(5, 0))

        appearance_tab = ttk.Frame(notebook, style="Paper.TFrame")
        notebook.add(appearance_tab, text="APPEARANCE")
        appearance = ttk.Frame(appearance_tab, style="Paper.TFrame")
        appearance.pack(fill="both", expand=True, padx=24, pady=24)
        ttk.Label(appearance, text="APPEARANCE / THEME", style="Section.TLabel").pack(anchor="w")
        theme_box = ttk.Combobox(appearance, textvariable=self.theme_var, values=list(THEMES), state="readonly")
        theme_box.pack(fill="x", pady=(16, 12))
        theme_box.bind("<<ComboboxSelected>>", self.change_theme)
        ttk.Label(appearance, text="Choose an interface theme. Your lighting colors stay independent.", style="Muted.Card.TLabel").pack(anchor="w")

        # SYSTEM tab — logs are available when wanted, not permanently screaming at you.
        system_inner = ttk.Frame(system_tab, style="Paper.TFrame")
        system_inner.pack(fill="both", expand=True, padx=24, pady=24)
        ttk.Label(system_inner, text="SYSTEM LOG", style="Section.TLabel").pack(anchor="w", pady=(0, 10))
        self.log_box = tk.Text(system_inner, height=12, state="disabled", font=("Cascadia Mono", 9), bg=INK_2, fg="#F8EEF2", insertbackground=WHITE, selectbackground=HOT, relief="flat", padx=14, pady=14, highlightthickness=0)
        self.log_box.pack(fill="both", expand=True)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.bluetooth = BluetoothWorker(self.set_status, self.log)
        self.music = MusicEngine(self.bluetooth.set_rgb, self.update_audio_meters, self.show_beat, self.log)
        self.music.colors = dict(self.music_colors)
        self.apply_theme()
        self.screen = ScreenEngine(self.bluetooth.set_rgb, self.update_screen_preview, self.log)
        self.artwork_worker = AlbumArtworkWorker()
        if self.music_color_source.get() == "Album cover":
            self.artwork_worker.set_enabled(True)
            self.album_status.configure(text="Waiting for the playing song's artwork…")
        self.root.after(200, self.poll_album_artwork)
        self.log(f"{APP_NAME} v{APP_VERSION} ready")


    # ========================================================
    # MONITORS
    # ========================================================

    def apply_theme(self):
        theme = THEMES[self.theme_var.get()]
        PAPER = theme["background"]
        PAPER_2 = theme["surface"]
        INK = theme["text"]
        INK_2 = theme["log_background"]
        MUTED = theme["muted"]
        PINK = theme["accent_soft"]
        HOT = theme["accent"]
        LINE = theme["border"]
        WHITE = theme["button"]
        self.root.configure(bg=PAPER)
        style = self.style
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("TFrame", background=PAPER)
        style.configure("Paper.TFrame", background=PAPER_2)
        style.configure("Ink.TFrame", background=INK)
        style.configure("TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=PAPER_2, foreground=INK, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=PAPER, foreground=INK, font=("Segoe UI Variable Display", 27, "bold"))
        style.configure("Kicker.TLabel", background=PAPER, foreground=HOT, font=("Segoe UI", 9, "bold"))
        style.configure("Status.TLabel", background=PAPER, foreground=INK, font=("Segoe UI", 10, "bold"))
        style.configure("Section.TLabel", background=PAPER_2, foreground=INK, font=("Segoe UI Variable Display", 15, "bold"))
        style.configure("TButton", background=WHITE, foreground=INK, bordercolor=LINE, lightcolor=WHITE, darkcolor=WHITE, padding=(12, 9), font=("Segoe UI", 10))
        style.map("TButton", background=[("active", theme["hover"]), ("pressed", PINK)], bordercolor=[("active", PINK)])
        style.configure("Mode.TButton", background=INK, foreground=theme["on_accent"], bordercolor=INK, padding=(18, 14), font=("Segoe UI Variable Display", 12, "bold"))
        style.map("Mode.TButton", background=[("active", HOT), ("pressed", theme["accent_soft"])], foreground=[("active", theme["on_accent"])])
        style.configure("Accent.TButton", background=HOT, foreground=theme["on_accent"], bordercolor=HOT, padding=(15, 10), font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton", background=[("active", theme["accent_soft"]), ("pressed", theme["pressed"])])
        style.configure("TCombobox", fieldbackground=WHITE, background=WHITE, foreground=INK, arrowcolor=INK, bordercolor=LINE, padding=5)
        style.map("TCombobox", fieldbackground=[("readonly", WHITE)], foreground=[("readonly", INK)], selectbackground=[("readonly", WHITE)], selectforeground=[("readonly", INK)])
        style.configure("Horizontal.TScale", background=PAPER_2, troughcolor=theme["border"], bordercolor=PAPER_2, lightcolor=PAPER_2, darkcolor=PAPER_2)
        style.configure("Horizontal.TProgressbar", troughcolor=theme["border"], background=HOT, bordercolor=PAPER_2, lightcolor=HOT, darkcolor=HOT)
        style.configure("TNotebook", background=PAPER, borderwidth=0, tabmargins=(0, 8, 0, 0))
        style.configure("TNotebook.Tab", background=PAPER, foreground=MUTED, borderwidth=0, padding=(22, 10), font=("Segoe UI", 10, "bold"))
        style.map("TNotebook.Tab", background=[("selected", PAPER_2), ("active", theme["hover"])], foreground=[("selected", INK), ("active", INK)])

        style.configure("Muted.Card.TLabel", background=PAPER_2, foreground=MUTED)
        style.configure("Palette.TButton", padding=(10, 4))
        style.configure("Beat.Card.TLabel", background=PAPER_2, foreground=HOT)
        self.root.option_add("*TCombobox*Listbox.background", theme["button"])
        self.root.option_add("*TCombobox*Listbox.foreground", theme["text"])
        self.root.option_add("*TCombobox*Listbox.selectBackground", theme["accent"])
        self.root.option_add("*TCombobox*Listbox.selectForeground", theme["on_accent"])
        if hasattr(self, "log_box"):
            self.log_box.configure(bg=theme["log_background"], fg=theme["log_text"], insertbackground=theme["log_text"], selectbackground=theme["accent"], selectforeground=theme["on_accent"])

    def change_theme(self, _=None):
        self.apply_theme()
        self.save_settings()

    def refresh_music_swatches(self):
        for key, swatch in self.music_swatches.items():
            color = self.music_colors[key]
            r, g, b = color_rgb(color)
            foreground = "#000000" if (r * 299 + g * 587 + b * 114) / 1000 >= 145 else "#FFFFFF"
            swatch.configure(bg=color, fg=foreground, text=color)

    def change_music_color_source(self, _=None):
        if self.music_color_source.get() == "Album cover":
            self.artwork_worker.set_enabled(True)
            self.album_status.configure(text="Waiting for the playing song's artwork…")
        else:
            self.artwork_worker.set_enabled(False)
            self.music_colors = dict(self.manual_music_colors)
            self.music.colors = dict(self.music_colors)
            self.refresh_music_swatches()
            self.album_status.configure(text="Custom music colors")
            self.album_cover.configure(image="")
            self.album_photo = None
        self.save_settings()

    def poll_album_artwork(self):
        if self.closing:
            return
        try:
            kind, description, palette, data = self.artwork_worker.messages.get_nowait()
        except queue.Empty:
            pass
        else:
            if self.music_color_source.get() == "Album cover":
                self.music_colors = dict(palette or self.manual_music_colors)
                self.music.colors = dict(self.music_colors)
                self.refresh_music_swatches()
                self.album_status.configure(text=description)
                self.album_cover.configure(image="")
                self.album_photo = None
                if kind == "artwork":
                    try:
                        from PIL import Image, ImageTk, ImageOps
                        with Image.open(io.BytesIO(data)) as image:
                            thumbnail = ImageOps.exif_transpose(image).convert("RGB")
                            thumbnail.thumbnail((100, 100))
                            self.album_photo = ImageTk.PhotoImage(thumbnail, master=self.root)
                        self.album_cover.configure(image=self.album_photo)
                    except Exception:
                        pass  # Extracted palette remains usable if preview rendering fails.
        self.root.after(200, self.poll_album_artwork)

    def choose_music_color(self, key):
        _, color = colorchooser.askcolor(color=self.music_colors[key], title=f"Music {key.title()} color", parent=self.root)
        if color:
            self.manual_music_colors = dict(self.music_colors, **{key: color.upper()})
            self.music_color_source.set("Custom")
            self.change_music_color_source()
            self.music_colors = dict(self.manual_music_colors)
            self.music.colors = dict(self.music_colors)
            self.refresh_music_swatches()
            self.save_settings()

    def get_monitors(self):
        try:
            with mss.MSS() as sct:
                count = (
                    len(sct.monitors) - 1
                )

            return [
                str(i)
                for i in range(
                    1,
                    count + 1
                )
            ]

        except Exception:
            return ["1"]

    # ========================================================
    # GUI HELPERS
    # ========================================================

    def make_meter(
        self,
        parent,
        name
    ):
        frame = ttk.Frame(
            parent
        )

        frame.pack(
            fill="x",
            padx=10,
            pady=5
        )

        ttk.Label(
            frame,
            text=name,
            width=8
        ).pack(
            side="left"
        )

        meter = ttk.Progressbar(
            frame,
            maximum=100
        )

        meter.pack(
            side="left",
            fill="x",
            expand=True
        )

        return meter

    def connect_lamp(self):
        # Log on the GUI thread FIRST so a button click is always visible,
        # even if the worker itself cannot start or submit a coroutine.
        self.log("Connect Lamp clicked")

        if self.bluetooth is None:
            self.set_status("🔴 NOT READY")
            self.log("Bluetooth worker is not initialized")
            return

        try:
            self.bluetooth.connect()
        except Exception as e:
            self.set_status("🔴 ERROR")
            self.log(f"Connect button error: {type(e).__name__}: {e}")

    def set_status(
        self,
        text
    ):
        self.root.after(
            0,
            lambda:
            self.status_label.config(
                text=text
            )
        )

    def log(
        self,
        text
    ):
        def update():
            self.log_box.config(
                state="normal"
            )

            timestamp = (
                time.strftime(
                    "%H:%M:%S"
                )
            )

            self.log_box.insert(
                "end",
                f"[{timestamp}] "
                f"{text}\n"
            )

            self.log_box.see(
                "end"
            )

            self.log_box.config(
                state="disabled"
            )

        self.root.after(
            0,
            update
        )

    # ========================================================
    # STOP REACTIVE MODES
    # ========================================================

    def stop_modes(self):
        self.music.stop()
        self.screen.stop()

        self.active_mode = None

        self.music_button.config(
            text="🎵 MUSIC"
        )

        self.movie_button.config(
            text="🎬 MOVIE"
        )

        self.game_button.config(
            text="🎮 GAMING"
        )

        self.beat_label.config(
            text="○ BEAT"
        )

    # ========================================================
    # MANUAL COLORS
    # ========================================================

    def choose_color(self):
        result = (
            colorchooser.askcolor()
        )

        if result[0]:
            rgb = tuple(
                int(x)
                for x in result[0]
            )

            self.set_manual_color(
                rgb
            )

    def set_manual_color(
        self,
        rgb
    ):
        self.stop_modes()

        self.bluetooth.set_rgb(
            *rgb,
            force=True
        )

        self.set_preview(
            rgb
        )

        self.analysis_label.config(
            text="Mode: Static"
        )

        self.log(
            f"Manual RGB → "
            f"{rgb[0]}, "
            f"{rgb[1]}, "
            f"{rgb[2]}"
        )

    # ========================================================
    # MUSIC
    # ========================================================

    def toggle_music(self):

        if not self.bluetooth.connected:
            self.log(
                "⚠ Connect the lamp first"
            )
            return

        if self.active_mode == "Music":
            self.stop_modes()
            return

        self.stop_modes()

        self.music.profile_name = (
            self.profile_var.get()
        )

        self.update_music_settings()

        self.music.start()

        self.active_mode = "Music"

        self.music_button.config(
            text="⏹ STOP MUSIC"
        )

        self.analysis_label.config(
            text=(
                "Mode: Music — "
                f"{self.profile_var.get()}"
            )
        )

    def change_profile(self):
        self.music.set_profile(
            self.profile_var.get()
        )

        if self.active_mode == "Music":
            self.analysis_label.config(
                text=(
                    "Mode: Music — "
                    f"{self.profile_var.get()}"
                )
            )

    def update_music_settings(
        self,
        _=None
    ):
        self.music.user_sensitivity = (
            self.music_sensitivity.get()
        )

        self.music.user_smoothing = (
            self.music_smoothing.get()
        )

    # ========================================================
    # MOVIE / GAMING
    # ========================================================

    def toggle_screen_mode(
        self,
        mode
    ):

        if not self.bluetooth.connected:
            self.log(
                "⚠ Connect the lamp first"
            )
            return

        if self.active_mode == mode:
            self.stop_modes()
            return

        self.stop_modes()

        self.update_screen_settings()

        try:
            monitor = int(
                self.monitor_var.get()
            )
        except Exception:
            monitor = 1

        self.screen.start(
            mode,
            monitor
        )

        self.active_mode = mode

        if mode == "Movie":
            self.movie_button.config(
                text="⏹ STOP MOVIE"
            )

        else:
            self.game_button.config(
                text="⏹ STOP GAMING"
            )

        self.analysis_label.config(
            text=(
                f"Mode: {mode} — "
                f"Monitor {monitor}"
            )
        )

    def update_screen_settings(
        self,
        _=None
    ):
        self.screen.intensity = (
            self.screen_intensity.get()
        )

        self.screen.saturation = (
            self.screen_saturation.get()
        )

    # ========================================================
    # MUSIC VISUALIZATION
    # ========================================================

    def update_audio_meters(
        self,
        bass,
        mids,
        treble,
        volume,
        rgb,
        dominant
    ):

        def update():

            self.bass_meter[
                "value"
            ] = bass * 100

            self.mid_meter[
                "value"
            ] = mids * 100

            self.treble_meter[
                "value"
            ] = treble * 100

            self.volume_meter[
                "value"
            ] = min(
                volume * 600,
                100
            )

            names = [
                "BASS",
                "MIDS",
                "TREBLE"
            ]

            self.analysis_label.config(
                text=(
                    "Music: "
                    f"{names[dominant]}"
                )
            )

            self.set_preview(
                rgb
            )

        self.root.after(
            0,
            update
        )

    def show_beat(self):

        def flash():

            self.beat_label.config(
                text="● BEAT!"
            )

            self.root.after(
                110,
                lambda:
                self.beat_label.config(
                    text="○ BEAT"
                )
            )

        self.root.after(
            0,
            flash
        )

    # ========================================================
    # SCREEN VISUALIZATION
    # ========================================================

    def update_screen_preview(
        self,
        rgb,
        mode
    ):

        def update():

            self.set_preview(
                rgb
            )

            self.analysis_label.config(
                text=(
                    f"Mode: {mode} — "
                    f"Monitor "
                    f"{self.monitor_var.get()}"
                )
            )

        self.root.after(
            0,
            update
        )

    # ========================================================
    # PREVIEW
    # ========================================================

    def set_preview(
        self,
        rgb
    ):

        r = max(
            0,
            min(
                255,
                int(rgb[0])
            )
        )

        g = max(
            0,
            min(
                255,
                int(rgb[1])
            )
        )

        b = max(
            0,
            min(
                255,
                int(rgb[2])
            )
        )

        color = (
            f"#{r:02x}"
            f"{g:02x}"
            f"{b:02x}"
        )

        self.preview.config(
            bg=color
        )

        self.rgb_label.config(
            text=(
                f"RGB: "
                f"{r}, {g}, {b}"
            )
        )


    def save_settings(self):
        save_app_settings({
            **self.settings,
            "ui_theme": self.theme_var.get(),
            "music_colors": dict(self.manual_music_colors),
            "music_color_source": self.music_color_source.get(),
            "music_profile": self.profile_var.get(),
            "music_sensitivity": float(self.music_sensitivity.get()),
            "music_smoothing": float(self.music_smoothing.get()),
            "monitor": self.monitor_var.get(),
            "screen_intensity": float(self.screen_intensity.get()),
            "screen_saturation": float(self.screen_saturation.get()),
            "version": APP_VERSION
        })

    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):

        self.closing = True
        self.artwork_worker.close()
        self.save_settings()
        self.stop_modes()

        self.bluetooth.disconnect()

        self.root.after(
            300,
            self.root.destroy
        )


# ============================================================
# START PROGRAM
# ============================================================

if __name__ == "__main__":

    root = tk.Tk()

    app = LampGUI(
        root
    )

    root.mainloop()
