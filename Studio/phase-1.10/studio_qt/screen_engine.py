"""Verbatim Tkinter ScreenEngine, isolated from Tk and hardware imports."""
import threading,time
import numpy as np
import mss

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

