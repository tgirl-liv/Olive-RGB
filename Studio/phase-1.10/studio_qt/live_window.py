"""Minimal LIVE status/connect affordances around the frozen Studio layout."""
from PySide6.QtCore import Qt,Slot
from PySide6.QtWidgets import QDialog,QVBoxLayout,QDialogButtonBox,QLabel,QRadioButton,QHBoxLayout
from studio_ui.state import StudioState
from .app import StudioWindow
from .corner_adapter import CornerLampAdapter
from .widgets.common import button,text
from .widgets.controls import DeviceChannel


def choose_startup_mode():
    dialog=QDialog();dialog.setWindowTitle('Olive RGB Studio · Choose startup mode')
    from .theme import QSS
    dialog.setStyleSheet(QSS+'QDialog {background:#11121d;}');dialog.setMinimumWidth(480)
    layout=QVBoxLayout(dialog)
    label=QLabel('DEMO uses simulated devices and audio. LIVE enables Corner Lamp, Philips Hue and optional music capture.\nNeither choice automatically connects a lamp or starts audio.');label.setWordWrap(True);layout.addWidget(label)
    demo=QRadioButton('DEMO — no hardware access');live=QRadioButton('LIVE — Corner Lamp and Philips Hue');demo.setChecked(True)
    layout.addWidget(demo);layout.addWidget(live)
    buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Ok|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(dialog.accept);buttons.rejected.connect(dialog.reject);layout.addWidget(buttons)
    return ('LIVE' if live.isChecked() else 'DEMO') if dialog.exec()==QDialog.DialogCode.Accepted else None


class LiveStudioWindow(StudioWindow):
    def __init__(self,workspace_path=None,worker_factory=None,adapter=None):
        state=adapter.state if adapter is not None else StudioState()
        adapter=adapter if adapter is not None else CornerLampAdapter(state,worker_factory=worker_factory)
        super().__init__(workspace_path=workspace_path,adapter=adapter,state=state)
        adapter.setParent(self);self._closing=False;self._cleanup_done=False
        self.setWindowTitle('Olive RGB Studio · LIVE Corner Lamp · Manual only')
        self.mode_badge.setText('LIVE · CORNER ONLY')
        self.demo.setText('Corner only')
        for label in self.channel_panel.findChildren(QLabel):
            if label.text()=='DEMO':label.setText('LIVE · CORNER ONLY')
        self.connect_button=button('Connect Corner Lamp',self.connect_corner)
        self.disconnect_button=button('Disconnect',self.disconnect_corner)
        self.live_status=text(adapter.message,'muted');self.live_status.setWordWrap(True)
        live_row=QHBoxLayout();live_row.addWidget(self.live_status,1);live_row.addWidget(self.connect_button);live_row.addWidget(self.disconnect_button)
        self.centralWidget().layout().insertLayout(2,live_row)
        adapter.connection_changed.connect(self.connection_update)
        adapter.finished.connect(self.cleanup_finished)
        self.c.changed.connect(self.live_controls)
        self.live_controls()
    def connect_corner(self):self.c.adapter.connect_corner();self.live_controls()
    def disconnect_corner(self):self.c.adapter.disconnect_corner();self.live_controls()
    @Slot(object)
    def connection_update(self,event):
        self.live_status.setText(event.message);self.live_controls()
    def live_controls(self):
        if not hasattr(self,'connect_button'):return
        a=self.c.adapter;enabled=a.connected and not self._closing
        self.connect_button.setEnabled(not self._closing and not a.session.wanted and not a.session.closed)
        self.disconnect_button.setEnabled(not self._closing and (a.session.wanted or a.connected))
        self.master.power.setEnabled(enabled and a.software_power);self.master.level.setEnabled(enabled)
        for name,b in self.master.modes.items():b.setEnabled(name=='Manual' and not self._closing)
        for row in self.findChildren(DeviceChannel):
            corner=row.key=='Corner';row.power.setEnabled(enabled and corner and a.software_power);row.level.setEnabled(enabled and corner);row.follow.setEnabled(enabled and corner)
            row.select.setToolTip('LIVE Corner Lamp' if corner else 'Philips Hue — not integrated in LIVE')
            row.dot.setStyleSheet('background:'+('#46dc97' if enabled else '#777386')+';border-radius:6px;' if corner else 'background:#777386;border-radius:6px;')
        corner=self.c.state.selected_channel=='Corner'
        self.inspector.tabs.setEnabled(enabled and corner)
        self.inspector.power.setEnabled(enabled and corner and a.software_power);self.inspector.follow.setEnabled(enabled and corner);self.inspector.brightness.setEnabled(enabled and corner)
        self.inspector.status.setText(('LIVE · '+a.status) if corner else 'NOT INTEGRATED · no Hue hardware')
        self.inspector.power.setToolTip('Software power: OFF sends RGB black; ON restores the selected color. Not a hardware power command.')
        self.master.power.setToolTip('Software power through RGB black, matching the existing application.')
        from .app import ScenePanel
        for panel in self.findChildren(ScenePanel):
            panel.setEnabled(False);panel.setToolTip('Scene lighting is unavailable in LIVE Phase 1.8')
            panel.status.setText('Unavailable in LIVE · use DEMO for scenes')
        self.pause.setEnabled(False);self.pause.setText('DEMO only')
    def closeEvent(self,event):
        if self._cleanup_done:return super().closeEvent(event)
        event.ignore()
        if self._closing:return
        self._closing=True;self.timer.stop();self.c.transition=None
        self.live_status.setText('Closing · cancelling pending work and disconnecting Corner Lamp…')
        self.live_controls();self.c.adapter.close()
    @Slot()
    def cleanup_finished(self):
        self._cleanup_done=True
        if self._closing:self.close()
        else:self.live_controls()
