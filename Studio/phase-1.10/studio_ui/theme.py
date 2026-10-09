"""Studio design tokens. No runtime settings or backend dependencies."""
BG = '#0E101A'
PANEL = '#1B1D2C'
RAISED = '#252438'
SIDEBAR = '#11131F'
WELL = '#10121F'
LINE = '#393650'
TEXT = '#F5F0FF'
MUTED = '#AAA5BD'
PINK = '#F34BAC'
PURPLE = '#A46AFF'
CYAN = '#35C8EF'
SELECTED = '#382653'
HOVER = '#332D48'
DISABLED = '#686579'
FOCUS = '#D8C1FF'

# Four-pixel rhythm; optical one-pixel strokes remain local to Canvas drawing.
SPACE = {'xs': 4, 'sm': 8, 'md': 12, 'lg': 16, 'xl': 24, 'xxl': 32}
RADIUS = {'control': 8, 'card': 12, 'pill': 16}
FONT_FAMILY = 'Segoe UI'
TYPE = {
    'title': (FONT_FAMILY, 22, 'bold'),
    'heading': (FONT_FAMILY, 11, 'bold'),
    'body': (FONT_FAMILY, 10),
    'control': (FONT_FAMILY, 9),
    'caption': (FONT_FAMILY, 8),
    'numeric': ('Consolas', 10),
}
FRAME_MS = 34
ATTACK_SECONDS = .045
DECAY_SECONDS = .28
PEAK_HOLD_SECONDS = .24
PEAK_DECAY_PER_SECOND = .30
SCENE_COLUMNS_BREAKPOINT = 650
COMPACT_NAV_BREAKPOINT = 1000


def font(size=10, bold=False):
    return (FONT_FAMILY, size, 'bold' if bold else 'normal')
