"""Versioned Qt-only preferences. Loading never invokes a device or audio service."""
import copy
import json
import math
import os
from pathlib import Path
import re
import tempfile

PROFILES = ('Smooth', 'Reactive', 'Hyperpop', 'MGK')
PALETTES = ('Default', 'The Weeknd — After Hours', 'The Weeknd — Dawn FM',
            'The Weeknd — Starboy', 'Charli xcx — BRAT', 'Charli xcx — Crash')


def default_path():
    return Path(os.environ.get('LOCALAPPDATA', Path.home()/'.local/share'))/'OliveRGBStudio'/'preferences-v1.json'


def defaults(mode):
    return {'master': {'power': True, 'brightness': .8},
            'devices': {key: {'power': True, 'brightness': .8, 'color': color,
                             'follow': key != 'Hue' or mode == 'demo'}
                        for key, color in (('Corner', '#F32E83'), ('Hue', '#7927DB'))},
            'music': {'profile': 'Reactive', 'palette': 'Default',
                      'sensitivity': 1. if mode == 'live' else .6,
                      'smoothing': 1. if mode == 'live' else .65,
                      'relationship': 'Coordinated Colors', 'separation': .25,
                      'participation': {'Corner': True, 'Hue': True}}}


def validate(data, mode):
    """Reject malformed values; fill missing v1 fields for forward additions."""
    def merge(template, supplied, key=''):
        if isinstance(template, dict):
            if not isinstance(supplied, dict):raise ValueError('Invalid '+key)
            return {k: merge(v, supplied.get(k, v), k) for k, v in template.items()}
        if isinstance(template, bool):valid = type(supplied) is bool
        elif isinstance(template, (float, int)):
            low, high = (0., 1.)
            if mode == 'live' and key in ('sensitivity', 'smoothing'):
                low, high = .25, (3. if key == 'sensitivity' else 1.4)
            valid = type(supplied) in (int, float) and low <= supplied <= high and math.isfinite(supplied)
        elif key == 'color':valid = isinstance(supplied, str) and re.fullmatch(r'#[0-9a-fA-F]{6}', supplied)
        elif key == 'profile':valid = supplied in PROFILES
        elif key == 'palette':valid = supplied in PALETTES
        elif key == 'relationship':valid = supplied in ('Coordinated Colors', 'Same Color') + (('Independent Devices',) if mode == 'demo' else ())
        else:valid = supplied == template
        if not valid:raise ValueError('Invalid '+key)
        return supplied.upper() if key == 'color' else supplied
    return merge(defaults(mode), data)


class PreferencesStore:
    def __init__(self, path=None):
        self.path = Path(path) if path is not None else None
        self.error = ''; self.blocked = False
        if self.path is not None:
            resolved = self.path.resolve()
            production = (Path(os.environ.get('APPDATA', Path.home()))/'OliveRGB'/'settings.json').resolve()
            if resolved == production or (resolved.name.lower() == 'settings.json' and resolved.parent.name.lower() == 'olivergb'):
                raise ValueError('Qt preferences cannot overwrite Tkinter settings')

    def _read(self):
        if self.path is None or not self.path.exists():return {}
        if self.path.stat().st_size > 65536:raise ValueError('Preferences file exceeds 64 KiB')
        with self.path.open(encoding='utf-8') as stream:data = json.load(stream)
        if not isinstance(data, dict) or type(data.get('version')) is not int:raise ValueError('Invalid preferences schema')
        if data['version'] != 1:
            self.blocked = True
            raise ValueError('Unsupported preferences version; file preserved')
        return {mode: validate(data.get(mode, {}), mode) for mode in ('demo', 'live')}

    def load(self, mode):
        try:return self._read().get(mode, defaults(mode))
        except (OSError, ValueError, TypeError, RecursionError) as exc:
            self.error = 'Qt preferences reset to defaults: '+str(exc)
            return defaults(mode)

    def save(self, mode, values):
        if self.path is None:return True
        try:
            values = validate(values, mode)
            try:data = self._read()
            except (OSError, ValueError, TypeError, RecursionError):data = {}
            if self.blocked:return False
            data.update(version=1);data[mode] = copy.deepcopy(values)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            name = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.path.parent,
                                                 prefix='.preferences-', delete=False) as stream:
                    name = stream.name
                    json.dump(data, stream, indent=2, allow_nan=False)
                    stream.flush();os.fsync(stream.fileno())
                os.replace(name, self.path)
            finally:
                if name is not None and os.path.exists(name):os.unlink(name)
            self.error = '';return True
        except (OSError, ValueError, TypeError) as exc:
            self.error = 'Qt preferences could not be saved: '+str(exc);return False


def restore(state, values):
    state.master_power = values['master']['power'];state.master_brightness = values['master']['brightness']
    for key, fields in values['devices'].items():
        for name, value in fields.items():setattr(state.channels[key], name, value)
    for name in ('sensitivity', 'smoothing', 'relationship', 'separation'):setattr(state, name, values['music'][name])
    state.mode = 'Manual';state.playing = False


def snapshot(state, music):
    return {'master': {'power': state.master_power, 'brightness': state.master_brightness},
            'devices': {key: {name: getattr(channel, name) for name in ('power', 'brightness', 'color', 'follow')}
                        for key, channel in state.channels.items()}, 'music': copy.deepcopy(music)}
