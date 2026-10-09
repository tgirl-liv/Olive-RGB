"""Album-derived Music palette controls; never themes or sends device commands."""
import queue
import sys
from PySide6.QtCore import QTimer,Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QComboBox,QLabel,QHBoxLayout
from .common import Panel,text,assign
from ..music_runtime import preset_colors,validated_palette


class ArtworkSession:
    """Pure Python destruction callback; never touches a deleted Qt widget."""
    def __init__(self):self.worker=None
    def close(self):
        worker,self.worker=self.worker,None
        if worker is not None:worker.close()


class AlbumLightingPanel(Panel):
    def __init__(self,runtime,preset,source='Preset',worker_factory=None,palette_resolver=None):
        super().__init__('ALBUM COVER LIGHTING')
        self.runtime=runtime;self.preset=preset;self.closed=False
        self.session=ArtworkSession();self.destroyed.connect(self.session.close)
        self.worker_factory=worker_factory;self.artwork_active=False
        self.resolve_palette=palette_resolver or (lambda:preset_colors(preset.currentText()))
        self.current_palette=self.resolve_palette()
        note=text('Changes Music LIGHT colors only. Start Music to apply through existing device participation; Master power/brightness still apply.','muted')
        note.setWordWrap(True);self.box.addWidget(note)
        self.source=QComboBox();self.source.addItems(['Preset','Album artwork'])
        self.source.setAccessibleName('Music lighting color source');assign(self.source,source);self.box.addWidget(self.source)
        row=QHBoxLayout();self.preview=QLabel('No artwork');self.preview.setFixedSize(110,110)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter);self.preview.setAccessibleName('Current album artwork')
        self.status=text('','muted');self.status.setWordWrap(True);self.status.setTextFormat(Qt.TextFormat.PlainText)
        row.addWidget(self.preview);row.addWidget(self.status,1);self.box.addLayout(row)
        row=QHBoxLayout();self.swatches={}
        for key in ('bass','mids','treble','beat'):
            label=QLabel();label.setAlignment(Qt.AlignmentFlag.AlignCenter);label.setMinimumHeight(42)
            label.setAccessibleName('Album lighting '+key+' color');self.swatches[key]=label;row.addWidget(label)
        self.box.addLayout(row)
        self.box.addWidget(text('VIRTUAL LIGHT PREVIEW','heading'))
        note=text('Read-only Corner Lamp Music output, including local power/brightness and Follow Master. Works without a connected light.','muted')
        note.setWordWrap(True);self.box.addWidget(note)
        row=QHBoxLayout();self.light_indicator=QLabel();self.light_indicator.setFixedSize(64,64)
        self.light_indicator.setAccessibleName('Virtual Corner Lamp color')
        self.light_readout=text('','muted');self.light_readout.setWordWrap(True)
        self.light_readout.setTextFormat(Qt.TextFormat.PlainText)
        row.addWidget(self.light_indicator);row.addWidget(self.light_readout,1);self.box.addLayout(row)
        self.virtual_rgb=None;self._light_snapshot=None
        self.update_light_preview(None,None,'Start Music for measured output.')
        self.timer=QTimer(self);self.timer.setInterval(200);self.timer.timeout.connect(self.poll)
        self.source.currentTextChanged.connect(self.change_source)
        self.preset.currentTextChanged.connect(self.preset_changed)
        self.change_source()

    @property
    def worker(self):return self.session.worker

    @worker.setter
    def worker(self,value):self.session.worker=value

    def apply_palette(self,colors):
        colors=validated_palette(colors);self.runtime.set_palette(colors);self.current_palette=colors
        for key,label in self.swatches.items():
            color=colors[key];rgb=tuple(int(color[i:i+2],16) for i in (1,3,5))
            ink='#000000' if sum(a*b for a,b in zip(rgb,(299,587,114)))>=145000 else '#FFFFFF'
            label.setText(key.upper()+'\n'+color)
            label.setStyleSheet('background-color:'+color+';color:'+ink+';border-radius:5px;')

    def update_light_preview(self,rgb,engine_rgb,status):
        if self.closed:return
        snapshot=(rgb,engine_rgb,status)
        if snapshot==self._light_snapshot:return
        self._light_snapshot=snapshot
        self.virtual_rgb=rgb
        color='#'+''.join(f'{c:02X}' for c in rgb) if rgb is not None else '#25283C'
        self.light_indicator.setStyleSheet('background-color:'+color+';border:1px solid #72768A;border-radius:12px;')
        def readout(value):return 'RGB '+', '.join(map(str,value))+' · #'+''.join(f'{c:02X}' for c in value)
        self.light_readout.setText(('Output: '+readout(rgb)+'\nEngine: '+readout(engine_rgb)+'\n' if rgb is not None else '')+status)

    def fallback(self,description):
        self.artwork_active=False
        self.apply_palette(self.resolve_palette())
        self.preview.clear();self.preview.setText('No artwork')
        self.status.setText(description+'\nFallback: '+self.preset.currentText())

    def retire_worker(self):
        self.timer.stop()
        self.session.close()

    def change_source(self,*args):
        if self.closed:return
        # Retire the whole media session: late results stay in its detached queue,
        # including a rapid Album -> Preset -> Album switch. No GUI callbacks.
        self.retire_worker()
        if self.source.currentText()=='Preset':
            self.fallback('Preset lighting colors');return
        self.fallback('Waiting for a playing media session and artwork…')
        if sys.platform!='win32' and self.worker_factory is None:
            self.fallback('Windows media artwork is unavailable on this platform.');return
        factory=self.worker_factory
        if factory is None:
            from ..album_artwork import StudioAlbumArtworkWorker
            factory=StudioAlbumArtworkWorker
        try:
            self.worker=factory();self.worker.set_enabled(True);self.timer.start()
        except (OSError,RuntimeError) as error:
            self.retire_worker();self.fallback('Artwork worker unavailable: '+type(error).__name__)

    def preset_changed(self,*args):
        if not self.closed and not self.artwork_active:
            self.fallback('Preset changed; waiting for artwork.' if self.source.currentText()=='Album artwork' else 'Preset lighting colors')

    def poll(self):
        if self.closed or self.worker is None or self.source.currentText()!='Album artwork':return
        try:kind,description,palette,data=self.worker.messages.get_nowait()
        except queue.Empty:return
        if kind!='artwork':self.fallback(description);return
        try:self.apply_palette(palette)
        except ValueError:
            self.fallback('Invalid artwork palette; using preset colors.');return
        self.artwork_active=True
        self.status.setText(description+'\nAlbum colors active for Music lighting.')
        self.preview.clear()
        pixmap=QPixmap()
        if data and pixmap.loadFromData(data):self.preview.setPixmap(pixmap)
        else:self.preview.setText('No preview')

    def shutdown(self):
        if self.closed:return
        self.closed=True;self.retire_worker();self.source.setEnabled(False)
