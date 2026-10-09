"""Render workspace presets and aligned device rows; no saved user preferences."""
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from studio_qt.app import StudioWindow


def capture():
    app=QApplication([]);app.setStyle('Fusion');w=StudioWindow();w.show();w.c.set('motion',False)
    for _ in range(30):w.reactor.advance(1/30)
    output=Path(__file__).parent/'workspace-screenshots';output.mkdir(exist_ok=True)
    for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
        w.resize(*size)
        for preset in ['Studio','Music','Compact']:
            w.apply_preset(preset);w.c.navigate('Studio');app.processEvents();QTest.qWait(50)
            w.grab().save(str(output/f'{preset.lower()}-{size[0]}x{size[1]}.png'))
        w.apply_preset('Studio');w.c.navigate('Devices');app.processEvents()
        w.grab().save(str(output/f'device-alignment-{size[0]}x{size[1]}.png'))
    w.close();assert not w.timer.isActive()

if __name__=='__main__':capture()
