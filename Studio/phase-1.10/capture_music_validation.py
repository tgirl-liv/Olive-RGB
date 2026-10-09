"""Own-window screenshots with fake audio and fake hardware only."""
from pathlib import Path
from test_music_live import MusicTests
from PySide6.QtTest import QTest


def capture():
    MusicTests.setUpClass();f=MusicTests();f.setUp()
    try:
        w=f.window();a=w.c.adapter;f.f.connect_corner(a);f.f.connect_hue(a)
        w.start_music();f.wait(lambda:a.last_frame is not None);w.music_timer.stop()
        output=Path(__file__).parent/'phase110-screenshots';output.mkdir(exist_ok=True)
        for width,height in [(1440,900),(1280,800),(1080,760),(800,600)]:
            for page in ('Studio','Music'):
                w.resize(width,height);w.c.navigate(page);QTest.qWait(60)
                w.live_status.setText('TEST TRANSPORT · fake Corner connected')
                w.hue_status.setText('TEST TRANSPORT · fake Hue connected')
                w.music_status.setText('TEST AUDIO · synthetic fixture frame · no microphone / loopback / hardware accessed')
                w.grab().save(str(output/f'{page.lower()}-{width}x{height}.png'))
    finally:f.tearDown()

if __name__=='__main__':capture()
