"""Music ownership and transport bridges around the unchanged production router."""
from .dual_adapter import DualLightingAdapter


class CornerOutput:
    def __init__(self, owner):self.owner = owner
    def set_rgb(self, *rgb, force=False):self.owner.music_color('Corner', rgb)


class HueOutput:
    def __init__(self, owner):self.owner = owner
    def update(self, master=None, **kwargs):
        if master is not None:self.owner.music_color('Hue', master['rgb'])


class MusicLightingAdapter(DualLightingAdapter):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.music_active = False
        self.participation = {'Corner':True,'Hue':True}
        self.music_colors = {}
        self.router = None
        self.last_frame = None

    def owns(self, key):
        connected = self.connected if key == 'Corner' else self.hue_connected
        return self.music_active and self.participation[key] and connected

    def start_music(self, relationship='Coordinated Colors', separation=.25):
        if self.closed or self.music_active:return
        from music_coordination import MusicLightingRouter
        self.router = MusicLightingRouter(CornerOutput(self), HueOutput(self))
        self.router.configure_music(relationship,separation)
        self.router.start_music()  # bridge ignores startup placeholder until a real frame arrives
        self.music_active = True;self.music_colors = {};self.last_frame = None

    def apply_frame(self, frame):
        if not self.music_active or self.closed:return
        self.last_frame = frame;self.router.set_music_frame(frame)

    def music_color(self, key, rgb):
        if not self.music_active or self.last_frame is None:return
        self.music_colors[key] = tuple(rgb)
        if not self.owns(key):return
        if key == 'Corner':
            self.session.color(self.corner_music_rgb(rgb));return
        channel = self.state.channels[key]
        scale = channel.brightness * (self.state.master_brightness if channel.follow else 1.)
        on = channel.power and (self.state.master_power or not channel.follow)
        intensity = max(rgb)/255 * scale
        values = dict(power=bool(on and intensity>0), brightness=max(1,min(254,round(intensity*254))))
        if self.hue_caps.get('color'):values['color'] = tuple(rgb)
        self.hue.update(values)

    def corner_music_rgb(self, rgb):
        """Exact Corner output calculation shared by transport and read-only preview."""
        channel=self.state.channels['Corner']
        scale=channel.brightness*(self.state.master_brightness if channel.follow else 1.)
        on=channel.power and (self.state.master_power or not channel.follow)
        return tuple(round(c*scale) for c in rgb) if on else (0,0,0)

    def _queue(self):
        if self.owns('Corner'):
            if 'Corner' in self.music_colors:self.music_color('Corner', self.music_colors['Corner'])
        else:super()._queue()

    def _queue_hue(self, color=False):
        if self.owns('Hue'):
            if 'Hue' in self.music_colors:self.music_color('Hue', self.music_colors['Hue'])
        else:super()._queue_hue(color)

    def set_rgb(self, device_id, color):
        if self.owns(device_id):raise ValueError('Music owns this device. Disable participation or Stop Music to edit manual color.')
        super().set_rgb(device_id,color)

    def set_participation(self, key, enabled):
        was = self.owns(key);self.participation[key] = bool(enabled)
        if was and not enabled and key in self.music_colors:self.restore_manual(key)
        elif self.owns(key) and key in self.music_colors:self.music_color(key,self.music_colors[key])

    def restore_manual(self, key):
        if key == 'Corner':super()._queue()
        elif self.hue_connected:
            # Replace the complete latest state; old music fields cannot linger.
            with self.hue.lock:self.hue.pending = {}
            super()._queue_hue(color=self.hue_caps.get('color',False))

    def stop_music(self):
        if not self.music_active:return
        owned = [key for key in self.participation if self.owns(key) and key in self.music_colors]
        self.music_active = False;self.music_colors = {};self.last_frame = None
        self.router.stop_music()  # disabled bridge; restore each device's own manual state
        for key in owned:self.restore_manual(key)

    def select_mode(self, mode):
        if mode == 'Music':return  # actual capture is controlled explicitly by the window
        super().select_mode(mode)

    def close(self):
        self.music_active = False;self.last_frame = None
        super().close()
