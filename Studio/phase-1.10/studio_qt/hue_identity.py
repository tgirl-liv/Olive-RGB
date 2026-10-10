"""Read only the original application's saved Hue identity; never write settings."""
import json
import os
from pathlib import Path


def load_hue_identity(path=None):
    path = Path(path) if path is not None else Path(os.getenv('APPDATA', str(Path.home()))) / 'OliveRGB' / 'settings.json'
    if not path.exists():return {'name': 'Tv lamp'}
    if path.stat().st_size > 1024 * 1024:raise ValueError('Production settings too large to read Hue identity safely')
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        hue = data.get('hue', {})
        identity = hue.get('identity', {})
        if not isinstance(identity, dict):raise ValueError('Hue identity must be an object')
        result = {'name': 'Tv lamp'}
        for key in ('name', 'address_hint', 'zigbee_address'):
            if key in identity:
                value = identity[key]
                if not isinstance(value, str) or not value.strip() or len(value) > 256:
                    raise ValueError(f'Invalid saved Hue {key}')
                result[key] = value
        return result
    except (ValueError, TypeError, AttributeError) as error:
        raise ValueError(f'Cannot use saved Hue identity: {error}. Production settings were not changed.') from error


def validate_identity(identity):
    """Only the existing BLE driver's identity fields; no bridge credentials."""
    if not isinstance(identity, dict):raise ValueError('Hue identity must be an object')
    result = {'name': 'Tv lamp'}
    for key in ('name', 'address_hint', 'zigbee_address'):
        if key in identity:
            value = identity[key]
            if not isinstance(value, str) or not value.strip() or len(value)>256:
                raise ValueError('Invalid Hue '+key)
            result[key] = value.strip()
    return result
