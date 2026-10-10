"""Minimal LIVE status/connect affordances around the frozen Studio layout."""
from PySide6.QtCore import Qt,Slot,QSignalBlocker
from PySide6.QtWidgets import QDialog,QVBoxLayout,QDialogButtonBox,QLabel,QRadioButton,QHBoxLayout,QComboBox
from .device_families import FAMILIES,LEDBLE
from studio_ui.state import StudioState
from .app import StudioWindow
from .corner_adapter import CornerLampAdapter
from .widgets.common import button,text
from .widgets.controls import DeviceChannel
from .widgets.live_inspector import LiveSetupInspector,replace_tab


def choose_startup_mode():
    dialog=QDialog();dialog.setWindowTitle('Olive RGB Studio · Choose startup mode')
    from .theme import QSS
    dialog.setStyleSheet(QSS+'QDialog {background:#11121d;}');dialog.setMinimumWidth(480)
    layout=QVBoxLayout(dialog)
    label=QLabel('DEMO uses simulated devices and audio. LIVE enables LotusLamp / LEDBLE, Philips Hue and optional music capture.\nNeither choice automatically connects a lamp or starts audio.');label.setWordWrap(True);layout.addWidget(label)
    demo=QRadioButton('DEMO — no hardware access');live=QRadioButton('LIVE — LotusLamp / LEDBLE and Philips Hue');demo.setChecked(True)
    layout.addWidget(demo);layout.addWidget(live)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    return ('LIVE' if live.isChecked() else 'DEMO') if dialog.exec()==QDialog.DialogCode.Accepted else None


