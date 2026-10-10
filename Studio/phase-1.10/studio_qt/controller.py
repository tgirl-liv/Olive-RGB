"""Qt signals around the unchanged, framework-neutral mock state model."""
import time
import colorsys
from .capture_diagnostics import emit
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QColor
from studio_ui.state import StudioState
from .backend_adapter import MockLightingAdapter


class StudioController(QObject):
    changed = Signal()
    output_changed = Signal()

    def __init__(self, state=None, parent=None, adapter=None):
        super().__init__(parent)
        self.state = state or StudioState()
        self.adapter = adapter or MockLightingAdapter(self.state, self)
        self.display_colors = {k:v.color for k,v in self.state.channels.items()}
        self.manual_target = None  # LIVE-only view selection; never persisted as device state.
        self.manual_feedback = ''
        self.transition = None
        self.transition_progress = 1.

    def set(self, name, value):
        if name=='mode':
            self.request_mode(value);return
        self._set(name,value)

    def request_mode(self,value):
        """One dispatch point for the actual selector and other mode requests."""
        if getattr(self.adapter,"live",False):
            emit('controller.mode.request',music=value=='Music',screen=value=='Screen',manual=value=='Manual')
            handler=getattr(self,"mode_request",None)
            if handler is not None:
                handler(value);return
            if value!="Manual":return
        self._set('mode',value)

    def _set(self,name,value):
        if name in ('master_power','master_brightness'):
            self.adapter.set_master(value if name=='master_power' else self.state.master_power,
                                    value if name=='master_brightness' else self.state.master_brightness)
        elif name=='mode':self.adapter.select_mode(value)
        setattr(self.state, name, value)
        self.changed.emit()

    def navigate(self, page):
        self.state.navigate(page); self.changed.emit()

    def select_channel(self, channel):
        self.manual_target = None;self.manual_feedback = ''
        self.state.select_channel(channel); self.changed.emit()

    def select_target(self, target):
        if target == 'Both' and getattr(self.adapter,'live',False):
            self.manual_target = 'Both';self.manual_feedback = '';self.changed.emit()
        else:self.select_channel(target)

    def target_devices(self):
        return ('Corner','Hue') if self.manual_target == 'Both' else (self.state.selected_channel,)

    def target_reason(self, key, field):
        a=self.adapter
        if a.closed:return 'shutting down'
        connected=a.connected if key=='Corner' else getattr(a,'hue_connected',False)
        if not connected:return 'disconnected'
        capability='color' if field=='color' else field
        supported=(field!='power' or a.software_power) if key=='Corner' else getattr(a,'hue_caps',{}).get(capability,False)
        if not supported:return capability+' unsupported'
        if field=='color' and hasattr(a,'owns') and a.owns(key):return ('Screen' if getattr(a,'screen_active',False) else 'Music')+' owns color'
        return ''

    def manual_reference(self):
        return next((key for key in self.target_devices() if not self.target_reason(key,'color')),self.target_devices()[0]) if getattr(self.adapter,'live',False) else self.state.selected_channel

    def manual_hsv(self):
        color=self.state.channels[self.manual_reference()].color
        return colorsys.rgb_to_hsv(*(int(color[i:i+2],16)/255 for i in (1,3,5)))

    def apply_manual(self, field, value):
        reasons=[]
        for key in self.target_devices():
            reason=self.target_reason(key,field)
            if reason:reasons.append(key+': '+reason);continue
            method={'color':self.adapter.set_rgb,'power':self.adapter.set_power,'brightness':self.adapter.set_brightness}[field]
            method(key,value)
            setattr(self.state.channels[key],'color' if field=='color' else field,value)
            reasons.append(key+': '+field+' updated')
        self.manual_feedback=' · '.join(reasons)
        if field=='color':self._manual_color()
        else:self.changed.emit()

    def manual_channel(self, name, value):
        if getattr(self.adapter,'live',False):self.apply_manual(name,value)
        else:self.channel(self.state.selected_channel,name,value)

    def channel(self, key, name, value):
        if name=='follow' and not value and self.transition is not None:
            start,source,target,seconds,curve=self.transition
            source[key]=target[key]=self.display_colors[key]
            self.state.channels[key].color=self.display_colors[key].upper()
        {'power':self.adapter.set_power,'brightness':self.adapter.set_brightness,
         'follow':self.adapter.set_follow_master}[name](key,value)
        setattr(self.state.channels[key],name,value)
        self.changed.emit()

    def favorite(self, name):
        self.state.toggle_favorite(name); self.changed.emit()

    def select_scene(self, name, now=None):
        if getattr(self.adapter,"live",False):return
        self.adapter.apply_scene(name)
        self.state.select_scene(name)
        target = {k:v.color for k,v in self.state.channels.items()}
        duration = self.state.transition_seconds if self.state.motion else 0
        self.transition = (time.monotonic() if now is None else now, dict(self.display_colors), target,
                           duration, self.state.transition_curve)
        self.transition_progress = 0.
        self.changed.emit()
        self.advance(time.monotonic() if now is None else now)

    def set_transition(self, seconds, curve='Smooth'):
        self.state.set_transition(seconds, curve); self.changed.emit()

    def set_hex(self, value):
        if getattr(self.adapter,'live',False):
            candidate=StudioState();candidate.set_hex(value)
            self.apply_manual('color',candidate.channels[candidate.selected_channel].color)
        else:
            self.adapter.set_rgb(self.state.selected_channel,value);self.state.set_hex(value);self._manual_color()

    def set_hsv(self, h, s, v):
        candidate=StudioState();candidate.set_hsv(h,s,v)
        self.set_hex(candidate.channels[candidate.selected_channel].color)

    def _manual_color(self):
        self.transition = None
        self.display_colors = {k:v.color for k,v in self.state.channels.items()}
        self.changed.emit(); self.output_changed.emit()

    def advance(self, now):
        if self.transition is None:return
        start, source, target, seconds, curve = self.transition
        t = 1. if not self.state.motion or seconds<=0 or curve=='Instant' else max(0.,min(1.,(now-start)/seconds))
        amount = t*t*(3-2*t) if curve=='Smooth' else t
        for key,value in target.items():
            a,b = QColor(source[key]),QColor(value)
            self.display_colors[key] = QColor(*(round(x+(y-x)*amount) for x,y in zip(a.getRgb()[:3],b.getRgb()[:3]))).name()
        self.transition_progress = t
        if t>=1:self.transition=None
        self.output_changed.emit()
