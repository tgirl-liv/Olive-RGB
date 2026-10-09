"""Versioned UI-only layout persistence. No lighting settings or backend imports."""
import json
import os
import tempfile
from pathlib import Path
from dataclasses import dataclass, asdict
from PySide6.QtCore import Qt, QRect
from PySide6.QtWidgets import QSplitter, QSplitterHandle, QApplication


@dataclass
class Workspace:
    version: int = 1
    sidebar_collapsed: bool = False
    inspector_collapsed: bool = False
    preset: str = 'Studio'
    splitter_sizes: tuple = (900,330)
    geometry: tuple | None = None


def default_path():
    return Path(os.environ.get('LOCALAPPDATA',Path.home()/'.local/share'))/'OliveRGBStudio'/'workspace-v1.json'


class WorkspaceStore:
    def __init__(self,path=None):self.path=Path(path) if path is not None else None;self.error=''
    def load(self):
        if self.path is None:return Workspace()
        try:
            if self.path.stat().st_size>16384:raise ValueError('Workspace file too large')
            d=json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(d,dict) or type(d.get('version')) is not int or d['version']!=1:raise ValueError('Unsupported workspace version')
            for key in ('sidebar_collapsed','inspector_collapsed'):
                if type(d.get(key)) is not bool:raise ValueError('Invalid panel preference')
            if d.get('preset') not in ('Studio','Music','Compact'):raise ValueError('Invalid workspace preset')
            sizes=d.get('splitter_sizes')
            if not isinstance(sizes,list) or len(sizes)!=2 or any(type(x) is not int or not 1<=x<=20000 for x in sizes):raise ValueError('Invalid splitter sizes')
            geometry=d.get('geometry')
            if geometry is not None:
                if not isinstance(geometry,list) or len(geometry)!=4 or any(type(x) is not int or abs(x)>100000 for x in geometry):raise ValueError('Invalid geometry')
                if not 800<=geometry[2]<=20000 or not 600<=geometry[3]<=20000:raise ValueError('Invalid window size')
            return Workspace(1,d['sidebar_collapsed'],d['inspector_collapsed'],d['preset'],tuple(sizes),tuple(geometry) if geometry else None)
        except FileNotFoundError:return Workspace()
        except (OSError,ValueError,TypeError):
            self.error='Saved workspace could not be read; default layout restored.';return Workspace()
    def save(self,workspace):
        if self.path is None:return True
        temporary=None
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=self.path.parent,prefix='.workspace-',suffix='.tmp',delete=False) as stream:
                temporary=Path(stream.name);json.dump(asdict(workspace),stream,indent=2);stream.flush();os.fsync(stream.fileno())
            os.replace(temporary,self.path);self.error='';return True
        except OSError:
            self.error='Workspace could not be saved; current layout remains available for this session.';return False
        finally:
            if temporary is not None:
                try:temporary.unlink(missing_ok=True)
                except OSError:pass


class WorkspaceHandle(QSplitterHandle):
    def __init__(self,orientation,parent):
        super().__init__(orientation,parent);self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('Resize workspace and inspector');self.setToolTip('Drag to resize · Left/Right arrows · Shift for larger steps')
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key.Key_Left,Qt.Key.Key_Right):
            splitter=self.splitter();sizes=splitter.sizes();step=40 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 16
            self.moveSplitter(sizes[0]+(step if event.key()==Qt.Key.Key_Right else -step));event.accept()
        else:super().keyPressEvent(event)


class WorkspaceSplitter(QSplitter):
    def createHandle(self):return WorkspaceHandle(self.orientation(),self)


def visible_geometry(saved):
    screens=[s.availableGeometry() for s in QApplication.screens()]
    if saved and any(area.contains(QRect(*saved)) for area in screens):return QRect(*saved)
    area=QApplication.primaryScreen().availableGeometry()
    width=min(1440,area.width()-24);height=min(900,area.height()-48)
    width=max(800,width);height=max(600,height)
    return QRect(area.x()+max(0,(area.width()-width)//2),area.y()+24,width,height)
