"""Verbatim production engine and dependencies; no Tk import or engine rewrite."""
import threading,time,re
import numpy as np
import soundcard as sc
from music_coordination import MusicFrame

DEFAULT_MUSIC_COLORS = {"bass": "#FF0A46", "mids": "#9614FF", "treble": "#00D2FF", "beat": "#FFFFFF"}

MUSIC_PRESETS = {
    "The Weeknd — After Hours": dict(bass="#B00020", mids="#FF2438", treble="#FF9B50", beat="#FFF0DC"),
    "The Weeknd — Dawn FM": dict(bass="#162D88", mids="#526FFF", treble="#00DBFF", beat="#E9F7FF"),
    "The Weeknd — Starboy": dict(bass="#E00032", mids="#8024C9", treble="#008FFF", beat="#FFFFFF"),
    "Charli xcx — BRAT": dict(bass="#6DB800", mids="#8ACE00", treble="#CBFF55", beat="#F2FFD9"),
    "Charli xcx — Crash": dict(bass="#C41235", mids="#FF4266", treble="#5BD5E8", beat="#FFE8E0"),
}

AUDIO_SAMPLE_RATE = 48000

AUDIO_FRAMES = 4096

BASS_RANGE = (40, 250)

MID_RANGE = (250, 2000)

TREBLE_RANGE = (2000, 12000)

def validated_music_colors(value):
    value = value if isinstance(value, dict) else {}
    return {key: value[key].upper() if isinstance(value.get(key), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", value[key]) else default
            for key, default in DEFAULT_MUSIC_COLORS.items()}

def color_rgb(value):
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))

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
        self.analysis_callback = None
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

                        if self.analysis_callback is not None:
                            total = float(np.sum(relative)) + 1e-9
                            self.analysis_callback(MusicFrame(
                                tuple(int(c) for c in rgb),
                                float(relative[0])/total, float(relative[1])/total,
                                float(relative[2])/total, rms, bool(beat), time.monotonic()))
                        else:
                            self.rgb_callback(int(rgb[0]), int(rgb[1]), int(rgb[2]))

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
