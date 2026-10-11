import time
from PySide6.QtCore import Qt,QTimer,QSize,Slot,QSignalBlocker
from PySide6.QtGui import QKeySequence,QShortcut
from PySide6.QtWidgets import QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,QSplitter,QStackedWidget,QFrame,QComboBox,QLabel,QDoubleSpinBox
from studio_ui.state import NAVIGATION,SCENES
from .preferences import PreferencesStore, restore, snapshot, default_path as preferences_path_default
from .theme import QSS,FRAME_MS
from .controller import StudioController
from .workspace import Workspace, WorkspaceStore, WorkspaceSplitter, visible_geometry, default_path
from .widgets.icons import icon
from .backend_adapter import AudioMeters
from .widgets.common import Panel,text,button,scroll,assign
from .widgets.controls import MasterBus,DeviceChannel
from .widgets.audio_reactor import AudioReactor
from .widgets.scene_pad import ScenePad
from .widgets.inspector import Inspector


class ScenePanel(Panel):
    def __init__(self,c):
        super().__init__('SCENE LAUNCH PADS');self.c=c;self.columns=0;self._visible_cards=None
        self.favorite=button('Favorites',lambda b:c.set('favorites_only',b),True);self.favorite.setIcon(icon('Favorite'));self.header.addWidget(self.favorite)
        if getattr(c.adapter,'live',False):
            self.duration=QDoubleSpinBox();self.duration.setRange(0,5);self.duration.setSingleStep(.1);self.duration.setDecimals(1);self.duration.setSuffix(' s');self.duration.setAccessibleName('Scene transition duration');self.duration.setToolTip('Scene fade duration · 0 seconds for instant')
            self.curve=QComboBox();self.curve.addItems(('Smooth','Linear','Instant'));self.curve.setAccessibleName('Scene transition curve')
            self.header.addWidget(self.duration);self.header.addWidget(self.curve)
            self.duration.valueChanged.connect(lambda value:c.set_transition(value,self.curve.currentText()))
            self.curve.currentTextChanged.connect(lambda curve:c.set_transition(self.duration.value(),curve))
        self.grid=QGridLayout();self.grid.setSpacing(10);self.box.addLayout(self.grid)
        self.cards=[ScenePad(name,c) for name in SCENES]
        self.status=text('','muted');self.status.setWordWrap(True)
        from .widgets.light_preview import VirtualLightPreview
        self.preview=VirtualLightPreview(compact=True)
        footer=QHBoxLayout();footer.addWidget(self.status,1);footer.addWidget(self.preview,1);self.box.addLayout(footer)
        self.status.setFixedHeight(44)
        c.changed.connect(self.refresh);c.output_changed.connect(self.progress);self.refresh()
    def resizeEvent(self,event):super().resizeEvent(event);self.refresh()
    def refresh(self):
        assign(self.favorite,self.c.state.favorites_only)
        if hasattr(self,'duration'):
            with QSignalBlocker(self.duration):self.duration.setValue(self.c.state.transition_seconds)
            with QSignalBlocker(self.curve):self.curve.setCurrentText(self.c.state.transition_curve)
        columns=4 if self.width()>=650 else 2
        visible=[card for card in self.cards if not self.c.state.favorites_only or card.name in self.c.state.favorites]
        if columns!=self.columns or visible!=self._visible_cards:
            for card in self.cards:self.grid.removeWidget(card);card.setVisible(card in visible)
            for i,card in enumerate(visible):self.grid.addWidget(card,i//columns,i%columns)
            self._visible_cards=visible
        for col in range(4):self.grid.setColumnStretch(col,1 if col<columns else 0)
        self.columns=columns;self.progress()
    def progress(self):
        c=self.c
        if getattr(c.adapter,'live',False):
            if not hasattr(c,'scene_request'):
                self.status.setText('Unavailable in LIVE · use the complete Studio window');return
            self.status.setText(c.scene_status if c.scene_active or c.scene_status.startswith(('Waiting','Scene failed','Select')) else 'Static scene inactive · '+c.scene_status)
            self.status.setToolTip(self.status.text())
            rgb=tuple(int(c.state.channels['Corner'].color[i:i+2],16) for i in (1,3,5))
            output=c.adapter.corner_music_rgb(rgb) if hasattr(c.adapter,'corner_music_rgb') else None
            self.preview.update_light_preview(output,rgb,'Read-only static output · lights optional')
            self.preview.light_readout.setToolTip(self.preview.light_readout.text())
            return
        channel=c.state.channels['Corner'];rgb=tuple(int(c.display_colors['Corner'][i:i+2],16) for i in (1,3,5))
        scale=channel.brightness*(c.state.master_brightness if channel.follow else 1.)
        output=tuple(round(v*scale) for v in rgb) if channel.power and (c.state.master_power or not channel.follow) else (0,0,0)
        self.preview.update_light_preview(output,rgb,'DEMO static output')
        if c.scene_status.startswith('Scene failed'):
            self.status.setText(c.scene_status);return
        self.status.setText(f'{c.state.scene} · '+(f'Transition {c.transition_progress:.0%}' if c.transition else f'{c.state.transition_seconds:g}s {c.state.transition_curve.lower()} · mock output'))


class StudioWindow(QMainWindow):
    def __init__(self,workspace_path=None,adapter=None,state=None,preferences_path=None):
        super().__init__();self.setWindowTitle('Olive RGB Studio · Qt Preview · DEMO');self.resize(1440,900);self.setMinimumSize(800,600)
        self.store=WorkspaceStore(workspace_path);self.workspace=self.store.load();self._restoring=True
        self.setStyleSheet(QSS);self.c=StudioController(parent=self,adapter=adapter,state=state);self.last_tick=time.monotonic()
        self.preferences_store=PreferencesStore(preferences_path)
        self.preferences_mode='live' if getattr(self.c.adapter,'live',False) else 'demo'
        self.preferences=self.preferences_store.load(self.preferences_mode)
        if preferences_path is not None:
            restore(self.c.state,self.preferences)
            self.c.display_colors={k:v.color for k,v in self.c.state.channels.items()}
        self.preferences_timer=QTimer(self);self.preferences_timer.setSingleShot(True);self.preferences_timer.setInterval(200)
        self.preferences_timer.timeout.connect(self.save_preferences)
        shell=QWidget();shell.setObjectName('shell');self.setCentralWidget(shell);root=QVBoxLayout(shell);root.setContentsMargins(12,12,12,12)
        header=QHBoxLayout();brand=QLabel();brand.setPixmap(icon('Logo').pixmap(QSize(28,28)));brand.setFixedSize(40,40);brand.setAlignment(Qt.AlignmentFlag.AlignCenter);brand.setObjectName('brandMark');header.addWidget(brand);header.addWidget(text('OLIVE <span style="color:#ef72eb">RGB</span>','title'));header.addWidget(text('MUSIC STUDIO','muted'));header.addStretch();self.mode_badge=text('DEMO · QT PREVIEW','demo');header.addWidget(self.mode_badge);root.addLayout(header)
        toolbar=QHBoxLayout();self.workspace_toolbar=toolbar;toolbar.addWidget(text('Workspace','muted'))
        self.preset=QComboBox();self.preset.addItems(['Studio','Music','Compact']);self.preset.setAccessibleName('Workspace preset');toolbar.addWidget(self.preset)
        self.sidebar_toggle=button('Sidebar',lambda:self.toggle_sidebar(),True);self.sidebar_toggle.setToolTip('Expand/collapse sidebar · Ctrl+B');toolbar.addWidget(self.sidebar_toggle)
        self.inspector_toggle=button('Inspector',lambda:self.toggle_inspector(),True);self.inspector_toggle.setToolTip('Show/hide inspector · Ctrl+I');toolbar.addWidget(self.inspector_toggle)
        toolbar.addStretch();self.reset_button=button('Reset layout',self.reset_workspace);toolbar.addWidget(self.reset_button);root.addLayout(toolbar)
        self.workspace_notice=text(self.store.error,'muted');self.workspace_notice.setWordWrap(True);self.workspace_notice.setVisible(bool(self.store.error));root.addWidget(self.workspace_notice)
        QShortcut(QKeySequence('Ctrl+B'),self,activated=self.toggle_sidebar);QShortcut(QKeySequence('Ctrl+I'),self,activated=self.toggle_inspector)
        self.preferences_notice=text(self.preferences_store.error,'muted');self.preferences_notice.setWordWrap(True)
        self.preferences_notice.setVisible(bool(self.preferences_store.error));root.addWidget(self.preferences_notice)
        self.inspector_links={};self.page_notes={}
        body=QHBoxLayout();body.setSpacing(12);root.addLayout(body,1)
        self.sidebar=QFrame();self.sidebar.setObjectName('sidebar');nav=QVBoxLayout(self.sidebar);nav.setContentsMargins(6,12,6,10)
        self.nav={}
        for i,page in enumerate(NAVIGATION):
            b=button(page,lambda checked=False,page=page:self.c.navigate(page),True);b.setObjectName('nav');b.setMinimumHeight(43);nav.addWidget(b);self.nav[page]=b;b.setIcon(icon(page));b.setIconSize(QSize(22,22))
            QShortcut(QKeySequence(f'Alt+{i+1}'),self,activated=lambda page=page:self.c.navigate(page))
        nav.addStretch();self.demo=text('Mock devices','muted');nav.addWidget(self.demo);body.addWidget(self.sidebar)
        self.splitter=WorkspaceSplitter(Qt.Orientation.Horizontal);self.splitter.setHandleWidth(8);self.splitter.setChildrenCollapsible(False);body.addWidget(self.splitter,1)
        self.pages=QStackedWidget();self.pages.setMinimumWidth(345);self.splitter.addWidget(self.pages)
        dashboard=QWidget();db=QVBoxLayout(dashboard);self.dashboard_layout=db;db.setContentsMargins(0,0,4,0);db.setSpacing(12)
        self.master=MasterBus(self.c);db.addWidget(self.master)
        audio=Panel('AUDIO REACTOR');self.audio_panel=audio;self.pause=button('Pause',lambda:self.c.set('playing',not self.c.state.playing));audio.header.addWidget(self.pause)
        audio.header.addWidget(text('DEMO','demo'))
        self.reactor=AudioReactor();audio.box.addWidget(self.reactor);db.addWidget(audio)
        self.scenes=ScenePanel(self.c);db.addWidget(self.scenes)
        channels=Panel('DEVICE CHANNELS','DEMO');self.channel_panel=channels;self.channels={}
        for key in self.c.state.channels:self.channels[key]=DeviceChannel(self.c,key);channels.box.addWidget(self.channels[key])
        db.addWidget(channels);db.addStretch();self.pages.addWidget(scroll(dashboard))
        for page in NAVIGATION[1:]:
            panel=Panel(page.upper())
            if page=='Scenes':panel.box.addWidget(ScenePanel(self.c))
            elif page=='Devices':
                for key in self.c.state.channels:panel.box.addWidget(DeviceChannel(self.c,key))
            else:
                note=text(f'{page}: DEMO-only preview controls. Screen capture is unavailable. Qt lighting and music preferences save separately from Tkinter settings; launch stays idle.','muted');self.page_notes[page]=note;note.setWordWrap(True);panel.box.addWidget(note)
                target='Music' if page=='Music' else 'Setup'
                link=button('Open '+target+' inspector',lambda checked=False,target=target:self.open_tab(target))
                self.inspector_links[page]=(target,link);panel.box.addWidget(link)
            panel.box.addStretch();self.pages.addWidget(scroll(panel))
        from .widgets.appearance_settings import AppearanceSettings
        self.appearance_settings=AppearanceSettings(self)
        self.pages.widget(NAVIGATION.index('Settings')).widget().box.insertWidget(1,self.appearance_settings)
        self.page_notes['Settings'].setText('Interface themes and status history work in DEMO and LIVE. Qt preferences are separate from original settings; launch stays idle.')
        self.inspector=Inspector(self.c);self.inspector.setMinimumWidth(260);self.inspector_scroll=scroll(self.inspector);self.inspector_scroll.setMinimumWidth(280);self.splitter.addWidget(self.inspector_scroll)
        self.splitter.setSizes([1000,330]);self.splitter.setStretchFactor(0,1);self.splitter.setStretchFactor(1,0)
        self.c.adapter.device_status.connect(self.inspector.receive_status, Qt.ConnectionType.QueuedConnection)
        self.c.adapter.audio_meters.connect(self.receive_meters, Qt.ConnectionType.QueuedConnection)
        self.c.adapter.discover_devices()
        self.last_meters=None
        self.timer=QTimer(self);self.timer.setInterval(FRAME_MS);self.timer.timeout.connect(self.tick)
        self.c.changed.connect(self.sync);self.c.output_changed.connect(self.refresh_timer)
        self.pages.widget(0).verticalScrollBar().valueChanged.connect(self.refresh_timer)
        self.preset.currentTextChanged.connect(self.apply_preset)
        self.splitter.splitterMoved.connect(self.remember_splitter)
        self.apply_preset(self.workspace.preset,restoring=True)
        self.setGeometry(visible_geometry(self.workspace.geometry)) if workspace_path is not None else None
        self.update_sidebar();self.inspector_scroll.setVisible(not self.workspace.inspector_collapsed)
        self.splitter.setSizes(list(self.workspace.splitter_sizes));self._restoring=False
        self.sync()
        self.c.changed.connect(self.queue_preferences);self.c.output_changed.connect(self.queue_preferences)
    def queue_preferences(self,*args):
        if self.preferences_store.path is not None:self.preferences_timer.start()
    def music_preferences(self):
        music=dict(self.preferences['music'])
        if self.preferences_mode=='demo':
            for key in ('sensitivity','smoothing','relationship','separation'):music[key]=getattr(self.c.state,key)
        return music
    def save_preferences(self):
        self.preferences_timer.stop()
        values=snapshot(self.c.state,self.music_preferences())
        values['appearance']=dict(self.preferences['appearance'])
        if self.preferences_mode=='live':
            from .device_families import identity_for
            family=self.c.adapter.session.family
            values['controller']={'family':family,'identity':identity_for(family)}
            values['hue']=self.hue_preferences() if hasattr(self,'hue_preferences') else self.preferences['hue']
            values['screen']=self.screen_preferences() if hasattr(self,'screen_preferences') else self.preferences['screen']
        self.preferences_store.save(self.preferences_mode,values)
        self.preferences_notice.setText(self.preferences_store.error)
        self.preferences_notice.setVisible(bool(self.preferences_store.error))
    def update_inspector_links(self):
        for target,link in self.inspector_links.values():
            index=('Color','Music','Setup').index(target)
            enabled=self.inspector.tabs.isEnabled() and self.inspector.tabs.isTabEnabled(index)
            link.setEnabled(enabled)
            link.setToolTip('DEMO-only inspector' if not enabled else 'Open '+target+' inspector')
    def open_tab(self,tab):
        index=('Color','Music','Setup').index(tab)
        if not self.inspector.tabs.isEnabled() or not self.inspector.tabs.isTabEnabled(index):return False
        if self.workspace.inspector_collapsed:self.toggle_inspector()
        self.c.state.select_inspector(tab);self.c.changed.emit();return True
    def sync(self):
        s=self.c.state;index=NAVIGATION.index(s.page)
        if self.pages.currentIndex()!=index:
            # QStackedWidget transfers focus when hiding/showing a page. Qt's
            # focus visibility handling must not change the dashboard viewport.
            bar=self.pages.widget(0).verticalScrollBar();position=bar.value()
            self.pages.setCurrentIndex(index);bar.setValue(position)
        for page,b in self.nav.items():assign(b,page==s.page)
        self.pause.setText('Pause' if s.playing else 'Play')
        if not s.motion:self.c.advance(time.monotonic())
        self.refresh_timer()
    def resizeEvent(self,event):
        super().resizeEvent(event)
        if not hasattr(self,'sidebar'):return
        self.update_sidebar()
    def update_sidebar(self):
        compact=self.workspace.sidebar_collapsed or self.width()<1100
        self.sidebar.setFixedWidth(56 if compact else 140);self.demo.setVisible(not compact)
        for page,b in self.nav.items():b.setText('' if compact else page)
        assign(self.sidebar_toggle,not self.workspace.sidebar_collapsed)
        assign(self.inspector_toggle,not self.workspace.inspector_collapsed)
    def toggle_sidebar(self):
        self.workspace.sidebar_collapsed=not self.workspace.sidebar_collapsed;self.update_sidebar()
    def toggle_inspector(self):
        if not self.workspace.inspector_collapsed:self.remember_splitter()
        self.workspace.inspector_collapsed=not self.workspace.inspector_collapsed
        self.inspector_scroll.setVisible(not self.workspace.inspector_collapsed)
        if not self.workspace.inspector_collapsed:self.splitter.setSizes(list(self.workspace.splitter_sizes))
        self.update_sidebar()
    def remember_splitter(self,*args):
        if not self._restoring and not self.workspace.inspector_collapsed:
            sizes=self.splitter.sizes()
            if all(x>0 for x in sizes):self.workspace.splitter_sizes=tuple(sizes)
    def apply_preset(self,name,restoring=False):
        self.workspace.preset=name;assign(self.preset,name)
        music=name=='Music';compact=name=='Compact'
        self.reactor.setMinimumHeight(300 if music else 130 if compact else 165)
        for card in self.scenes.cards:card.setFixedHeight(84 if music or compact else 92)
        panels=[self.master,self.audio_panel,self.scenes,self.channel_panel]
        for panel in panels:self.dashboard_layout.removeWidget(panel)
        order=[self.master,self.channel_panel,self.audio_panel,self.scenes] if compact else [self.master,self.audio_panel,self.channel_panel,self.scenes] if music else panels
        for i,panel in enumerate(order):self.dashboard_layout.insertWidget(i,panel)
        self.dashboard_layout.setSpacing(12 if music else 8)
        if not restoring:
            self.workspace.sidebar_collapsed=compact;self.workspace.inspector_collapsed=music or compact
            self.workspace.splitter_sizes=(900,330)
            self.inspector_scroll.setVisible(not self.workspace.inspector_collapsed)
            self.splitter.setSizes(list(self.workspace.splitter_sizes))
        self.update_sidebar();self.refresh_timer()
    def reset_workspace(self):
        self.workspace=Workspace();self.apply_preset('Studio');self.setGeometry(visible_geometry(None));self.save_workspace()
    def save_workspace(self):
        self.remember_splitter();r=self.normalGeometry() if self.isMaximized() else self.geometry()
        self.workspace.geometry=(r.x(),r.y(),r.width(),r.height())
        okay=self.store.save(self.workspace)
        self.workspace_notice.setText(self.store.error);self.workspace_notice.setVisible(bool(self.store.error))
        return okay
    @Slot(object)
    def receive_meters(self,meters):
        if not self.c.adapter.closed:
            self.last_meters=meters
            self.reactor.meter_values=[meters.bass,meters.mids,meters.treble,meters.level]
            if self.reactor.isVisible():self.reactor.update()

    def refresh_timer(self):
        if not hasattr(self,"timer"):return
        s=self.c.state
        animating=(s.motion and s.playing and s.master_power and s.mode=="Music" and s.page=="Studio" and not self.reactor.visibleRegion().isEmpty())
        needed=self.isVisible() and not self.isMinimized() and not self.c.adapter.closed and (animating or self.c.transition is not None)
        if needed and not self.timer.isActive():self.last_tick=time.monotonic();self.timer.start()
        elif not needed:self.timer.stop()

    def changeEvent(self,event):
        super().changeEvent(event);self.refresh_timer()

    def tick(self):
        now=time.monotonic();dt=now-self.last_tick;self.last_tick=now;self.c.advance(now)
        s=self.c.state
        if s.motion and s.playing and s.master_power and s.mode=='Music' and not self.isMinimized() and not self.reactor.visibleRegion().isEmpty():
            self.reactor.advance(dt,playing=True,intensity=s.master_brightness)
            bands=[sum(self.reactor.levels[i:i+24])/24 for i in (0,24,48)]
            self.c.adapter.publish_demo_meters(AudioMeters(*bands,sum(bands)/3))
        self.refresh_timer()
    def showEvent(self,event):super().showEvent(event);self.last_tick=time.monotonic();self.timer.start()
    def hideEvent(self,event):self.timer.stop();super().hideEvent(event)
    def closeEvent(self,event):self.appearance_settings.timer.stop();self.save_preferences();self.save_workspace();self.timer.stop();self.c.transition=None;self.c.adapter.close();super().closeEvent(event)


def main():
    app=QApplication.instance() or QApplication([]);app.setStyle('Fusion')
    from .live_window import choose_startup_mode,LiveStudioWindow
    mode=choose_startup_mode()
    if mode is None:return 0
    if mode=='LIVE':
        from .screen_window import ScreenLiveWindow
        window=ScreenLiveWindow(workspace_path=default_path(),preferences_path=preferences_path_default())
    else:window=StudioWindow(workspace_path=default_path(),preferences_path=preferences_path_default())
    window.show();return app.exec()
