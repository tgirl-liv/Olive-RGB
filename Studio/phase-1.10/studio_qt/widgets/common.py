from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QPushButton, QSlider, QScrollArea


def text(value, role=None):
    widget=QLabel(value)
    if role:widget.setProperty('role',role)
    return widget


def button(value, callback=None, checkable=False):
    widget=QPushButton(value);widget.setCheckable(checkable)
    widget.setAccessibleName(value);widget.setToolTip(value)
    if callback:widget.clicked.connect(callback)
    return widget


def slider(value, callback=None, high=100, vertical=False):
    widget=QSlider(Qt.Orientation.Vertical if vertical else Qt.Orientation.Horizontal)
    widget.setRange(0,high);widget.setValue(round(value));widget.setMinimumWidth(18 if vertical else 50)
    if callback:widget.valueChanged.connect(callback)
    return widget


def assign(widget, value):
    blocker=QSignalBlocker(widget)
    if hasattr(widget,'setChecked') and isinstance(value,bool):widget.setChecked(value)
    elif hasattr(widget,'setCurrentText'):widget.setCurrentText(str(value))
    elif hasattr(widget,'setValue'):widget.setValue(value)
    else:widget.setText(str(value))


class Panel(QFrame):
    def __init__(self,title=None,caption=None,parent=None):
        super().__init__(parent);self.setObjectName('panel')
        self.box=QVBoxLayout(self);self.box.setContentsMargins(14,10,14,10);self.box.setSpacing(8)
        self.header=QHBoxLayout()
        if title:self.header.addWidget(text(title,'heading'))
        self.header.addStretch()
        if caption:self.header.addWidget(text(caption,'muted'))
        if title:self.box.addLayout(self.header)


def scroll(widget):
    area=QScrollArea();area.setWidgetResizable(True);area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setWidget(widget)
    widget.setAutoFillBackground(False)
    return area
