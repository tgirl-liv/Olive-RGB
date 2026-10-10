"""LIVE Movie/Gaming controls. Capture threads publish snapshots; Qt routes them."""
import time
from PySide6.QtCore import QTimer,QSignalBlocker
from PySide6.QtWidgets import QComboBox,QHBoxLayout
from .music_window import MusicLiveWindow
from .screen_adapter import ScreenLightingAdapter
from .screen_runtime import ScreenRuntime
from .widgets.common import Panel,button,text,slider,assign
from .widgets.light_preview import VirtualLightPreview


class ScreenLiveWindow(MusicLiveWindow):
    def __init__(self,*args,screen_factory=None,monitor_scanner=None,**kwargs):
        super().__init__(*args,adapter_factory=ScreenLightingAdapter,**kwargs)
        self.screen_runtime=ScreenRuntime(screen_factory,monitor_scanner)
        runtime=self.screen_runtime
        self.destroyed.connect(lambda *_:runtime.close())
        self._pending_screen_mode=None;self._pending_music=False;self._last_screen_frame=None
        self.setWindowTitle('Olive RGB Studio · LIVE Manual / Music / Movie / Gaming')
        self.mode_badge.setText('LIVE · MUSIC / SCREEN')
        panel=Panel('LIVE SCREEN LIGHTING')
        self.screen_status=text('Select a monitor, then explicitly Start Movie or Gaming.','muted');self.screen_status.setWordWrap(True);panel.box.addWidget(self.screen_status)
        self.monitor=QComboBox();self.monitor.setAccessibleName('Screen capture monitor');panel.box.addWidget(self.monitor)
        self.refresh_monitors_button=button('Refresh monitors',self.refresh_monitors);panel.box.addWidget(self.refresh_monitors_button)
        values=self.preferences['screen'];self.screen_intensity=slider(round(values['intensity']*100),high=200);self.screen_intensity.setMinimum(25)
        self.screen_saturation=slider(round(values['saturation']*100),high=250);self.screen_saturation.setMinimum(50)
        self.screen_labels={}
        for name,control in (('Intensity',self.screen_intensity),('Saturation',self.screen_saturation)):
            control.setAccessibleName('Screen '+name.lower());label=text('');self.screen_labels[name]=label;panel.box.addWidget(label);panel.box.addWidget(control)
            control.valueChanged.connect(self.screen_settings_changed)
        note=text('Capture region: whole selected monitor (original behavior). Movie uses smooth 80 ms sampling; Gaming uses responsive 40 ms sampling and impact boosts. Responsiveness is fixed by mode. Hue follows Screen when Follow Master is ON.','muted');note.setWordWrap(True);panel.box.addWidget(note)
        row=QHBoxLayout();self.movie_start=button('Start Movie',lambda:self.start_screen('Movie'));self.gaming_start=button('Start Gaming',lambda:self.start_screen('Gaming'));self.screen_stop=button('Stop Screen',self.stop_screen)
        for control in (self.movie_start,self.gaming_start,self.screen_stop):row.addWidget(control)
        panel.box.addLayout(row)
        self.screen_preview=VirtualLightPreview();panel.box.addWidget(self.screen_preview)
        self.pages.widget(2).widget().layout().insertWidget(1,panel)
        self.page_notes['Screen'].setText('LIVE MSS capture runs in the background. Monitor, intensity and saturation persist; launch stays idle. Protected video may appear black. Preview is read-only.')
        self.master.modes['Screen'].clicked.connect(lambda:self.c.navigate('Screen'))
        self.master.modes['Manual'].clicked.connect(self.stop_screen)
        self.stop_shortcut.activated.connect(self.stop_screen)
        self.monitor.currentIndexChanged.connect(self.monitor_changed)
        self.screen_timer=QTimer(self);self.screen_timer.setInterval(33);self.screen_timer.timeout.connect(self.poll_screen);self.screen_timer.start()
        self._saved_monitor=values['monitor'];self.screen_settings_changed();self.refresh_monitors();self.live_controls()

    def screen_preferences(self):
        if not hasattr(self,'screen_runtime'):return self.preferences['screen']
        return {'monitor':self.monitor.currentData() or self._saved_monitor,'intensity':self.screen_intensity.value()/100,'saturation':self.screen_saturation.value()/100}

    def screen_settings_changed(self,*args):
        if not hasattr(self,'screen_runtime'):return
        values=self.screen_preferences();self.screen_runtime.configure(**values)
        for name,control in (('Intensity',self.screen_intensity),('Saturation',self.screen_saturation)):
            self.screen_labels[name].setText(name+f': {control.value()}%')
        self.queue_preferences()

    def monitor_changed(self,*args):
        if self.monitor.currentData() is not None:self._saved_monitor=self.monitor.currentData()
        self.screen_settings_changed()
        if self.c.adapter.screen_active:self.start_screen(self.c.state.mode)

    def refresh_monitors(self):
        if self.screen_runtime.refresh_monitors():self.screen_status.setText('Discovering monitors…')
        self.live_controls()

    def start_screen(self,mode):
        if self._closing or self.monitor.currentData() is None:return
        self._pending_music=False
        MusicLiveWindow.stop_music(self)
        self.screen_runtime.stop();self.c.adapter.stop_screen()
        self._pending_screen_mode=mode;self._last_screen_frame=None
        self.screen_status.setText('Stopping previous capture before '+mode+'…');self.live_controls()

    def stop_screen(self):
        if not hasattr(self,'screen_runtime'):return
        self._pending_screen_mode=None;self._pending_music=False
        self.screen_runtime.stop();self.c.adapter.stop_screen();self._last_screen_frame=None
        self.c.state.mode='Manual';self.c.changed.emit();self.live_controls()
        self.screen_status.setText('Stopping screen capture…' if self.screen_runtime.busy else 'Screen stopped · manual control restored')

    def start_music(self):
        if hasattr(self,'screen_runtime'):
            self.stop_screen()
            if self.screen_runtime.busy:
                self._pending_music=True;self.music_status.setText('Waiting for Screen capture to stop…');return
        super().start_music()

    def poll_screen(self):
        r=self.screen_runtime
        if self._closing:
            if not r.busy and not r.scanning and self._cleanup_done and not self.runtime.busy:self.close()
            return
        if r.monitors is not None:
            with r.lock:monitors=r.monitors;r.monitors=None;error=r.scan_error
            blocker=QSignalBlocker(self.monitor);self.monitor.clear()
            for i,m in enumerate(monitors,1):self.monitor.addItem(f'Monitor {i} · {m["width"]}×{m["height"]} · ({m["left"]}, {m["top"]})',i)
            index=self.monitor.findData(self._saved_monitor)
            self.monitor.setCurrentIndex(index if index>=0 else 0);del blocker
            if monitors:
                missing=index<0
                self._saved_monitor=self.monitor.currentData();self.screen_settings_changed()
                self.screen_status.setText('Saved monitor unavailable; selected Monitor 1. Press Start.' if missing else 'Ready · whole selected monitor · no connection required')
            else:self.screen_status.setText(error)
        if self._pending_music and not r.busy:
            self._pending_music=False;super().start_music()
        if self._pending_screen_mode and not r.busy and not self.runtime.busy:
            mode=self._pending_screen_mode;self._pending_screen_mode=None;self.screen_settings_changed()
            if r.start(mode):self.c.adapter.start_screen();self.c.state.mode=mode;self.c.changed.emit()
        frame,message,error,wanted=r.take()
        if self.c.adapter.screen_active:
            if error or not wanted:
                self.c.adapter.stop_screen();self.c.state.mode='Manual';self._last_screen_frame=None;self.c.changed.emit()
                self.screen_status.setText(error or 'Screen capture stopped · manual control restored')
            elif frame is not None and 0<=time.monotonic()-frame[2]<=1:
                self._last_screen_frame=frame;self.c.adapter.apply_screen(frame[0]);self.screen_status.setText(frame[1]+' · measured screen RGB · '+message)
            elif self._last_screen_frame and time.monotonic()-self._last_screen_frame[2]>1:
                self.screen_runtime.stop();self.c.adapter.stop_screen();self.c.state.mode='Manual';self._last_screen_frame=None;self.c.changed.emit()
                self.screen_status.setText('Screen data stale · capture stopped; press Start to retry')
            else:self.screen_status.setText(message)
        self.live_controls()

    def poll_music(self):
        if getattr(self.c.adapter,'screen_active',False):self.music_timer.stop();return
        super().poll_music()

    def live_controls(self):
        super().live_controls()
        if not hasattr(self,'screen_timer'):return
        r=self.screen_runtime;ready=not self._closing and self.monitor.currentData() is not None
        for control in (self.movie_start,self.gaming_start):control.setEnabled(ready)
        self.screen_stop.setEnabled(not self._closing and (r.busy or self.c.adapter.screen_active or self._pending_screen_mode is not None))
        self.refresh_monitors_button.setEnabled(not self._closing and not r.busy and not r.scanning)
        self.monitor.setEnabled(not self._closing and not r.scanning)
        self.master.modes['Screen'].setEnabled(not self._closing)
        assign(self.master.modes['Screen'],self.c.adapter.screen_active)
        for control in (self.screen_intensity,self.screen_saturation):control.setEnabled(not self._closing)
        frame=self._last_screen_frame
        if self.c.adapter.screen_active and frame and time.monotonic()-frame[2]<=1:
            self.screen_preview.update_light_preview(self.c.adapter.corner_music_rgb(frame[0]),frame[0],'Read-only Bluetooth-channel output · '+('connected' if self.c.adapter.connected else 'disconnected; no light required'))
        else:self.screen_preview.update_light_preview(None,None,'Waiting for measured screen data.' if self.c.adapter.screen_active else 'Screen stopped.')
        if self.c.adapter.screen_active and self.c.adapter.owns(self.c.state.selected_channel):
            self.inspector.status.setText('LIVE · Screen owns color')
        self.refresh_manual_target()

    def closeEvent(self,event):
        if hasattr(self,'screen_runtime'):
            self._pending_screen_mode=None;self._pending_music=False;self.screen_runtime.close()
            if self._cleanup_done and (self.screen_runtime.busy or self.screen_runtime.scanning):event.ignore();return
        super().closeEvent(event)
        if hasattr(self,'screen_timer') and self._cleanup_done and not self.screen_runtime.busy and not self.screen_runtime.scanning and not self.runtime.busy:self.screen_timer.stop()
