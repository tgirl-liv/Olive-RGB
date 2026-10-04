import asyncio
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
APP_VERSION = "1.0.3"

import os
import json

APP_DATA_DIR = Path(os.getenv("APPDATA", str(Path.home()))) / "OliveRGB"
SETTINGS_FILE = APP_DATA_DIR / "settings.json"

def load_app_settings():
    try:
        if SETTINGS_FILE.exists():
            return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
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

        # ----------------------------------------
        # MGK PALETTE
        # ----------------------------------------

        if self.profile_name == "MGK":

            colors = [
                np.array(
                    [255, 8, 65],
                    dtype=float
                ),

                np.array(
                    [255, 30, 145],
                    dtype=float
                ),

                np.array(
                    [255, 150, 210],
                    dtype=float
                )
            ]

        # ----------------------------------------
        # NORMAL PALETTE
        # ----------------------------------------

        else:

            colors = [
                np.array(
                    [255, 10, 70],
                    dtype=float
                ),

                np.array(
                    [150, 20, 255],
                    dtype=float
                ),

                np.array(
                    [0, 210, 255],
                    dtype=float
                )
            ]

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
            speaker = sc.default_speaker()

            self.log_callback(
                f"Listening to: {speaker.name}"
            )

            loopback = sc.get_microphone(
                speaker.name,
                include_loopback=True
            )

            self.log_callback(
                f"🎵 {self.profile_name} music mode started"
            )

            with loopback.recorder(
                samplerate=AUDIO_SAMPLE_RATE,
                channels=2
            ) as recorder:

                while self.running:

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

                        if (
                            self.profile_name
                            == "MGK"
                        ):
                            target_color = (
                                target_color
                                * 0.55
                                +
                                np.array(
                                    [255, 220, 235]
                                )
                                * 0.45
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

        self.root.geometry(
            "1050x800"
        )

        self.root.minsize(
            950,
            720
        )

        style = ttk.Style()

        try:
            style.theme_use(
                "clam"
            )
        except Exception:
            pass

        style.configure(
            "Title.TLabel",
            font=(
                "Segoe UI",
                24,
                "bold"
            )
        )

        style.configure(
            "Big.TButton",
            font=(
                "Segoe UI",
                11,
                "bold"
            ),
            padding=9
        )

        self.settings = load_app_settings()

        # ----------------------------------------------------
        # WORKERS
        # ----------------------------------------------------
        # IMPORTANT: workers are started only AFTER the GUI widgets
        # (especially status_label and log_box) exist. This keeps
        # background-thread callbacks from touching half-built UI.
        self.bluetooth = None
        self.music = None
        self.screen = None
        self.active_mode = None

        # ====================================================
        # HEADER
        # ====================================================

        header = ttk.Frame(
            root
        )

        header.pack(
            fill="x",
            padx=20,
            pady=15
        )

        ttk.Label(
            header,
            text=(
                f"🌸 {APP_NAME} "
                f"Command Center v{APP_VERSION}"
            ),
            style="Title.TLabel"
        ).pack(
            side="left"
        )

        self.status_label = (
            ttk.Label(
                header,
                text="⚪ DISCONNECTED"
            )
        )

        self.status_label.pack(
            side="right",
            padx=10
        )

        ttk.Button(
            header,
            text="Connect Lamp",
            command=self.connect_lamp
        ).pack(
            side="right"
        )

        # ====================================================
        # MODE BUTTONS
        # ====================================================

        modes = ttk.LabelFrame(
            root,
            text="Reactive Modes"
        )

        modes.pack(
            fill="x",
            padx=20,
            pady=(0, 10)
        )

        self.music_button = (
            ttk.Button(
                modes,
                text="🎵 MUSIC",
                style="Big.TButton",
                command=(
                    self.toggle_music
                )
            )
        )

        self.music_button.pack(
            side="left",
            fill="x",
            expand=True,
            padx=8,
            pady=10
        )

        self.movie_button = (
            ttk.Button(
                modes,
                text="🎬 MOVIE",
                style="Big.TButton",
                command=(
                    lambda:
                    self.toggle_screen_mode(
                        "Movie"
                    )
                )
            )
        )

        self.movie_button.pack(
            side="left",
            fill="x",
            expand=True,
            padx=8,
            pady=10
        )

        self.game_button = (
            ttk.Button(
                modes,
                text="🎮 GAMING",
                style="Big.TButton",
                command=(
                    lambda:
                    self.toggle_screen_mode(
                        "Gaming"
                    )
                )
            )
        )

        self.game_button.pack(
            side="left",
            fill="x",
            expand=True,
            padx=8,
            pady=10
        )

        # ====================================================
        # MAIN AREA
        # ====================================================

        main = ttk.Frame(
            root
        )

        main.pack(
            fill="both",
            expand=True,
            padx=20
        )

        left = ttk.Frame(
            main
        )

        left.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 10)
        )

        right = ttk.Frame(
            main
        )

        right.pack(
            side="right",
            fill="both",
            expand=True,
            padx=(10, 0)
        )

        # ====================================================
        # SCENES
        # ====================================================

        scenes = ttk.LabelFrame(
            left,
            text="Static Scenes"
        )

        scenes.pack(
            fill="x",
            pady=5
        )

        presets = [
            ("🩷 Pink", (255, 20, 120)),
            ("💜 Purple", (150, 30, 255)),
            ("🩵 Cyan", (0, 200, 255)),
            ("❤️ Red", (255, 0, 0)),
            ("🧡 Warm", (255, 90, 20)),
            ("🤍 White", (255, 255, 255)),
            ("🔥 MGK", (255, 0, 70)),
            ("🌙 Off", (0, 0, 0))
        ]

        for i, (
            name,
            rgb
        ) in enumerate(
            presets
        ):

            ttk.Button(
                scenes,
                text=name,
                command=(
                    lambda c=rgb:
                    self.set_manual_color(
                        c
                    )
                )
            ).grid(
                row=i // 2,
                column=i % 2,
                sticky="ew",
                padx=5,
                pady=5
            )

        scenes.columnconfigure(
            0,
            weight=1
        )

        scenes.columnconfigure(
            1,
            weight=1
        )

        ttk.Button(
            scenes,
            text="🎨 Custom Color",
            command=self.choose_color
        ).grid(
            row=4,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=5,
            pady=8
        )

        # ====================================================
        # MUSIC SETTINGS
        # ====================================================

        music_settings = (
            ttk.LabelFrame(
                left,
                text="Music Settings"
            )
        )

        music_settings.pack(
            fill="x",
            pady=10
        )

        self.profile_var = (
            tk.StringVar(
                value=self.settings.get("music_profile", "Reactive")
            )
        )

        profile_box = (
            ttk.Combobox(
                music_settings,
                textvariable=(
                    self.profile_var
                ),
                values=[
                    "Smooth",
                    "Reactive",
                    "Hyperpop",
                    "MGK"
                ],
                state="readonly"
            )
        )

        profile_box.pack(
            fill="x",
            padx=10,
            pady=8
        )

        profile_box.bind(
            "<<ComboboxSelected>>",
            lambda _:
            self.change_profile()
        )

        ttk.Label(
            music_settings,
            text="Sensitivity"
        ).pack()

        self.music_sensitivity = (
            tk.DoubleVar(
                value=float(self.settings.get("music_sensitivity", 1.0))
            )
        )

        ttk.Scale(
            music_settings,
            from_=0.4,
            to=2.5,
            variable=(
                self.music_sensitivity
            ),
            command=(
                self.update_music_settings
            )
        ).pack(
            fill="x",
            padx=10
        )

        ttk.Label(
            music_settings,
            text="Smoothing"
        ).pack(
            pady=(8, 0)
        )

        self.music_smoothing = (
            tk.DoubleVar(
                value=float(self.settings.get("music_smoothing", 1.0))
            )
        )

        ttk.Scale(
            music_settings,
            from_=0.5,
            to=1.35,
            variable=(
                self.music_smoothing
            ),
            command=(
                self.update_music_settings
            )
        ).pack(
            fill="x",
            padx=10,
            pady=(0, 10)
        )

        # ====================================================
        # SCREEN SETTINGS
        # ====================================================

        screen_settings = (
            ttk.LabelFrame(
                left,
                text=(
                    "Movie / Gaming "
                    "Settings"
                )
            )
        )

        screen_settings.pack(
            fill="x",
            pady=10
        )

        ttk.Label(
            screen_settings,
            text="Monitor"
        ).pack(
            pady=(8, 0)
        )

        self.monitor_var = (
            tk.StringVar(
                value=str(self.settings.get("monitor", "1"))
            )
        )

        monitor_values = (
            self.get_monitors()
        )

        self.monitor_box = (
            ttk.Combobox(
                screen_settings,
                textvariable=(
                    self.monitor_var
                ),
                values=monitor_values,
                state="readonly"
            )
        )

        self.monitor_box.pack(
            fill="x",
            padx=10,
            pady=5
        )

        ttk.Label(
            screen_settings,
            text="Intensity"
        ).pack(
            pady=(8, 0)
        )

        self.screen_intensity = (
            tk.DoubleVar(
                value=float(self.settings.get("screen_intensity", 1.0))
            )
        )

        ttk.Scale(
            screen_settings,
            from_=0.25,
            to=2.0,
            variable=(
                self.screen_intensity
            ),
            command=(
                self.update_screen_settings
            )
        ).pack(
            fill="x",
            padx=10
        )

        ttk.Label(
            screen_settings,
            text="Color Saturation"
        ).pack(
            pady=(8, 0)
        )

        self.screen_saturation = (
            tk.DoubleVar(
                value=float(self.settings.get("screen_saturation", 1.25))
            )
        )

        ttk.Scale(
            screen_settings,
            from_=0.5,
            to=2.5,
            variable=(
                self.screen_saturation
            ),
            command=(
                self.update_screen_settings
            )
        ).pack(
            fill="x",
            padx=10,
            pady=(0, 10)
        )

        # ====================================================
        # LIVE ANALYSIS
        # ====================================================

        analysis = ttk.LabelFrame(
            right,
            text="Live Analysis"
        )

        analysis.pack(
            fill="x",
            pady=5
        )

        self.bass_meter = (
            self.make_meter(
                analysis,
                "Bass"
            )
        )

        self.mid_meter = (
            self.make_meter(
                analysis,
                "Mids"
            )
        )

        self.treble_meter = (
            self.make_meter(
                analysis,
                "Treble"
            )
        )

        self.volume_meter = (
            self.make_meter(
                analysis,
                "Volume"
            )
        )

        self.analysis_label = (
            ttk.Label(
                analysis,
                text="Mode: Static",
                font=(
                    "Segoe UI",
                    11,
                    "bold"
                )
            )
        )

        self.analysis_label.pack(
            pady=8
        )

        self.beat_label = (
            ttk.Label(
                analysis,
                text="○ BEAT",
                font=(
                    "Segoe UI",
                    15,
                    "bold"
                )
            )
        )

        self.beat_label.pack(
            pady=8
        )

        # ====================================================
        # OUTPUT PREVIEW
        # ====================================================

        preview_frame = (
            ttk.LabelFrame(
                right,
                text="Lamp Output"
            )
        )

        preview_frame.pack(
            fill="x",
            pady=10
        )

        self.preview = tk.Canvas(
            preview_frame,
            height=130,
            bg="#000000",
            highlightthickness=0
        )

        self.preview.pack(
            fill="x",
            padx=10,
            pady=10
        )

        self.rgb_label = (
            ttk.Label(
                preview_frame,
                text="RGB: 0, 0, 0"
            )
        )

        self.rgb_label.pack(
            pady=(0, 8)
        )

        # ====================================================
        # LOG
        # ====================================================

        log_frame = ttk.LabelFrame(
            root,
            text="System Log"
        )

        log_frame.pack(
            fill="both",
            padx=20,
            pady=15
        )

        self.log_box = tk.Text(
            log_frame,
            height=6,
            state="disabled",
            font=("Consolas", 9)
        )

        self.log_box.pack(
            fill="both",
            expand=True,
            padx=5,
            pady=5
        )

        self.root.protocol(
            "WM_DELETE_WINDOW",
            self.close
        )

        # Start the known-good engines only after every GUI callback
        # target has been created. Sacred Bluetooth Worker stays intact.
        self.bluetooth = BluetoothWorker(
            self.set_status,
            self.log
        )

        self.music = MusicEngine(
            self.bluetooth.set_rgb,
            self.update_audio_meters,
            self.show_beat,
            self.log
        )

        self.screen = ScreenEngine(
            self.bluetooth.set_rgb,
            self.update_screen_preview,
            self.log
        )

        self.log(
            f"{APP_NAME} v{APP_VERSION} ready"
        )

    # ========================================================
    # MONITORS
    # ========================================================

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
                "BASS 🩷",
                "MIDS 💜",
                "TREBLE 🩵"
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