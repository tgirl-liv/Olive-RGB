"""Original interface themes; lighting palettes and painters remain independent."""
from .theme import QSS

THEMES = {'Tickets': {'background': '#F4EEE9',
             'surface': '#FFF9F5',
             'text': '#171417',
             'log_background': '#292329',
             'muted': '#756A72',
             'accent_soft': '#F08AB6',
             'accent': '#F34D9B',
             'border': '#D7C9D0',
             'button': '#FFFFFF',
             'on_accent': '#FFFFFF',
             'hover': '#FBE3EE',
             'pressed': '#C93679',
             'log_text': '#F8EEF2'},
 'Sakura': {'background': '#21151F',
            'surface': '#342330',
            'text': '#F7EAF3',
            'log_background': '#190F18',
            'muted': '#C9AFC0',
            'accent_soft': '#D898BC',
            'accent': '#FF77B7',
            'border': '#75506B',
            'button': '#49313F',
            'on_accent': '#21151F',
            'hover': '#604253',
            'pressed': '#D898BC',
            'log_text': '#F7EAF3'},
 'Blackout': {'background': '#111111',
              'surface': '#202020',
              'text': '#F5F5F5',
              'log_background': '#080808',
              'muted': '#B8B8B8',
              'accent_soft': '#BBBBBB',
              'accent': '#EEEEEE',
              'border': '#555555',
              'button': '#303030',
              'on_accent': '#111111',
              'hover': '#444444',
              'pressed': '#BBBBBB',
              'log_text': '#F5F5F5'},
 'Cyberpunk': {'background': '#140B26',
               'surface': '#25143D',
               'text': '#F4EAFF',
               'log_background': '#0C0618',
               'muted': '#C0A9DA',
               'accent_soft': '#00DDEB',
               'accent': '#FF48CC',
               'border': '#705098',
               'button': '#382052',
               'on_accent': '#140B26',
               'hover': '#52316F',
               'pressed': '#00DDEB',
               'log_text': '#00DDEB'}}


def stylesheet(name):
    if name=='Studio':return QSS
    t=THEMES[name]
    # Override semantic UI surfaces and interaction states, not custom painters.
    return QSS+f"""
QWidget {{color:{t['text']};}}
QMainWindow, QWidget#shell {{background:{t['background']};}}
QFrame#panel, QFrame#deviceChannel {{background:{t['surface']};border-color:{t['border']};}}
QFrame#sidebar {{background:{t['background']};border-color:{t['border']};}}
QLabel[role="muted"], QTabBar::tab {{color:{t['muted']};}}
QPushButton, QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{background:{t['button']};color:{t['text']};border-color:{t['border']};}}
QPushButton:hover, QPushButton#nav:hover {{background:{t['hover']};border-color:{t['accent']};}}
QPushButton:pressed {{background:{t['pressed']};}}
QPushButton:checked, QPushButton#nav:checked, QPushButton#modeSegment:checked, QPushButton#masterPower:checked {{background:{t['accent']};color:{t['on_accent']};border-color:{t['accent_soft']};}}
QPushButton#nav {{color:{t['text']};}}
QPushButton:disabled {{color:{t['muted']};background:{t['background']};border-color:{t['border']};}}
QComboBox QAbstractItemView {{background:{t['surface']};color:{t['text']};selection-background-color:{t['accent']};selection-color:{t['on_accent']};}}
QLineEdit, QPlainTextEdit {{selection-background-color:{t['accent']};selection-color:{t['on_accent']};}}
QPlainTextEdit {{background:{t['log_background']};color:{t['log_text']};border:1px solid {t['border']};}}
QTabBar::tab {{background:{t['surface']};}}
QTabBar::tab:selected {{background:{t['hover']};color:{t['text']};border-bottom-color:{t['accent']};}}
QSlider::sub-page:horizontal, QCheckBox::indicator:checked {{background:{t['accent']};}}
QSlider::handle:horizontal {{background:{t['button']};border-color:{t['accent']};}}
QSlider::groove:horizontal {{background:{t['background']};border-color:{t['border']};}}
QCheckBox {{color:{t['text']};}}
QCheckBox:hover {{color:{t['accent']};}}
QToolTip {{background:{t['surface']};color:{t['text']};border-color:{t['border']};}}
"""
