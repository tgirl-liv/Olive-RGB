"""Qt lifecycle wrapper around the existing Windows artwork worker; no Qt calls."""
import asyncio
import io
import threading
from album_colors import AlbumArtworkWorker


class StudioAlbumArtworkWorker(AlbumArtworkWorker):
    def __init__(self):
        self._lifecycle=threading.Lock();self._loop=None;self._task=None
        super().__init__()

    def _describe(self, session, props):
        return 'Player: '+str(session.source_app_user_model_id or 'Unknown player')+'\nTrack: '+super()._describe(session,props)

    def _publish(self, message):
        kind,description,palette,data=message
        if kind=='artwork':
            # Only small PNG previews reach Qt. Decoding the original cover and
            # extracting its palette both remain on the existing media thread.
            from PIL import Image,ImageOps
            try:
                with Image.open(io.BytesIO(data)) as image:
                    preview=ImageOps.exif_transpose(image).convert('RGB')
                    preview.thumbnail((110,110))
                    output=io.BytesIO();preview.save(output,format='PNG');data=output.getvalue()
            except (OSError,ValueError) as error:
                data=None;description+='\nPreview unavailable: '+type(error).__name__
        elif description.startswith('Album colors need'):
            description='Optional media dependencies unavailable. Install requirements-studio-album.txt; using preset colors.'
        if kind=='fallback':description=description.replace('custom colors','preset colors')
        super()._publish((kind,description,palette,data))

    def _run(self):
        loop=asyncio.new_event_loop()
        with self._lifecycle:
            self._loop=loop;self._task=loop.create_task(self._watch())
            if self.closed.is_set():self._task.cancel()
        try:
            loop.run_until_complete(self._task)
        except asyncio.CancelledError:
            pass  # Explicit close cancels in-flight WinRT waits and polling sleeps.
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            with self._lifecycle:
                self._loop=None;self._task=None;loop.close()

    def close(self):
        super().close()
        with self._lifecycle:
            if self._loop is not None:self._loop.call_soon_threadsafe(self._task.cancel)
