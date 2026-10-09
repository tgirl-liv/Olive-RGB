"""Ephemeral demo state; deliberately has no filesystem or hardware adapters."""
import colorsys
from dataclasses import dataclass, field

NAVIGATION = ('Studio', 'Music', 'Devices', 'Screen', 'Scenes', 'Settings')
SCENES = {
    'MGK After Dark': ('#F34BAC', '#6623AC', 'After the lights go out'),
    'Ultraviolet': ('#7922D8', '#356BFF', 'Electric atmosphere'),
    'Cyber Night': ('#19CAEE', '#E737BF', 'City after midnight'),
    'BRAT Energy': ('#ACFA23', '#149953', 'Unapologetic energy'),
    'Sunset Chill': ('#FF995D', '#C3338C', 'Golden hour glow'),
    'Ocean Breeze': ('#2365DD', '#35D9EB', 'Find your flow'),
    'Neon Party': ('#EF27DA', '#4948EF', 'Turn the night up'),
    'Movie Mode': ('#E08A32', '#183991', 'Settle into the scene'),
}


@dataclass
class Channel:
    name: str
    color: str
    brightness: float = .8
    power: bool = True
    follow: bool = True


@dataclass
class StudioState:
    page: str = 'Studio'
    inspector: str = 'Color'
    selected_channel: str = 'Hue'
    scene: str = 'MGK After Dark'
    favorites: set = field(default_factory=lambda: {'MGK After Dark', 'Ocean Breeze'})
    favorites_only: bool = False
    master_power: bool = True
    master_brightness: float = .8
    mode: str = 'Music'
    playing: bool = True
    motion: bool = True
    transition_seconds: float = 1.2
    transition_curve: str = 'Smooth'
    relationship: str = 'Coordinated Colors'
    separation: float = .25
    sensitivity: float = .6
    smoothing: float = .65
    screen_source: str = 'Demo display 1'
    screen_intensity: float = .75
    channels: dict = field(default_factory=lambda: {
        'Corner': Channel('Corner Lamp', '#F32E83'),
        'Hue': Channel('Philips Hue', '#7927DB'),
    })

    def navigate(self, page):
        if page not in NAVIGATION: raise ValueError(page)
        self.page = page

    def select_inspector(self, tab):
        if tab not in ('Color', 'Music', 'Setup'): raise ValueError(tab)
        self.inspector = tab

    def select_channel(self, channel):
        if channel not in self.channels: raise ValueError(channel)
        self.selected_channel = channel

    def select_scene(self, name):
        if name not in SCENES: raise ValueError(name)
        self.scene = name
        for channel, color in zip(self.channels.values(), SCENES[name][:2]):
            if channel.follow: channel.color = color

    def toggle_favorite(self, name):
        if name not in SCENES: raise ValueError(name)
        if name in self.favorites: self.favorites.remove(name)
        else: self.favorites.add(name)

    def set_transition(self, seconds, curve):
        if curve not in ('Smooth', 'Linear', 'Instant'): raise ValueError(curve)
        self.transition_seconds = max(0., min(5., float(seconds)))
        self.transition_curve = curve

    def set_hex(self, value):
        value = value.strip().lstrip('#')
        if len(value) != 6: raise ValueError('Use six hex digits, e.g. F32E83')
        int(value, 16)
        self.channels[self.selected_channel].color = '#'+value.upper()

    def get_hsv(self):
        value = self.channels[self.selected_channel].color.lstrip('#')
        return colorsys.rgb_to_hsv(*(int(value[i:i+2],16)/255 for i in (0,2,4)))

    def set_hsv(self, h, s, v):
        rgb = colorsys.hsv_to_rgb(float(h)%1, max(0,min(1,float(s))), max(0,min(1,float(v))))
        self.set_hex(''.join(f'{round(c*255):02X}' for c in rgb))
