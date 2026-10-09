"""Qt style sheet using the existing framework-neutral Studio palette."""
from studio_ui.theme import BG, PANEL, RAISED, LINE, TEXT, MUTED, PURPLE, PINK, CYAN, FRAME_MS

QSS = f'''
QWidget {{ color:{TEXT}; font-family:"Segoe UI"; font-size:12px; }}
QMainWindow, QWidget#shell {{ background:{BG}; }}
QFrame#panel {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #1d1e30,stop:1 #151827); border:1px solid {LINE}; border-radius:12px; }}
QFrame#sidebar {{ background:#101320; border-right:1px solid #25273d; }}
QLabel {{ background:transparent; border:0; }}
QLabel[role="title"] {{ font-size:25px; font-weight:700; }}
QLabel[role="heading"] {{ font-size:13px; font-weight:600; letter-spacing:.4px; }}
QLabel[role="muted"] {{ color:{MUTED}; font-size:11px; }}
QLabel[role="demo"] {{ color:{CYAN}; font-size:10px; font-weight:600; letter-spacing:1px; }}
QPushButton {{ background:{RAISED}; border:1px solid {LINE}; border-radius:7px; padding:7px 10px; }}
QPushButton:hover {{ background:#37304c; border-color:#766093; }}
QPushButton:pressed {{ background:#40295c; }}
QPushButton:checked {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #7132c9,stop:1 #9d3af3); border-color:{PURPLE}; }}
QPushButton:focus, QComboBox:focus, QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{ border:1px solid #e4ccff; }}
QPushButton:disabled {{ color:#656779; background:#1a1b27; border-color:#242537; }}
QPushButton#nav {{ text-align:left; border:1px solid transparent; background:transparent; padding:12px; font-size:13px; }}
QPushButton#nav:checked {{ background:#36265d; border-color:#5b3c8d; }}
QPushButton#nav:hover {{ background:#28223d; }}
QComboBox, QLineEdit, QSpinBox, QDoubleSpinBox {{ background:#202336; border:1px solid {LINE}; border-radius:6px; padding:5px; min-height:20px; selection-background-color:#773ad1; }}
QComboBox QAbstractItemView {{ background:#202336; selection-background-color:#643699; color:{TEXT}; }}
QSlider::groove:horizontal {{ background:#25283e; border:1px solid #393852; border-radius:5px; height:8px; }}
QSlider::sub-page:horizontal {{ background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #6935c8,stop:1 {PURPLE}); border-radius:4px; }}
QSlider::handle:horizontal {{ background:#f2eaff; border:2px solid #a78bd5; width:14px; margin:-5px 0; border-radius:8px; }}
QSlider::handle:horizontal:hover {{ border-color:#ecbcff; }}
QSlider::groove:vertical {{ background:#29263e; border-radius:5px; width:9px; }}
QSlider::add-page:vertical {{ background:qlineargradient(x1:0,y1:1,x2:0,y2:0,stop:0 #5a20a4,stop:1 #e9dfff); border-radius:5px; }}
QSlider::handle:vertical {{ background:#f5f0ff; border:2px solid #a78bd5; height:14px; margin:0 -4px; border-radius:8px; }}
QCheckBox {{ spacing:6px; background:transparent; }}
QCheckBox::indicator {{ width:15px; height:15px; border:1px solid #77678c; border-radius:4px; background:#242236; }}
QCheckBox::indicator:checked {{ background:{PURPLE}; border-color:#dcc2ff; }}
QCheckBox:focus {{ color:#dfcaff; }}
QScrollArea {{ background:transparent; border:0; }}
QScrollBar:vertical {{ width:7px; background:#141622; margin:0; }}
QScrollBar::handle:vertical {{ background:#49435e; border-radius:3px; min-height:28px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background:none; }}
QSplitter::handle {{ background:#111420; width:5px; }}
QTabWidget::pane {{ border:0; background:transparent; }}
QTabBar::tab {{ background:#202234; padding:9px 12px; color:{MUTED}; border-bottom:2px solid transparent; }}
QTabBar::tab:selected {{ background:#422773; color:{TEXT}; border-bottom-color:{PINK}; }}
QToolTip {{ background:#27243a; color:{TEXT}; border:1px solid #806696; padding:5px; }}
'''

QSS += """
QPushButton#masterPower {border-radius:15px;background:#242538;border:1px solid #5b4d73;}
QPushButton#masterPower:checked {background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #9b46fc,stop:1 #642eb6);border:1px solid #c595ff;}
QPushButton#masterPower:hover {border:2px solid #edd2ff;}
QPushButton#masterPower:focus {border:2px solid white;}
QPushButton#modeSegment {padding:8px 10px;border-radius:6px;color:#bdb4d2;}
QPushButton#modeSegment:checked {color:white;border-color:#c574ff;background:#7037b8;}
QPushButton#modeSegment:focus {border-color:white;}
QSlider#masterLevel::groove:horizontal {height:11px;border-radius:6px;}
QSlider#masterLevel::handle:horizontal {width:18px;margin:-5px 0;border-radius:10px;}
QPushButton#nav {padding:10px;}
QTabBar::tab {padding:10px 11px;min-width:40px;}
QSlider:focus {border:1px solid #ab82da;border-radius:5px;}
"""

# Phase 1.6: shared hierarchy and interaction states, without effect timers.
SPACING = (4, 8, 12, 16, 24)
ICON_SIZE = 22
QSS += """
QWidget {font-size:13px;}
QLabel[role="heading"] {font-size:13px;font-weight:600;letter-spacing:.5px;}
QLabel[role="muted"] {font-size:12px;color:#afa7c3;}
QLabel[role="demo"] {font-size:11px;letter-spacing:.6px;}
QLabel#brandMark {background:#7739ce;border-radius:12px;}
QFrame#panel {border-color:#333449;}
QFrame#deviceChannel {background:#1b1d2b;border:0;border-radius:9px;}
QPushButton {border-color:#3c3b50;}
QPushButton:hover {border-color:#9b76ba;background:#363049;}
QPushButton:focus {border:2px solid #e8d4ff;}
QPushButton#nav {padding:10px;text-align:left;}
QPushButton#nav:checked {border:1px solid #6f489b;border-left:3px solid #c17aff;background:#352553;}
QPushButton#nav:focus {border:2px solid #eed7ff;}
QPushButton#nav:disabled {color:#68677c;background:transparent;}
QSlider::handle:horizontal:hover {background:white;border-color:#efa5f6;}
QSlider::handle:horizontal:pressed {background:#eabaff;border-color:white;}
QSlider::handle:horizontal:disabled {background:#81738c;border-color:#63596b;}
QTabBar::tab {padding:10px 10px;min-width:38px;border-top-left-radius:6px;border-top-right-radius:6px;}
QTabBar::tab:hover {color:#f3e7ff;background:#332842;}
QTabBar::tab:selected {background:#4b2d75;border-bottom:2px solid #e871ed;}
QTabBar::tab:focus {border:1px solid white;}
QCheckBox:hover {color:#efd5ff;}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus {border-color:#e6c6ff;}
"""

QSS += """
QSplitter::handle:horizontal {background:#242337;width:8px;border-left:1px solid #37324b;border-right:1px solid #37324b;}
QSplitter::handle:hover {background:#65438b;}
QSplitter::handle:focus {background:#9465c5;border:1px solid #e8d0ff;}
"""
