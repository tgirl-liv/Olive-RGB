"""GUI-owned Screen routing through existing throttled sessions, never transport."""
from .music_adapter import MusicLightingAdapter
from .dual_adapter import DualLightingAdapter


class ScreenLightingAdapter(MusicLightingAdapter):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.screen_active=False;self.screen_rgb=None

    def owns(self,key):
        if self.screen_active:
            return (self.connected if key=='Corner' else self.hue_connected and self.state.channels[key].follow)
        return super().owns(key)

    def start_music(self,*args,**kwargs):
        if self.screen_active:raise RuntimeError('Stop Screen before starting Music')
        return super().start_music(*args,**kwargs)

    def start_screen(self):
        if self.music_active:raise RuntimeError('Stop Music before starting Screen')
        if not self.closed:self.screen_active=True;self.screen_rgb=None

    def apply_screen(self,rgb):
        if not self.screen_active or self.closed:return
        self.screen_rgb=tuple(rgb);self._queue()
        if self.owns('Hue'):self._queue_hue(color=True)

    def _queue(self):
        if self.screen_active:
            if self.owns('Corner') and self.screen_rgb is not None:self.session.color(self.corner_music_rgb(self.screen_rgb))
        else:super()._queue()

    def _queue_hue(self,color=False):
        if self.screen_active and self.owns('Hue'):
            if self.screen_rgb is None:return
            rgb=self.screen_rgb;channel=self.state.channels['Hue']
            scale=channel.brightness*self.state.master_brightness
            on=channel.power and self.state.master_power
            intensity=max(rgb)/255*scale
            values={}
            if self.hue_caps.get('power'):values['power']=bool(on and intensity>0)
            if self.hue_caps.get('brightness'):values['brightness']=max(1,min(254,round(intensity*254)))
            if color and self.hue_caps.get('color'):values['color']=rgb
            if values:self.hue.update(values)
        else:
            # Hue opted out of Screen by disabling Follow Master.
            if self.screen_active:
                with self.hue.lock:self.hue.pending={}
                DualLightingAdapter._queue_hue(self,color)
            else:super()._queue_hue(color)

    def set_rgb(self,key,color):
        if self.screen_active and self.owns(key):raise ValueError('Screen owns this device. Stop Screen to edit manual color.')
        super().set_rgb(key,color)

    def set_participation(self,key,enabled):
        if self.screen_active:self.participation[key]=bool(enabled)
        else:super().set_participation(key,enabled)

    def stop_screen(self):
        if not self.screen_active:return
        owned=[key for key in ('Corner','Hue') if self.owns(key)]
        self.screen_active=False;self.screen_rgb=None
        for key in owned:self.restore_manual(key)

    def close(self):
        self.screen_active=False;self.screen_rgb=None;super().close()
