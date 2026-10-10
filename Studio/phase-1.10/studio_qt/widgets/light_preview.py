"""Shared read-only output indicator; contains no lighting calculations."""
from .common import Panel,text
from PySide6.QtWidgets import QHBoxLayout

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


class VirtualLightPreview(Panel):
    update_light_preview=update_light_preview
    def __init__(self,compact=False):
        super().__init__(None if compact else 'VIRTUAL LIGHT PREVIEW')
        self.closed=False;self._light_snapshot=None;self.virtual_rgb=None
        self.light_indicator=text('');self.light_indicator.setMinimumHeight(80)
        self.light_readout=text('','muted');self.light_readout.setWordWrap(True)
        if compact:
            self.box.setContentsMargins(0,0,0,0)
            self.light_indicator.setFixedSize(48,44);self.light_readout.setFixedHeight(44)
            row=QHBoxLayout();row.addWidget(self.light_indicator);row.addWidget(self.light_readout,1);self.box.addLayout(row)
        else:self.box.addWidget(self.light_indicator);self.box.addWidget(self.light_readout)
        self.update_light_preview(None,None,'Start capture; no physical lights required.')