class LiveStudioWindow(StudioWindow):
    supported_modes=('Manual',)
    def __init__(self,workspace_path=None,worker_factory=None,adapter=None,preferences_path=None):
        state=adapter.state if adapter is not None else StudioState()
        adapter=adapter if adapter is not None else CornerLampAdapter(state,worker_factory=worker_factory)
        super().__init__(workspace_path=workspace_path,adapter=adapter,state=state,preferences_path=preferences_path)
        adapter.setParent(self);self._closing=False;self._cleanup_done=False
        self.setWindowTitle('Olive RGB Studio · LIVE LotusLamp / LEDBLE · Manual only')
        self.mode_badge.setText('LIVE')
        self.demo.setText('Bluetooth only')
        for label in self.channel_panel.findChildren(QLabel):
            if label.text()=='DEMO':label.setText('LIVE')
        self.connect_button=button('Connect Corner Lamp',self.connect_corner)
        self.disconnect_button=button('Disconnect',self.disconnect_corner)
        self.family_selector=QComboBox();self.family_selector.addItems(FAMILIES)
        self.family_selector.setAccessibleName('Bluetooth controller family')
        self.family_selector.setToolTip('Selecting disconnects the current controller. Press Connect to connect the selected family.')
        self.family_selector.setCurrentText(self.preferences['controller']['family'])
        adapter.select_family(self.family_selector.currentText())
        self.live_status=text(adapter.message,'muted');self.live_status.setWordWrap(True)
        live_row=QHBoxLayout();live_row.addWidget(self.live_status,1);live_row.addWidget(self.family_selector);live_row.addWidget(self.connect_button);live_row.addWidget(self.disconnect_button)
        self.centralWidget().layout().insertLayout(2,live_row)
        adapter.connection_changed.connect(self.connection_update)
        adapter.finished.connect(self.cleanup_finished)
        blocker=QSignalBlocker(self.inspector.device)
        self.inspector.device.clear()
        for label,key in (('Both Lights','Both'),('Corner Lamp','Corner'),('Philips Hue','Hue')):self.inspector.device.addItem(label,key)
        self.inspector.device.setCurrentIndex(self.inspector.device.findData(self.c.state.selected_channel));del blocker
        self.inspector.device.setAccessibleName('LIVE lighting target')
        self.inspector.target_notice=text('','muted');self.inspector.target_notice.setWordWrap(True)
        self.inspector.box.insertWidget(3,self.inspector.target_notice)
        self.inspector.live_setup=LiveSetupInspector(self)
        replace_tab(self.inspector,2,self.inspector.live_setup,'Setup')
        self.c.changed.connect(self.live_controls)
        self.family_selector.currentTextChanged.connect(self.select_family)
        self.update_family_labels()
        self.live_controls()
    def select_family(self,family):
        self.c.adapter.select_family(family);self.live_status.setText(self.c.adapter.message)
        self.update_family_labels();self.c.changed.emit();self.queue_preferences()
    def update_family_labels(self):
        strip=self.c.adapter.session.family==LEDBLE;name='LEDBLE Strip' if strip else 'Corner Lamp'
        self.c.state.channels['Corner'].name=name;self.connect_button.setText('Connect '+name)
        for row in self.findChildren(DeviceChannel):
            if row.key=='Corner':row.select.setText(name)
        index=self.inspector.device.findData('Corner')
        if index>=0:
            blocker=QSignalBlocker(self.inspector.device);self.inspector.device.setItemText(index,name);del blocker
    def connect_corner(self):self.c.adapter.connect_corner();self.live_controls()
    def disconnect_corner(self):self.c.adapter.disconnect_corner();self.live_controls()
    @Slot(object)
    def connection_update(self,event):
        self.live_status.setText(event.message);self.live_controls()
    def live_controls(self):
        if not hasattr(self,'connect_button'):return
        a=self.c.adapter;enabled=a.connected and not self._closing
        self.family_selector.setEnabled(not self._closing and not a.session.closed)
        self.connect_button.setEnabled(not self._closing and not a.session.wanted and not a.session.closed)
        self.disconnect_button.setEnabled(not self._closing and (a.session.wanted or a.connected))
        self.master.power.setEnabled(enabled and a.software_power);self.master.level.setEnabled(enabled)
        # Decide availability once for the complete window. Temporarily disabling
        # a focused mode moves Qt focus and can auto-scroll the whole dashboard.
        for name,b in self.master.modes.items():b.setEnabled(name in self.supported_modes and not self._closing)
        for row in self.findChildren(DeviceChannel):
            corner=row.key=='Corner';row.power.setEnabled(enabled and corner and a.software_power);row.level.setEnabled(enabled and corner);row.follow.setEnabled(enabled and corner)
            row.select.setToolTip('LIVE '+self.c.state.channels['Corner'].name if corner else 'Philips Hue — not integrated in LIVE')
            row.dot.setStyleSheet('background:'+('#46dc97' if enabled else '#777386')+';border-radius:6px;' if corner else 'background:#777386;border-radius:6px;')
        corner=self.c.state.selected_channel=='Corner'
        self.inspector.tabs.setEnabled(not self._closing)
        self.inspector.tabs.widget(0).setEnabled(enabled and corner)
        self.inspector.power.setEnabled(enabled and corner and a.software_power);self.inspector.follow.setEnabled(enabled and corner);self.inspector.brightness.setEnabled(enabled and corner)
        self.inspector.status.setText(('LIVE · '+a.status) if corner else 'NOT INTEGRATED · no Hue hardware')
        self.inspector.power.setToolTip('Software power: OFF sends RGB black; ON restores the selected color. Not a hardware power command.')
        self.master.power.setToolTip('Software power through RGB black, matching the existing application.')
        from .app import ScenePanel
        for panel in self.findChildren(ScenePanel):
            panel.setEnabled(False);panel.setToolTip('DEMO-only scenes; unavailable in LIVE')
            panel.status.setText('Unavailable in LIVE · use DEMO for scenes')
        self.pause.setEnabled(False);self.pause.setText('DEMO only')
        self.inspector.tabs.setTabEnabled(1,hasattr(self.inspector,'live_music'))
        self.inspector.tabs.setTabEnabled(2,True)
        self.inspector.tabs.setTabToolTip(1,'LIVE music routing' if hasattr(self.inspector,'live_music') else 'Music requires the LIVE Music window')
        self.inspector.tabs.setTabToolTip(2,'Selected device connection and capabilities')
        self.inspector.live_setup.refresh()
        self.update_inspector_links()
        self.refresh_manual_target()
    def refresh_manual_target(self):
        c=self.c;ins=self.inspector;keys=c.target_devices()
        ins.tabs.widget(0).setEnabled(not self._closing and any(not c.target_reason(key,'color') for key in keys))
        ins.power.setEnabled(not self._closing and any(not c.target_reason(key,'power') for key in keys))
        ins.brightness.setEnabled(not self._closing and any(not c.target_reason(key,'brightness') for key in keys))
        if len(keys)>1:ins.follow.setEnabled(False)
        ins.follow.setToolTip('Follow Master remains independent; select one device to change it')
        details=[key+': '+(c.target_reason(key,'color') or 'manual color available') for key in keys]
        if len(keys)>1:
            details.append('Displayed color/brightness use '+c.manual_reference()+'. Edits apply to eligible targets; other settings stay independent.')
            details.extend(f'{key}: brightness {c.state.channels[key].brightness:.0%}, power '+('ON' if c.state.channels[key].power else 'OFF') for key in keys)
        if c.manual_feedback:details.append('Last action: '+c.manual_feedback)
        ins.target_notice.setText('\n'.join(details))
    def closeEvent(self,event):
        if self._cleanup_done:return super().closeEvent(event)
        event.ignore()
        if self._closing:return
        self._closing=True;self.timer.stop();self.c.transition=None
        self.live_status.setText('Closing · cancelling pending work and disconnecting Bluetooth controller…')
        self.live_controls();self.c.adapter.close()
    @Slot()
    def cleanup_finished(self):
        self._cleanup_done=True
        if self._closing:self.close()
        else:self.live_controls()
