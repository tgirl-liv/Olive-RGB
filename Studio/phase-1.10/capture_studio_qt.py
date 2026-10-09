"""Developer validation: render this preview's own widget, never the desktop."""
import json,os
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from studio_qt.app import StudioWindow
from studio_qt.backend_adapter import AudioMeters

def capture():
    app=QApplication([]);app.setStyle('Fusion');window=StudioWindow();window.show()
    output=Path(__file__).parent/'qt-screenshots';output.mkdir(exist_ok=True)
    scale=os.environ.get('QT_SCALE_FACTOR','1');results=[]
    for width,height in [(1440,900),(1280,800),(1080,760),(800,600)]:
        window.resize(width,height);app.processEvents();QTest.qWait(160)
        window.c.set('motion',False)
        # Deterministic synthetic snapshot, independent of frame timing.
        window.reactor.phase=0;window.reactor.levels=[.1]*72
        for _ in range(30):window.reactor.advance(1/30)
        bands=[sum(window.reactor.levels[i:i+24])/24 for i in (0,24,48)]
        window.c.adapter.publish_demo_meters(AudioMeters(*bands,sum(bands)/3))
        app.processEvents()
        name=f'qt-{width}x{height}-scale-{scale}.png'
        pixmap=window.grab();assert pixmap.save(str(output/name))
        results.append({'file':name,'logical_size':[window.width(),window.height()], 'pixel_size':[pixmap.width(),pixmap.height()], 'device_pixel_ratio':window.devicePixelRatioF(),'horizontal_scroll':window.pages.widget(0).horizontalScrollBar().maximum()})
        if width==800:
            window.c.navigate('Scenes');app.processEvents();window.grab().save(str(output/f'qt-scenes-800x600-scale-{scale}.png'))
            window.c.navigate('Studio')
    window.close();assert not window.timer.isActive()
    (output/f'metrics-scale-{scale}.json').write_text(json.dumps(results,indent=2),encoding='utf-8')

if __name__=='__main__':capture()
