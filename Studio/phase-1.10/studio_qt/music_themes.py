"""Bounded, versioned Music palette library. No Qt, capture or transport calls."""
import copy
import json
import os
from pathlib import Path
import queue
import tempfile
import threading
import uuid
from .music_runtime import preset_colors,validated_palette

MAX_BYTES=131072
MAX_THEMES=128


def theme_id(value):
    return isinstance(value,str) and str(uuid.UUID(value))==value


def valid_theme_id(value):
    try:return theme_id(value)
    except (ValueError,AttributeError,TypeError):return False


def validated_name(name):
    if not isinstance(name,str):raise ValueError('Theme name must be text')
    name=name.strip()
    if not 1<=len(name)<=64 or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Use a theme name of 1–64 characters without control characters')
    return name


def validated_library(data):
    if not isinstance(data,dict) or type(data.get('version')) is not int or data['version']!=1:
        raise ValueError('Unsupported or invalid theme schema; file preserved')
    records=data.get('themes')
    if not isinstance(records,list) or len(records)>MAX_THEMES:raise ValueError('Invalid theme library size')
    result={};names=set()
    for record in records:
        if not isinstance(record,dict) or not valid_theme_id(record.get('id')):raise ValueError('Invalid theme ID')
        name=validated_name(record.get('name'));identifier=record['id']
        if identifier in result or name.casefold() in names:raise ValueError('Duplicate theme ID or name')
        result[identifier]={'id':identifier,'name':name,'colors':validated_palette(record.get('colors'))}
        names.add(name.casefold())
    return result


class ThemeStore:
    def __init__(self,path=None):
        self.path=Path(path) if path is not None else None
        self.themes={};self.error='';self.blocked=False;self._raw=None
        if self.path is not None:
            resolved=self.path.resolve()
            if resolved.name.lower() in ('settings.json','preferences-v1.json') or any(
                ((parent/'.git').is_file() or (parent/'.git'/'HEAD').is_file()) for parent in (resolved.parent,*resolved.parents)):
                raise ValueError('Theme storage must be outside Git and separate from application settings')
        self.load()

    def _bytes(self):
        if self.path is None or not self.path.exists():return None
        if self.path.stat().st_size>MAX_BYTES:raise ValueError('Theme file exceeds 128 KiB; file preserved')
        with self.path.open('rb') as stream:data=stream.read(MAX_BYTES+1)
        if len(data)>MAX_BYTES:raise ValueError('Theme file exceeds 128 KiB; file preserved')
        return data

    def load(self):
        try:
            raw=self._bytes()
            records={} if raw is None else validated_library(json.loads(raw))
            self.themes=records;self._raw=raw;self.error='';self.blocked=False
        except (OSError,ValueError,TypeError,RecursionError) as error:
            self.themes={};self.error='Custom themes unavailable: '+str(error);self.blocked=True

    def get(self,identifier):return copy.deepcopy(self.themes.get(identifier))
    def list(self):return sorted(copy.deepcopy(list(self.themes.values())),key=lambda t:t['name'].casefold())

    def resolve(self,identifier,builtin):
        theme=self.get(identifier)
        return theme['colors'] if theme is not None else preset_colors(builtin)

    def _persist(self,records):
        if self.blocked:raise ValueError(self.error or 'Theme file is read-only')
        data={'version':1,'themes':list(records.values())}
        records=validated_library(data)
        raw=(json.dumps(data,indent=2,allow_nan=False)+'\n').encode('utf-8')
        if len(raw)>MAX_BYTES:raise ValueError('Theme library exceeds 128 KiB')
        if self.path is not None:
            if self._bytes()!=self._raw:raise ValueError('Theme file changed externally; reopen Studio before saving')
            self.path.parent.mkdir(parents=True,exist_ok=True);temporary=None
            try:
                with tempfile.NamedTemporaryFile(dir=self.path.parent,prefix='.music-themes-',delete=False) as stream:
                    temporary=stream.name;stream.write(raw);stream.flush();os.fsync(stream.fileno())
                os.replace(temporary,self.path)
            finally:
                if temporary is not None and os.path.exists(temporary):os.unlink(temporary)
        # Complete snapshot replacement only after successful disk commit.
        self.themes=records;self._raw=raw;self.error=''

    def save(self,identifier,name,colors):
        name=validated_name(name);colors=validated_palette(colors)
        records=copy.deepcopy(self.themes)
        if identifier is not None and identifier not in records:raise ValueError('Custom theme no longer exists')
        identifier=identifier or str(uuid.uuid4())
        records[identifier]={'id':identifier,'name':name,'colors':colors}
        self._persist(records);return identifier

    def rename(self,identifier,name):
        theme=self.get(identifier)
        if theme is None:raise ValueError('Only custom themes can be renamed')
        return self.save(identifier,name,theme['colors'])

    def delete(self,identifier):
        records=copy.deepcopy(self.themes)
        if identifier not in records:raise ValueError('Only custom themes can be deleted')
        del records[identifier];self._persist(records);return identifier


class ThemeJobs:
    """One disk transaction at a time; GUI polls a bounded result mailbox."""
    def __init__(self,store):self.store=store;self.thread=None;self.results=queue.Queue(maxsize=1)
    @property
    def busy(self):return (self.thread is not None and self.thread.is_alive()) or not self.results.empty()
    def submit(self,operation,*args):
        if self.busy:raise ValueError('A theme save is already in progress')
        args=copy.deepcopy(args)
        def run():
            try:result=(getattr(self.store,operation)(*args),'')
            except (OSError,ValueError,TypeError) as error:result=(None,str(error))
            self.results.put_nowait(result)
        self.thread=threading.Thread(target=run,name='Music theme save',daemon=True);self.thread.start()
    def take(self):
        if self.thread is not None and self.thread.is_alive():return None
        try:return self.results.get_nowait()
        except queue.Empty:return None
