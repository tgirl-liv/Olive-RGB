"""LIVE inspector views of existing window actions; no sessions or controller state."""
from PySide6.QtCore import QSignalBlocker,Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QComboBox, QCheckBox
from .common import text, button, slider, assign


def replace_tab(inspector, index, widget, title):
    # Keep the hidden DEMO controls alive for Inspector.sync, but never interactive.
    tabs = inspector.tabs
    blocker = QSignalBlocker(tabs)
    current = tabs.currentIndex()
    previous = tabs.widget(index)
    tabs.removeTab(index)
    previous.hide();previous.setEnabled(False)
    tabs.insertTab(index, widget, title)
    tabs.setCurrentIndex(current)
    del blocker


class LiveSetupInspector(QWidget):
    def __init__(self, window):
        super().__init__();self.window = window
        layout = QVBoxLayout(self)
        layout.addWidget(text('LIVE DEVICE CONNECTION', 'heading'))
        self.status = text('', 'muted');self.status.setWordWrap(True);layout.addWidget(self.status)
        self.connect_button = button('Connect selected device', lambda:self.connection_action(True))
        self.disconnect_button = button('Disconnect selected device', lambda:self.connection_action(False))
        layout.addWidget(self.connect_button);layout.addWidget(self.disconnect_button)
        self.capabilities = text('', 'muted');self.capabilities.setWordWrap(True);layout.addWidget(self.capabilities)
        note = text('Capabilities describe the current connection. No connection or scan starts when opening this tab.', 'muted')
        note.setWordWrap(True);layout.addWidget(note)
        for label in ('Choose another device', 'Color temperature', 'Scene / transition settings'):
            control = button(label);control.setEnabled(False)
            control.setToolTip('Unavailable in the current Qt LIVE controls')
            layout.addWidget(control)
        layout.addStretch()

    def endpoints(self, key):
        w = self.window
        if key == 'Corner':return w.connect_button, w.disconnect_button
        if hasattr(w, 'hue_connect'):return w.hue_connect, w.hue_disconnect
        return None, None

    def connection_action(self, connect):
        # Existing buttons retain cancellation/connection ownership and gating.
        for key in self.window.c.target_devices():
            endpoint = self.endpoints(key)[0 if connect else 1]
            if endpoint is not None and endpoint.isEnabled():endpoint.click()

    def refresh(self):
        w = self.window;a = w.c.adapter;keys=w.c.target_devices()
        pairs=[self.endpoints(key) for key in keys]
        self.connect_button.setEnabled(any(connect is not None and connect.isEnabled() for connect,_ in pairs))
        self.disconnect_button.setEnabled(any(disconnect is not None and disconnect.isEnabled() for _,disconnect in pairs))
        statuses=[];capabilities=[]
        for key in keys:
            if key == 'Corner':
                name=w.c.state.channels['Corner'].name
                statuses.append(name+' · '+w.live_status.text())
                power = 'software power via RGB black' if a.software_power else 'power unsupported'
                capabilities.append(name+': '+('connected, RGB color, software brightness, '+power+'. No native power or temperature control.'
                                               if a.connected else 'disconnected; RGB color, software brightness, '+power+' after connection.'))
            elif hasattr(w, 'hue_status'):
                statuses.append(w.hue_status.text())
                if a.hue_connected:
                    supported = ', '.join(k for k,v in a.hue_caps.items() if v) or 'none reported'
                    capabilities.append('Hue reported capabilities: '+supported+'. Qt lighting controls use verified power, brightness and color only.')
                else:capabilities.append('Hue capabilities unknown until connected.')
            else:
                statuses.append('Hue · unavailable in this window')
                capabilities.append('No Hue session in this Corner-only window.')
        self.status.setText('\n'.join(statuses));self.capabilities.setText('\n'.join(capabilities))


class LiveMusicInspector(QWidget):
    def __init__(self, window):
        super().__init__();self.window = window
        layout = QVBoxLayout(self);layout.addWidget(text('LIVE MUSIC ROUTING', 'heading'))
        self.participation = QCheckBox();layout.addWidget(self.participation)
        self.participation.checkStateChanged.connect(lambda state:self.set_participation(state==Qt.CheckState.Checked))
        note = text('Participation applies to the selected device. Coordination is shared by all participating devices; change it while Music runs.', 'muted')
        note.setWordWrap(True);layout.addWidget(note)
        self.relationship = QComboBox();self.relationship.addItems([window.harmony.itemText(i) for i in range(window.harmony.count())])
        self.relationship.currentTextChanged.connect(window.harmony.setCurrentText)
        window.harmony.currentTextChanged.connect(lambda value:assign(self.relationship, value))
        layout.addWidget(text('Shared color relationship'));layout.addWidget(self.relationship)
        self.separation = slider(window.separation.value(), window.separation.setValue)
        window.separation.valueChanged.connect(lambda value:assign(self.separation, value))
        layout.addWidget(text('Shared color separation (%)'));layout.addWidget(self.separation)
        self.start = button('Start Music', window.music_start.click)
        self.stop = button('Stop Music', window.music_stop.click)
        layout.addWidget(self.start);layout.addWidget(self.stop)
        self.status = text('', 'muted');self.status.setWordWrap(True);layout.addWidget(self.status)
        layout.addWidget(button('Open LIVE Music panel', lambda:window.c.navigate('Music')))
        layout.addStretch();self.refresh()

    def set_participation(self, enabled):
        for key in self.window.c.target_devices():
            endpoint=self.window.participate[key]
            if endpoint.isEnabled():endpoint.setChecked(enabled)

    def refresh(self):
        w = self.window;keys = w.c.target_devices()
        values=[w.participate[key].isChecked() for key in keys]
        blocker=QSignalBlocker(self.participation);self.participation.setTristate(len(keys)>1)
        self.participation.setCheckState(Qt.CheckState.Checked if all(values) else Qt.CheckState.Unchecked if not any(values) else Qt.CheckState.PartiallyChecked)
        del blocker
        self.participation.setText(('Both Lights' if len(keys)>1 else keys[0])+' participate in Music')
        self.participation.setEnabled(any(w.participate[key].isEnabled() for key in keys))
        assign(self.relationship, w.harmony.currentText());assign(self.separation, w.separation.value())
        self.relationship.setEnabled(w.harmony.isEnabled());self.separation.setEnabled(w.separation.isEnabled())
        self.relationship.setToolTip('Shared production coordination; stop capture before changing' if not w.harmony.isEnabled() else w.harmony.currentText())
        self.separation.setToolTip('Shared production coordination; stop capture before changing' if not w.separation.isEnabled() else 'Separation for Coordinated Colors')
        self.start.setEnabled(w.music_start.isEnabled());self.stop.setEnabled(w.music_stop.isEnabled())
        ownership=[];owner='Screen' if getattr(w.c.adapter,'screen_active',False) else 'Music'
        for key in keys:
            ownership.append(owner+' owns '+key+(' color. Stop Screen to edit manually.' if owner=='Screen' else ' color. Opt out or Stop to edit manually.') if w.c.adapter.owns(key) else key+': '+(w.c.target_reason(key,'color') or 'manual color available'))
        self.status.setText('\n'.join(ownership)+'\n'+w.music_status.text())
