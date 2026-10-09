"""Phase 1.9 LIVE connection/status controls around the approved dashboard."""
from PySide6.QtWidgets import QHBoxLayout, QLabel
from .live_window import LiveStudioWindow
from .dual_adapter import DualLightingAdapter
from .widgets.common import button, text
from .widgets.controls import DeviceChannel


class DualLiveWindow(LiveStudioWindow):
    def __init__(self, workspace_path=None, worker_factory=None, hue_factory=None, hue_identity=None, adapter=None,preferences_path=None):
        adapter = adapter if adapter is not None else DualLightingAdapter(worker_factory=worker_factory, hue_factory=hue_factory, hue_identity=hue_identity)
        super().__init__(workspace_path=workspace_path, adapter=adapter,preferences_path=preferences_path)
        self.setWindowTitle('Olive RGB Studio · LIVE Corner + Hue · Manual only')
        self.mode_badge.setText('LIVE · MANUAL')
        self.demo.setText('Corner + Hue')
        for label in self.channel_panel.findChildren(QLabel):
            if label.text() == 'LIVE · CORNER ONLY':label.setText('LIVE')
        self.hue_connect = button('Connect Hue', self.connect_hue)
        self.hue_connect.setAccessibleName('Connect Philips Hue')
        self.hue_disconnect = button('Disconnect Hue', self.disconnect_hue)
        self.hue_status = text('Hue · disconnected · Tv lamp', 'muted');self.hue_status.setWordWrap(True)
        row = QHBoxLayout();row.addWidget(self.hue_status, 1);row.addWidget(self.hue_connect);row.addWidget(self.hue_disconnect)
        self.centralWidget().layout().insertLayout(3, row)
        self.hue_note = text('', 'muted');self.hue_note.setWordWrap(True)
        self.inspector.box.insertWidget(4, self.hue_note)
        adapter.hue_changed.connect(self.hue_update)
        adapter.state_observed.connect(self.c.changed)
        self.c.output_changed.connect(self.live_controls)
        adapter.finished.connect(self.live_controls)
        self.live_controls()

    def connect_hue(self):self.c.adapter.connect_hue();self.live_controls()
    def disconnect_hue(self):self.c.adapter.disconnect_hue();self.live_controls()
    def closeEvent(self, event):
        super().closeEvent(event)
        if self._closing and not self._cleanup_done:
            self.live_status.setText('Closing · cancelling pending work and disconnecting both devices…')
    def hue_update(self, event):
        a = self.c.adapter
        identity = a.hue_identity
        message = a.hue_error if a.hue_status == 'error' else f"{identity.get('name', 'Tv lamp')} · {identity.get('address_hint', 'not connected')}"
        self.hue_status.setText(f'Hue · {a.hue_status} · {message}')
        self.live_controls()

    def live_controls(self):
        super().live_controls()
        if not hasattr(self, 'hue_connect'):return
        a = self.c.adapter
        hue = a.hue_connected and not self._closing
        corner = a.connected and not self._closing
        self.hue_connect.setEnabled(not self._closing and not a.hue.wanted and not a.hue.closed)
        self.hue_disconnect.setEnabled(not self._closing and (a.hue.wanted or a.hue_connected))
        self.master.power.setEnabled(corner or (hue and a.hue_caps.get('power', False)))
        self.master.level.setEnabled(corner or (hue and a.hue_caps.get('brightness', False)))
        self.master.power.setToolTip('Following devices: Corner uses RGB black; Hue uses its verified power control.')
        for row in self.findChildren(DeviceChannel):
            if row.key != 'Hue':continue
            row.select.setToolTip('LIVE Philips Hue · verified capabilities only')
            row.power.setEnabled(hue and a.hue_caps.get('power', False))
            row.power.setToolTip('Hue native power' if hue and a.hue_caps.get('power') else 'Hue power unavailable until the connected bulb confirms support')
            row.level.setEnabled(hue and a.hue_caps.get('brightness', False))
            row.follow.setEnabled(hue and a.hue_caps.get('power', False))
            row.dot.setStyleSheet('background:'+('#46dc97' if hue else '#777386')+';border-radius:6px;')
            row.level.setToolTip('Hue brightness capability verified' if hue and a.hue_caps.get('brightness') else 'Hue brightness unavailable until the connected bulb confirms support')
        selected_hue = self.c.state.selected_channel == 'Hue'
        self.inspector.status.setText('LIVE · '+a.status_for(self.c.state.selected_channel))
        self.inspector.tabs.setEnabled(not self._closing)
        self.inspector.tabs.setTabEnabled(1, hasattr(self.inspector,'live_music'))
        self.inspector.tabs.setTabEnabled(2, True)
        color_enabled = hue and a.hue_caps.get('color', False) if selected_hue else corner
        self.inspector.tabs.widget(0).setEnabled(color_enabled)
        self.inspector.tabs.setTabToolTip(0, 'Requested RGB; not a bulb color readback' if color_enabled else 'Connect a device with a verified color capability')
        self.hue_note.setVisible(selected_hue)
        if selected_hue:
            self.inspector.power.setEnabled(hue and a.hue_caps.get('power', False))
            self.inspector.brightness.setEnabled(hue and a.hue_caps.get('brightness', False))
            self.inspector.follow.setEnabled(hue and a.hue_caps.get('power', False))
            self.inspector.power.setToolTip('Hue native power; verified by existing backend')
            supported = ', '.join(k for k in ('power','brightness','color') if a.hue_caps.get(k)) or 'none verified'
            observed = a.hue_observed
            power = ('on' if observed['power'] else 'off') if 'power' in observed else 'unknown'
            brightness = str(observed.get('brightness', 'unknown'))
            self.hue_note.setText(f'Capabilities: {supported}.\nRead on connect: power {power}, brightness {brightness}/254. RGB is requested, not read back.')
        self.refresh_manual_target()
        self.inspector.live_setup.refresh()
        self.update_inspector_links()
        for i in (0,1,2):
            if self.inspector.tabs.isTabEnabled(i):
                if not self.inspector.tabs.isTabEnabled(self.inspector.tabs.currentIndex()):self.inspector.tabs.setCurrentIndex(i)
                break
