"""Resolve the Windows default output to a loopback, never a physical microphone.

The unchanged MusicEngine still owns its single recorder and device-change loop.
This facade only validates/resolves the backend endpoint on that capture thread.
"""
import threading
import sys
import soundcard


class LoopbackAudio:
    def __init__(self,backend):
        self.backend=backend;self.local=threading.local()

    def default_speaker(self):
        speaker=self.backend.default_speaker()
        if speaker is None or not getattr(speaker,'name',None) or getattr(speaker,'id',None) is None:
            raise RuntimeError('No valid default audio output device. Select an enabled Windows playback device.')
        self.local.speaker=speaker
        return speaker

    def get_microphone(self,name,include_loopback=False):
        if not include_loopback:raise RuntimeError('Music capture requires output loopback')
        speaker=getattr(self.local,'speaker',None)
        if speaker is None:raise RuntimeError('No default output was selected for loopback capture')
        # SoundCard name/fuzzy matching includes physical inputs. WASAPI loopbacks
        # use the playback endpoint ID; exact identity avoids ambiguous names.
        inputs=self.backend.all_microphones(include_loopback=True)
        matches=[device for device in inputs if getattr(device,'isloopback',False) and device.id==speaker.id]
        if len(matches)==1:return matches[0]
        if sys.platform=='win32':
            raise RuntimeError(f'No enabled loopback matches Windows default output {speaker.name} ({speaker.id})')
        # PulseAudio monitor IDs differ from sink IDs. Permit its existing name
        # lookup only when the resulting input is genuinely a loopback.
        try:device=self.backend.get_microphone(name,include_loopback=True)
        except Exception as error:
            raise RuntimeError(f'Loopback unavailable for {speaker.name} ({speaker.id}): {error}') from error
        if not getattr(device,'isloopback',False):
            raise RuntimeError(f'No valid output loopback for {speaker.name} ({speaker.id}); backend selected a physical microphone')
        return device


audio=LoopbackAudio(soundcard)
