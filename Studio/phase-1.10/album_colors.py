"""Optional Windows media-artwork adapter. Never writes to the lamp or Tk widgets."""
import asyncio
import colorsys
import hashlib
import io
import queue
import threading


def palette_from_artwork(data):
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(data)) as original:
        image = ImageOps.exif_transpose(original).convert("RGBA")
        image.thumbnail((96, 96))
        backdrop = Image.new("RGBA", image.size, (0, 0, 0, 255))
        image = Image.alpha_composite(backdrop, image).convert("RGB")
        quantized = image.quantize(colors=12, method=Image.Quantize.MEDIANCUT)
        table = quantized.getpalette()
        candidates = []
        for count, index in quantized.getcolors():
            rgb = tuple(table[index * 3:index * 3 + 3])
            _, saturation, value = colorsys.rgb_to_hsv(*(c / 255 for c in rgb))
            candidates.append((count, rgb, saturation, value))
        # Prefer prominent colorful pixels, retaining neutral colors for grayscale covers.
        visible = [c for c in candidates if 0.12 < c[3] < 0.98 and c[2] > 0.12]
        choices = sorted(visible or candidates,
                         key=lambda c: c[0] * (0.5 + c[2]), reverse=True)
        selected = []
        for _, rgb, _, _ in choices:
            if all(sum((a - b) ** 2 for a, b in zip(rgb, other)) >= 40 ** 2 for other in selected):
                selected.append(rgb)
            if len(selected) == 3:
                break
        while len(selected) < 3:
            selected.append(selected[0])
        # Raise very dark colors slightly so an otherwise dark cover can illuminate a lamp.
        def readable(rgb):
            peak = max(rgb)
            return tuple(round(c * 90 / peak) for c in rgb) if 0 < peak < 90 else rgb
        selected = [readable(rgb) for rgb in selected]
        beat = max((c[1] for c in candidates), key=lambda rgb: sum(rgb))
        beat = readable(beat)
        return {key: "#" + "".join(f"{c:02X}" for c in rgb)
                for key, rgb in zip(("bass", "mids", "treble", "beat"), [*selected, beat])}


class AlbumArtworkWorker:
    def __init__(self):
        self.messages = queue.Queue(maxsize=1)
        self.enabled = threading.Event()
        self.closed = threading.Event()
        self.generation = 0
        self.thread = threading.Thread(target=self._run, daemon=True, name="OliveAlbumArtwork")
        self.thread.start()

    def _publish(self, message):
        try:
            self.messages.get_nowait()
        except queue.Empty:
            pass
        self.messages.put_nowait(message)

    def close(self):
        self.closed.set()
        self.enabled.set()

    def set_enabled(self, enabled):
        self.generation += 1
        if enabled:
            self.enabled.set()
        else:
            self.enabled.clear()

    def _describe(self, session, props):
        return " — ".join(v for v in (props.title, props.artist) if v) or "Current media"

    def _run(self):
        asyncio.run(self._watch())

    async def _watch(self):
        api = None
        last = None
        manager = None
        last_generation = -1
        while not self.closed.is_set():
            if not self.enabled.is_set():
                last = None
                await asyncio.sleep(0.2)
                continue
            generation = self.generation
            if generation != last_generation:
                last = None
                last_generation = generation
            try:
                if api is None:
                    import PIL.Image
                    from winrt.windows.media.control import (
                        GlobalSystemMediaTransportControlsSessionManager as Manager,
                        GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status,
                    )
                    from winrt.windows.storage.streams import Buffer, InputStreamOptions
                    api = Manager, Status, Buffer, InputStreamOptions
                Manager, Status, Buffer, InputStreamOptions = api
                if manager is None:
                    manager = await asyncio.wait_for(Manager.request_async(), timeout=8)
                session = manager.get_current_session()
                if session is None or session.get_playback_info().playback_status != Status.PLAYING:
                    session = next((s for s in manager.get_sessions()
                                    if s.get_playback_info().playback_status == Status.PLAYING), None)
                if session is None:
                    message = ("fallback", "No playing media session — using custom colors.", None, None)
                else:
                    props = await asyncio.wait_for(session.try_get_media_properties_async(), timeout=8)
                    if props is None or props.thumbnail is None:
                        message = ("fallback", "This player has no artwork — using custom colors.", None, None)
                    else:
                        # Streams and decoded images are scoped and bounded; retry late artwork next poll.
                        stream = await asyncio.wait_for(props.thumbnail.open_read_async(), timeout=8)
                        try:
                            size = int(stream.size)
                            if not 0 < size <= 10 * 1024 * 1024:
                                raise ValueError("Album artwork is empty or too large")
                            result = await asyncio.wait_for(
                                stream.read_async(Buffer(size), size, InputStreamOptions.READ_AHEAD), timeout=8)
                            data = bytes(memoryview(result))
                        finally:
                            stream.close()
                        identity = (session.source_app_user_model_id, props.title, props.artist,
                                    props.album_title, hashlib.sha256(data).hexdigest())
                        if identity == last:
                            await asyncio.sleep(2)
                            continue
                        palette = palette_from_artwork(data)
                        description = self._describe(session, props)
                        message = ("artwork", description, palette, data)
                        if self.enabled.is_set() and not self.closed.is_set() and generation == self.generation:
                            self._publish(message)
                            last = identity
                        await asyncio.sleep(2)
                        continue
            except ImportError:
                message = ("fallback", "Album colors need the optional dependencies. Run install_dependencies.bat, then restart.", None, None)
            except Exception as error:
                manager = None
                message = ("fallback", f"Artwork unavailable — using custom colors ({type(error).__name__}).", None, None)
            signature = message[:2]
            if signature != last and self.enabled.is_set() and not self.closed.is_set() and generation == self.generation:
                self._publish(message)
                last = signature
            await asyncio.sleep(2)
