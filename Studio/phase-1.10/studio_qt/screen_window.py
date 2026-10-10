"""LIVE Movie/Gaming controls. Capture threads publish snapshots; Qt routes them."""
import time
from PySide6.QtCore import QTimer,QSignalBlocker
from PySide6.QtWidgets import QComboBox,QHBoxLayout
from studio_ui.state import NAVIGATION
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
        self._screen_mode=self.preferences['screen']['capture_mode']
        self.c.mode_request=self.request_mode
        self.setWindowTitle('Olive RGB Studio · LIVE Manual / Music / Movie / Gaming')
        self.mode_badge.setText('LIVE · MUSIC / SCREEN')
        panel=Panel('LIVE SCREEN LIGHTING')
        self.screen_status=text('Select Screen to start saved Movie/Gaming capture; select Manual to stop.','muted');self.screen_status.setWordWrap(True);panel.box.addWidget(self.screen_status)
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
        self.pages.widget(NAVIGATION.index('Screen')).widget().layout().insertWidget(1,panel)
        self.page_notes['Screen'].setText('LIVE MSS capture runs in the background. Monitor, intensity and saturation persist; launch stays idle. Protected video may appear black. Preview is read-only.')
        self.monitor.currentIndexChanged.connect(self.monitor_changed)
        self.screen_timer=QTimer(self);self.screen_timer.setInterval(33);self.screen_timer.timeout.connect(self.poll_screen);self.screen_timer.start()
        self._saved_monitor=values['monitor'];self.screen_settings_changed();self.refresh_monitors()
        self.c.changed.connect(self.sync_mode_selector);self.live_controls()

    def request_mode(self,mode,restart=False):
        """GUI-only latest request. Never start a new capture until both drain."""
        if self._closing:return
        if mode=='Screen':mode=self._screen_mode
        if mode not in ('Manual','Music','Movie','Gaming'):raise ValueError('Unsupported mode')
        if mode in ('Movie','Gaming'):self.c.navigate('Screen')
        a=self.c.adapter
        pending=self._pending_screen_mode or ('Music' if self._pending_music else None)
        active='Music' if a.music_active or self.runtime.wanted else self._screen_mode if a.screen_active or self.screen_runtime.wanted else 'Manual'
        if not restart and (mode==pending or (pending is None and mode==active and (mode!='Manual' or (self.c.state.mode=='Manual' and not (self.runtime.wanted or self.screen_runtime.wanted))))):
            self.sync_mode_selector();return
        MusicLiveWindow.stop_music(self)
        self.screen_runtime.stop();a.stop_screen();self._last_screen_frame=None
        self._pending_music=mode=='Music'
        self._pending_screen_mode=mode if mode in ('Movie','Gaming') else None
        if self._pending_screen_mode:
            self._screen_mode=mode;self.queue_preferences()
        self.c.state.mode='Manual';self.c.changed.emit()
        if mode!='Manual':
            status=self.music_status if mode=='Music' else self.screen_status
            status.setText('Waiting for previous capture to stop…')
        else:self.screen_status.setText('Screen stopped · manual control restored')
        self.live_controls()

    def select_screen(self):self.request_mode('Screen')

    def sync_mode_selector(self):
        mode='Screen' if self.c.state.mode in ('Screen','Movie','Gaming') else self.c.state.mode
        for name,control in self.master.modes.items():assign(control,name==mode)

    def screen_preferences(self):
        if not hasattr(self,'screen_runtime'):return self.preferences['screen']
        return {'capture_mode':self._screen_mode,'monitor':self.monitor.currentData() or self._saved_monitor,'intensity':self.screen_intensity.value()/100,'saturation':self.screen_saturation.value()/100}

    def screen_settings_changed(self,*args):
        if not hasattr(self,'screen_runtime'):return
        values=self.screen_preferences();self.screen_runtime.configure(**{k:v for k,v in values.items() if k!='capture_mode'})
        for name,control in (('Intensity',self.screen_intensity),('Saturation',self.screen_saturation)):
            self.screen_labels[name].setText(name+f': {control.value()}%')
        self.queue_preferences()

    def monitor_changed(self,*args):
        if self.monitor.currentData() is not None:self._saved_monitor=self.monitor.currentData()
        self.screen_settings_changed()
        if self.c.adapter.screen_active:self.request_mode(self.c.state.mode,restart=True)

    def refresh_monitors(self):
        if self.screen_runtime.refresh_monitors():self.screen_status.setText('Discovering monitors…')
        self.live_controls()

    def start_screen(self,mode):self.request_mode(mode)

    def stop_screen(self):
        if hasattr(self,'screen_runtime'):self.request_mode('Manual')

    def start_music(self):
        if hasattr(self,'screen_runtime'):self.request_mode('Music')
        else:super().start_music()

    def stop_music(self):
        if hasattr(self,'screen_runtime'):self.request_mode('Manual')
        else:super().stop_music()

    def activation_failed(self,message,status):
        self.request_mode('Manual');status.setText(message)

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
                self.screen_status.setText('Saved monitor unavailable; selected Monitor 1. Select Screen to start.' if missing else 'Ready · whole selected monitor · no connection required')
            else:self.screen_status.setText(error)
        if not r.busy and not self.runtime.busy:
            if self._pending_music:
                self._pending_music=False
                try:
                    MusicLiveWindow.start_music(self)
                    if not self.runtime.wanted:raise RuntimeError(self.runtime.error or 'Audio activation refused')
                except Exception as error:self.activation_failed(f'Audio activation failed: {error}',self.music_status)
            elif self._pending_screen_mode and not r.scanning:
                mode=self._pending_screen_mode;self._pending_screen_mode=None
                try:
                    if self.monitor.currentData() is None:raise RuntimeError(r.scan_error or 'No capturable monitor available')
                    self.screen_settings_changed()
                    if not r.start(mode):raise RuntimeError('Screen activation refused')
                    self.c.state.mode='Manual';self.c.changed.emit()
                except Exception as error:self.activation_failed(f'Screen activation failed: {error}',self.screen_status)
        frame,message,error,wanted=r.take()
        if wanted and not self.c.adapter.screen_active and not error:
            if frame is not None and 0<=time.monotonic()-frame[2]<=1:
                self.c.adapter.start_screen();self.c.state.mode=frame[1];self.c.changed.emit()
            elif r.started_at is not None and time.monotonic()-r.started_at>5:
                error='Screen startup timed out: no captured frames. Check monitor availability and capture permissions.'
            else:self.screen_status.setText(message+' · waiting for first captured frame')
        if not wanted and not error and r.started_at is not None and not self.c.adapter.screen_active:
            error='Screen capture ended before the first captured frame · '+message
        if error and (wanted or self.c.adapter.screen_active or r.started_at is not None):
            self.activation_failed(error,self.screen_status)
        elif self.c.adapter.screen_active:
            if not wanted:self.activation_failed('Screen capture stopped · manual control restored',self.screen_status)
            elif frame is not None and 0<=time.monotonic()-frame[2]<=1:
                self._last_screen_frame=frame;self.c.adapter.apply_screen(frame[0]);self.screen_status.setText(frame[1]+' · measured screen RGB · '+message)
            elif self._last_screen_frame and time.monotonic()-self._last_screen_frame[2]>1:
                self.activation_failed('Screen data stale · capture stopped; select Screen to retry',self.screen_status)
            else:self.screen_status.setText(message)
        self.live_controls()

    def poll_music(self):
        if not self._closing and not self.c.adapter.music_active and not self.runtime.wanted and self.runtime.started_at is None:
            # Stopped-generation messages cannot cancel a newer mode request.
            self.runtime.take();self.runtime.take_spectrum()
            if not self.runtime.busy:self.music_timer.stop()
            return
        running=self.c.adapter.music_active or self.runtime.wanted
        super().poll_music()
        if running and not self.runtime.wanted and not self.c.adapter.music_active and not self._closing:
            message=self.music_status.text()
            self.activation_failed(message,self.music_status)

    def live_controls(self):
        super().live_controls()
        if not hasattr(self,'screen_timer'):return
        r=self.screen_runtime;ready=not self._closing and self.monitor.currentData() is not None
        for control in (self.movie_start,self.gaming_start):control.setEnabled(ready)
        self.screen_stop.setEnabled(not self._closing and (r.busy or self.c.adapter.screen_active or self._pending_screen_mode is not None))
        self.refresh_monitors_button.setEnabled(not self._closing and not r.busy and not r.scanning)
        self.monitor.setEnabled(not self._closing and not r.scanning)
        self.master.modes['Screen'].setEnabled(not self._closing)
        self.sync_mode_selector()
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
