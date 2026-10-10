"""Interface-only settings and bounded history of existing GUI status messages."""
from datetime import datetime
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QComboBox,QPlainTextEdit,QApplication
from .common import Panel,text,button
from ..appearance import THEMES,stylesheet


class AppearanceSettings(Panel):
    def __init__(self,window):
        super().__init__('APPEARANCE / SYSTEM');self.window=window;self.seen={}
        self.theme=QComboBox();self.theme.addItems(['Studio']+list(THEMES))
        self.theme.setAccessibleName('Interface theme');self.theme.setCurrentText(window.preferences['appearance']['theme'])
        self.box.addWidget(self.theme)
        note=text('Interface colors only. Music palettes, artwork and light output stay independent.','muted');note.setWordWrap(True);self.box.addWidget(note)
        self.log=QPlainTextEdit();self.log.setReadOnly(True);self.log.setMaximumBlockCount(500);self.log.setMinimumHeight(150)
        self.log.setAccessibleName('Studio status and error history');self.box.addWidget(self.log)
        self.box.addWidget(button('Copy log',lambda:QApplication.clipboard().setText(self.log.toPlainText())))
        self.box.addWidget(button('Clear log',self.log.clear))
        self.theme.currentTextChanged.connect(self.change_theme);self.change_theme(self.theme.currentText())
        self.timer=QTimer(self);self.timer.setInterval(250);self.timer.timeout.connect(self.collect);self.timer.start()
        self.append('Studio','Ready. Hardware and capture require explicit actions.')

    def change_theme(self,name):
        self.window.setStyleSheet(stylesheet(name));self.window.preferences['appearance']['theme']=name
        self.window.queue_preferences()

    def append(self,source,message):
        self.log.appendPlainText(datetime.now().strftime('%H:%M:%S')+' · '+source+' · '+str(message)[:2048])

    def collect(self):
        # Read GUI-owned labels only; no worker lock, queue, capture or hardware I/O.
        if getattr(self.window,'_closing',False):self.timer.stop();return
        for name in ('live_status','hue_status','music_status','screen_status','preferences_notice','theme_notice'):
            label=getattr(self.window,name,None)
            if label is None:continue
            message=label.text()
            if name=='music_status' and message.startswith('LIVE · RMS'):message='LIVE · measured Music output active'
            if self.seen.get(name)!=message:
                self.seen[name]=message
                if message:self.append(name.removesuffix('_status').replace('_',' '),message)

        album=getattr(self.window,'album',None)
        if album is not None:
            message=album.status.text()
            if self.seen.get('album')!=message:
                self.seen['album']=message
                if message:self.append('Album lighting',message)
