"""Qt owns rendering/routing; production capture reports into one bounded mailbox."""
import time
from pathlib import Path
import weakref
from shiboken6 import isValid
from PySide6.QtCore import QTimer
from PySide6.QtGui import QShortcut,QKeySequence
from PySide6.QtWidgets import QHBoxLayout,QComboBox,QCheckBox,QLabel,QInputDialog,QMessageBox
from .dual_window import DualLiveWindow
from .music_adapter import MusicLightingAdapter
from .music_runtime import MusicRuntime
from .widgets.common import Panel,button,text,slider,assign
from .preferences import PROFILES,PALETTES
from .widgets.live_inspector import LiveMusicInspector,replace_tab
from .widgets.album_lighting import AlbumLightingPanel
from .music_themes import ThemeStore,ThemeJobs
from .widgets.music_theme_editor import MusicThemeEditor


class MusicLiveWindow(DualLiveWindow):
    def __init__(self, workspace_path=None, worker_factory=None, hue_factory=None, hue_identity=None, engine_factory=None,preferences_path=None,album_worker_factory=None,themes_path=None,adapter_factory=MusicLightingAdapter):
        adapter=adapter_factory(worker_factory=worker_factory,hue_factory=hue_factory,hue_identity=hue_identity)
        super().__init__(workspace_path=workspace_path,adapter=adapter,preferences_path=preferences_path)
        self.runtime=MusicRuntime(engine_factory)
        self.builtin_palette=self.preferences['music']['palette']
        library_path=themes_path if themes_path is not None else (Path(preferences_path).with_name('custom-music-themes-v1.json') if preferences_path is not None else None)
        try:
            if library_path is not None and preferences_path is not None and Path(library_path).resolve()==Path(preferences_path).resolve():
                raise ValueError('Theme library cannot overwrite Qt preferences')
            self.themes=ThemeStore(library_path)
        except ValueError as error:
            self.themes=ThemeStore();self.themes.blocked=True;self.themes.error=str(error)
        self.theme_jobs=ThemeJobs(self.themes);self._theme_completion=None;self._theme_close_pending=False
        self.theme_timer=QTimer(self);self.theme_timer.setInterval(25);self.theme_timer.timeout.connect(self.poll_theme_job)
        self.setWindowTitle('Olive RGB Studio · LIVE Manual / Music')
        self.mode_badge.setText('LIVE · MANUAL / MUSIC')
        self.reactor.enable_live()
        self.reactor.setAccessibleName('Live log-spaced audio spectrum and RMS level')
        self.reactor.setToolTip('72 log-spaced bands from the existing audio FFT (20 Hz–20 kHz). Adaptive visual gain and independent curve smoothing; no additional capture. Band meters show proportions; LEVEL maps RMS from -60 to -12 dBFS.')
        self.pause.hide()  # The DEMO pause control has no LIVE meaning; Stop is persistent.
        for label in self.reactor.parentWidget().findChildren(QLabel):
            if label.text()=='DEMO':label.setText('LIVE AUDIO')
        self.music_start=button('Start Music',self.start_music)
        self.music_stop=button('Stop Music',self.stop_music)
        self.music_status=text('Audio stopped · default Windows output loopback','muted');self.music_status.setWordWrap(True)
        row=QHBoxLayout();row.addWidget(self.music_status,1)
        self.centralWidget().layout().insertLayout(4,row)
        panel=Panel('LIVE MUSIC')
        actions=QHBoxLayout();actions.addWidget(self.music_start);actions.addWidget(self.music_stop);panel.box.addLayout(actions)
        note=text('Captures the Windows default output. Change output in Windows; the existing engine follows it. Stop / Esc releases music ownership.','muted');note.setWordWrap(True);panel.box.addWidget(note)
        self.profile=QComboBox();self.profile.addItems(PROFILES);self.profile.setCurrentText('Reactive');panel.box.addWidget(text('Production response profile'));panel.box.addWidget(self.profile)
        self.palette=QComboBox();self.palette.addItems(PALETTES);panel.box.addWidget(text('Production palette (Album artwork fallback)'));panel.box.addWidget(self.palette)
        for theme in self.themes.list():self.palette.addItem('Custom · '+theme['name'],theme['id'])
        row=QHBoxLayout();self.theme_buttons={}
        for action,callback in (('New',lambda:self.open_theme_editor('new')),('Edit',lambda:self.open_theme_editor('edit')),
                                ('Duplicate',lambda:self.open_theme_editor('duplicate')),('Rename',self.rename_theme),('Delete',self.delete_theme)):
            control=button(action,callback);self.theme_buttons[action]=control;row.addWidget(control)
        panel.box.addLayout(row)
        self.theme_notice=text(self.themes.error,'muted');self.theme_notice.setWordWrap(True);panel.box.addWidget(self.theme_notice)
        self.sensitivity=slider(100,high=300);self.sensitivity.setMinimum(25)
        self.smoothing=slider(100,high=140);self.smoothing.setMinimum(25)
        for name,widget in [('Sensitivity multiplier (%)',self.sensitivity),('Smoothing multiplier (%)',self.smoothing)]:
            widget.setAccessibleName(name);panel.box.addWidget(text(name));panel.box.addWidget(widget)
        self.output_brightness=slider(100);self.output_saturation=slider(100)
        self.adjustment_labels={}
        for name,widget in (('Brightness',self.output_brightness),('Saturation',self.output_saturation)):
            widget.setAccessibleName('Music-output '+name.lower())
            label=text('Music-output '+name.lower()+': 100%');self.adjustment_labels[name]=label
            panel.box.addWidget(label);panel.box.addWidget(widget)
        self.adjustment_reset=button('Reset Music brightness and saturation',self.reset_music_adjustments)
        panel.box.addWidget(self.adjustment_reset)
        self.harmony=QComboBox();self.harmony.addItems(['Coordinated Colors','Same Color']);panel.box.addWidget(text('Production color relationship'));panel.box.addWidget(self.harmony)
        self.separation=slider(25);panel.box.addWidget(text('Color separation (%)'));panel.box.addWidget(self.separation)
        for combo in (self.profile,self.palette,self.harmony):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(12)
            combo.currentTextChanged.connect(combo.setToolTip);combo.setToolTip(combo.currentText())
        self.participate={}
        for key in ('Corner','Hue'):
            check=QCheckBox(key+' participates in Music');check.setChecked(True)
            check.toggled.connect(lambda enabled,key=key:self.participation(key,enabled));panel.box.addWidget(check);self.participate[key]=check
        note=text('Music owns color only for participating connected devices. Local power/brightness remain effective; Follow Master ON additionally applies Master power/brightness. Opt out to edit manual color.','muted');note.setWordWrap(True);panel.box.addWidget(note)
        self.pages.widget(1).widget().layout().insertWidget(1,panel)
        self.c.mode_request=lambda mode:self.start_music() if mode=='Music' else self.stop_music() if mode=='Manual' else None
        self.stop_shortcut=QShortcut(QKeySequence('Esc'),self);self.stop_shortcut.activated.connect(self.stop_music)
        self.music_timer=QTimer(self);self.music_timer.setInterval(33);self.music_timer.timeout.connect(self.poll_music)
        if preferences_path is not None:
            music=self.preferences['music']
            for name in ('profile','palette'):assign(getattr(self,name),music[name])
            assign(self.harmony,music['relationship'])
            for name in ('sensitivity','smoothing','separation'):assign(getattr(self,name),round(music[name]*100))
            for name in ('output_brightness','output_saturation'):assign(getattr(self,name),round(music[name]*100))
            for key,enabled in music['participation'].items():
                assign(self.participate[key],enabled);adapter.set_participation(key,enabled)
        selected=self.preferences['music']['custom_theme_id']
        if selected is not None:
            index=self.palette.findData(selected)
            if index>=0:self.palette.setCurrentIndex(index)
            else:self.theme_notice.setText('Saved custom theme unavailable; using '+self.builtin_palette+'. '+self.themes.error)
        self.album=AlbumLightingPanel(self.runtime,self.palette,self.preferences['music']['color_source'],album_worker_factory,self.resolve_music_palette)
        self.palette.currentIndexChanged.connect(self.theme_selection_changed)
        self.pages.widget(1).widget().layout().insertWidget(2,self.album)
        self.album.source.currentTextChanged.connect(self.queue_preferences)
        for widget in (self.profile,self.palette,self.harmony):widget.currentTextChanged.connect(self.queue_preferences)
        for widget in (self.sensitivity,self.smoothing,self.separation):widget.valueChanged.connect(self.queue_preferences)
        for widget in self.participate.values():widget.toggled.connect(self.queue_preferences)
        self.profile.currentTextChanged.connect(self.update_music_response)
        self.sensitivity.valueChanged.connect(self.update_music_response)
        self.smoothing.valueChanged.connect(self.update_music_response)
        self.harmony.currentTextChanged.connect(self.update_music_routing)
        self.separation.valueChanged.connect(self.update_music_routing)
        for widget in (self.output_brightness,self.output_saturation):
            widget.valueChanged.connect(self.update_music_adjustments)
            widget.valueChanged.connect(self.queue_preferences)
        self.update_music_adjustments()
        self.page_notes['Music'].setText('LIVE music uses production capture after Start Music. Saved preferences never start capture or connect devices.')
        self.page_notes['Screen'].setText('Screen capture is unavailable in Qt Studio. DEMO inspector controls simulate output only.')
        self.page_notes['Settings'].setText('Qt preferences save automatically, separately from Tkinter settings. DEMO and LIVE configurations are isolated. Connections and running modes are never restored.')
        self.inspector.live_music=LiveMusicInspector(self)
        replace_tab(self.inspector,1,self.inspector.live_music,'Music')
        self.live_controls()

    def music_preferences(self):
        if not hasattr(self,'participate'):return super().music_preferences()
        return {'profile':self.profile.currentText(),'palette':self.fallback_palette(),
                'custom_theme_id':self.palette.currentData(),
                'color_source':self.album.source.currentText() if hasattr(self,'album') else 'Preset',
                'sensitivity':self.sensitivity.value()/100,'smoothing':self.smoothing.value()/100,
                'output_brightness':self.output_brightness.value()/100,'output_saturation':self.output_saturation.value()/100,
                'relationship':self.harmony.currentText(),'separation':self.separation.value()/100,
                'participation':{k:w.isChecked() for k,w in self.participate.items()}}

    def start_music(self):
        if self._closing or self.runtime.busy:return
        colors={'colors':self.album.current_palette} if self.album.source.currentText()=='Album artwork' or self.palette.currentData() is not None else {}
        if self.runtime.start(self.profile.currentText(),self.sensitivity.value()/100,self.smoothing.value()/100,self.fallback_palette(),**colors):
            self.music_timer.start()
            self.music_status.setText('Opening Windows default output loopback · waiting for measured audio…')
            self.c.state.mode='Manual';self.c.changed.emit()
        self.live_controls()

    def stop_music(self):
        if not hasattr(self,'runtime'):return
        self.runtime.stop();self.c.adapter.stop_music();self.c.state.mode='Manual';self.c.changed.emit()
        self.reactor.reset_live()
        self.music_status.setText('Stopping audio…' if self.runtime.busy else 'Audio stopped · manual control restored')
        self.live_controls()

    def fallback_palette(self):
        return self.palette.currentText() if self.palette.currentData() is None else self.builtin_palette

    def resolve_music_palette(self):
        return self.themes.resolve(self.palette.currentData(),self.fallback_palette())

    def theme_selection_changed(self,*args):
        if self.palette.currentData() is None:self.builtin_palette=self.palette.currentText()
        self.refresh_theme_buttons()

    def refresh_theme_buttons(self):
        editable=self.palette.currentData() is not None
        ready=not self._closing and not self.themes.blocked and not self.theme_jobs.busy
        for action,control in self.theme_buttons.items():control.setEnabled(ready and (editable or action in ('New','Duplicate')))

    def open_theme_editor(self,action):
        if self.theme_jobs.busy or self.themes.blocked or self._closing:return
        identifier=self.palette.currentData();theme=self.themes.get(identifier)
        if action=='edit' and theme is None:return
        name=theme['name'] if theme is not None else self.palette.currentText()
        if action!='edit':name=('New theme' if action=='new' else name+' copy');identifier=None
        colors=self.resolve_music_palette()
        dialog=MusicThemeEditor(name,colors,identifier,self)
        reference=weakref.ref(dialog)
        def save(identifier,name,colors,select):
            def finished(error):
                editor=reference()
                if editor is not None and isValid(editor):editor.save_finished(error)
            if not self.save_theme(identifier,name,colors,select,finished):finished('A save is already in progress')
        dialog.save_requested.connect(save)
        dialog.open();return dialog

    def save_theme(self,identifier,name,colors,select=False,completion=None):
        return self.submit_theme_job('save',(identifier,name,colors),select,completion)

    def rename_theme(self):
        theme=self.themes.get(self.palette.currentData())
        if theme is None:return
        name,accepted=QInputDialog.getText(self,'Rename Music theme','Theme name',text=theme['name'])
        if accepted:self.submit_theme_job('rename',(theme['id'],name))

    def delete_theme(self):
        identifier=self.palette.currentData();theme=self.themes.get(identifier)
        if theme is None:return
        if QMessageBox.question(self,'Delete Music theme','Delete '+theme['name']+'?')==QMessageBox.StandardButton.Yes:
            self.submit_theme_job('delete',(identifier,))

    def submit_theme_job(self,operation,args,select=False,completion=None):
        if self.theme_jobs.busy or self.themes.blocked or self._closing:return False
        self.theme_jobs.submit(operation,*args)
        self._theme_completion=(select,completion);self.theme_notice.setText('Saving custom themes…')
        self.theme_timer.start();self.refresh_theme_buttons();return True

    def poll_theme_job(self):
        result=self.theme_jobs.take()
        if result is None:return
        identifier,error=result;select,completion=self._theme_completion;self._theme_completion=None
        self.theme_timer.stop()
        if not error:
            selected=identifier if select else self.palette.currentData()
            from PySide6.QtCore import QSignalBlocker
            blocker=QSignalBlocker(self.palette)
            self.palette.clear();self.palette.addItems(PALETTES)
            for theme in self.themes.list():self.palette.addItem('Custom · '+theme['name'],theme['id'])
            index=self.palette.findData(selected) if selected is not None else -1
            self.palette.setCurrentIndex(index if index>=0 else self.palette.findText(self.builtin_palette))
            del blocker
            self.palette.setToolTip(self.palette.currentText())
            self.album.preset_changed();self.queue_preferences()
        self.theme_notice.setText('Custom themes saved.' if not error else 'Custom themes not saved: '+error)
        self.refresh_theme_buttons()
        if completion is not None:completion(error)
        if self._theme_close_pending:self.close()

    def update_music_response(self,*args):
        self.runtime.set_response(self.profile.currentText(),self.sensitivity.value()/100,self.smoothing.value()/100)

    def update_music_adjustments(self,*args):
        self.c.adapter.set_adjustments(self.output_brightness.value()/100,self.output_saturation.value()/100)
        for name,widget in (('Brightness',self.output_brightness),('Saturation',self.output_saturation)):
            self.adjustment_labels[name].setText('Music-output '+name.lower()+f': {widget.value()}%')

    def reset_music_adjustments(self):
        assign(self.output_brightness,100);assign(self.output_saturation,100)
        self.update_music_adjustments();self.queue_preferences()

    def update_music_routing(self,*args):
        adapter=self.c.adapter
        if adapter.music_active and adapter.router is not None:
            adapter.router.configure_music(self.harmony.currentText(),self.separation.value()/100)

    def participation(self,key,enabled):self.c.adapter.set_participation(key,enabled);self.live_controls()

    def poll_music(self):
        frame,message,error,wanted=self.runtime.take()
        spectrum=self.runtime.take_spectrum()
        if self._closing:
            if not self.runtime.busy and self._cleanup_done:self.close()
            return
        if not error and wanted and frame is None and self.c.adapter.last_frame is None and self.runtime.started_at is not None and time.monotonic()-self.runtime.started_at>5:
            error='Audio startup timed out: no recorded audio frames from Windows default output loopback. Check the default output device and audio service.'
        if not wanted and not error and self.runtime.started_at is not None:
            error='Audio capture ended'+(' before the first measured frame' if self.c.adapter.last_frame is None else '')+' · '+message
        if error or (not wanted and (self.c.adapter.music_active or self.runtime.started_at is not None)):
            self.runtime.stop();self.c.adapter.stop_music();self.c.state.mode='Manual';self.c.changed.emit()
            self.music_status.setText(error or 'Audio stopped · manual control restored')
            self.reactor.reset_live()
        elif frame is not None and wanted:
            if not self.c.adapter.music_active:
                self.c.adapter.start_music(self.harmony.currentText(),self.separation.value()/100)
                self.c.state.mode='Music';self.c.changed.emit()
            self.c.adapter.apply_frame(frame)
            self.reactor.set_live_frame(frame)
            self.music_status.setText(('LIVE · capture running · silence' if frame.energy<=1e-6 else f'LIVE · RMS {frame.energy:.4f}')+' · '+self.runtime.capture_source+' · '+('BEAT · ' if frame.beat else '')+'RGB #'+''.join(f'{c:02X}' for c in frame.rgb))
        elif wanted and self.c.adapter.last_frame is None:self.music_status.setText(message)
        elif wanted and time.monotonic()-self.c.adapter.last_frame.timestamp>1:
            self.music_status.setText('Waiting for fresh audio data · Stop remains available')
            self.reactor.clear_live_frame()
        if spectrum is not None and wanted and self.c.adapter.music_active:self.reactor.set_spectrum_frame(spectrum)
        self.live_controls()
        if not self.runtime.busy and not self.c.adapter.music_active:
            if not error and self.music_status.text()=='Stopping audio…':self.music_status.setText('Audio stopped · manual control restored')
            self.music_timer.stop()

    def live_controls(self):
        super().live_controls()
        if not hasattr(self,'runtime'):return
        a=self.c.adapter;active=a.music_active
        self.refresh_theme_buttons()
        if hasattr(self,'album'):
            frame=a.last_frame
            if active and frame is not None and 0<=time.monotonic()-frame.timestamp<=1:
                rgb=a.music_colors.get('Corner')
                if rgb is not None:
                    status='Read-only · '+('connected' if a.connected else 'disconnected; no light required')
                    if not a.participation['Corner']:status+=' · Music participation off; calculated only'
                    self.album.update_light_preview(a.corner_music_rgb(rgb),frame.rgb,status)
            else:self.album.update_light_preview(None,None,'Waiting for fresh Music data.' if active else 'Start Music for measured output.')
        self.music_start.setEnabled(not self._closing and not self.runtime.busy)
        self.music_stop.setEnabled(not self._closing and (active or self.runtime.busy))
        self.master.modes['Music'].setEnabled(not self._closing)
        for widget in (self.profile,self.palette,self.sensitivity,self.smoothing,self.harmony,self.separation,self.output_brightness,self.output_saturation,self.adjustment_reset):widget.setEnabled(not self._closing)
        selected=self.c.state.selected_channel
        if a.owns(selected):
            self.inspector.tabs.widget(0).setEnabled(False)
            self.inspector.status.setText('LIVE · connected · Music owns color')
        for key,check in self.participate.items():check.setEnabled(not self._closing)
        self.refresh_manual_target()
        if hasattr(self.inspector,'live_music'):self.inspector.live_music.refresh()

    def tick(self):self.timer.stop()  # LIVE never invokes the synthetic animation engine.

    def closeEvent(self,event):
        if hasattr(self,'album'):self.album.shutdown()
        if hasattr(self,'runtime'):
            self.reactor.reset_live()
            self.runtime.stop();self.c.adapter.music_active=False
            if self.runtime.busy:self.music_timer.start()
            if self._cleanup_done and self.runtime.busy:event.ignore();return
        super().closeEvent(event)
        if hasattr(self,'music_timer') and self._cleanup_done and not self.runtime.busy:self.music_timer.stop()
        if hasattr(self,'theme_jobs') and self.theme_jobs.busy:
            self._theme_close_pending=True;self.theme_timer.start();event.ignore()
