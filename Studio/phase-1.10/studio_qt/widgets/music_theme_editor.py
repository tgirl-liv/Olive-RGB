"""Music lighting palette editor; drafts never touch the engine or transports."""
from PySide6.QtCore import Qt,Signal,QSignalBlocker
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QLineEdit,QSpinBox,QColorDialog
from .common import button,text
from ..music_runtime import validated_palette
from ..music_themes import validated_name


class ThemeColorRow:
    def __init__(self,layout,key,color,parent):
        row=QHBoxLayout();row.addWidget(text(key.upper()))
        self.swatch=button('Pick color',lambda:self.pick(parent));self.swatch.setFixedWidth(90);row.addWidget(self.swatch)
        self.hex=QLineEdit();self.hex.setMaxLength(7);self.hex.setAccessibleName(key+' hex');row.addWidget(self.hex)
        self.rgb=[]
        for component in ('R','G','B'):
            spin=QSpinBox();spin.setRange(0,255);spin.setPrefix(component+' ')
            spin.setAccessibleName(key+' '+component);row.addWidget(spin);self.rgb.append(spin)
            spin.valueChanged.connect(self.rgb_changed)
        self.hex.textChanged.connect(self.hex_changed);layout.addLayout(row);self.set_color(color)

    def set_color(self,color):
        blockers=[QSignalBlocker(widget) for widget in (self.hex,*self.rgb)]
        self.hex.setText(color.upper())
        for spin,value in zip(self.rgb,(int(color[i:i+2],16) for i in (1,3,5))):spin.setValue(value)
        self.swatch.setStyleSheet('background-color:'+color+';color:'+('#000000' if QColor(color).lightness()>140 else '#FFFFFF')+';')

    def hex_changed(self,value):
        try:validated_palette({key:value for key in ('bass','mids','treble','beat')})
        except ValueError:return
        self.set_color(value)

    def rgb_changed(self,*args):self.set_color('#'+''.join(f'{spin.value():02X}' for spin in self.rgb))
    def pick(self,parent):
        color=QColorDialog.getColor(QColor(self.hex.text()),parent,'Music lighting color')
        if color.isValid():self.set_color(color.name())


class MusicThemeEditor(QDialog):
    save_requested=Signal(object,str,object,bool)
    def __init__(self,name,colors,identifier=None,parent=None):
        super().__init__(parent);self.setWindowTitle('Custom Music Lighting Theme')
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.identifier=identifier;layout=QVBoxLayout(self)
        note=text('Edits LIGHT colors only. Save & Select uses the existing Music output and Virtual Light Preview. Album artwork keeps ownership while available.','muted')
        note.setWordWrap(True);layout.addWidget(note)
        self.name=QLineEdit(name);self.name.setMaxLength(64);self.name.setAccessibleName('Custom theme name');layout.addWidget(self.name)
        self.colors={key:ThemeColorRow(layout,key,value,self) for key,value in validated_palette(colors).items()}
        self.error=QLabel();self.error.setTextFormat(Qt.TextFormat.PlainText);self.error.setWordWrap(True);layout.addWidget(self.error)
        row=QHBoxLayout();self.save_button=button('Save',lambda:self.request_save(False))
        self.select_button=button('Save & Select',lambda:self.request_save(True))
        row.addWidget(self.save_button);row.addWidget(self.select_button);row.addWidget(button('Cancel',self.reject));layout.addLayout(row)

    def request_save(self,select):
        try:
            name=validated_name(self.name.text());colors=validated_palette({key:row.hex.text() for key,row in self.colors.items()})
        except ValueError as error:self.error.setText(str(error));return
        self.error.clear();self.save_button.setEnabled(False);self.select_button.setEnabled(False)
        self.save_requested.emit(self.identifier,name,colors,select)

    def save_finished(self,error):
        if error:
            self.error.setText(error);self.save_button.setEnabled(True);self.select_button.setEnabled(True)
        else:self.accept()
