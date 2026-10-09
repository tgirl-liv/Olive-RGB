"""Fake-transport screenshots only; no real HueDriver or BLE client is created."""
from pathlib import Path
from test_dual_live import DualTests


def capture():
    DualTests.setUpClass();fixture=DualTests();fixture.setUp()
    try:
        w=fixture.window();a=w.c.adapter
        output=Path(__file__).parent/'phase19-screenshots';output.mkdir(exist_ok=True)
        w.live_status.setText('TEST TRANSPORT · disconnected · no physical hardware')
        w.hue_status.setText('TEST TRANSPORT · Hue disconnected · no physical hardware')
        fixture.app.processEvents();w.grab().save(str(output/'disconnected.png'))
        fixture.connect_hue(a);w.c.select_channel('Hue')
        w.live_status.setText('TEST TRANSPORT · Corner disconnected · no physical hardware')
        w.hue_status.setText('TEST TRANSPORT · mock Hue connected alone · no physical hardware')
        fixture.app.processEvents();w.grab().save(str(output/'hue-only.png'))
        fixture.connect_corner(a)
        for width,height in [(1440,900),(1280,800),(1080,760),(800,600)]:
            w.resize(width,height);fixture.app.processEvents()
            w.live_status.setText('TEST TRANSPORT · mock Corner connected · no physical hardware')
            w.hue_status.setText('TEST TRANSPORT · mock Hue connected · no physical hardware')
            fixture.app.processEvents();w.grab().save(str(output/f'both-mocked-{width}x{height}.png'))
        w.resize(1440,900);w.c.navigate('Devices');fixture.app.processEvents()
        w.grab().save(str(output/'device-controls.png'));w.c.navigate('Studio')
        w.resize(1080,760);a.disconnect_hue();fixture.wait(lambda:a.hue_status=='disconnected')
        fixture.options['fail_connect']=True;a.connect_hue();fixture.wait(lambda:a.hue_status=='error')
        w.hue_status.setText('TEST TRANSPORT · '+a.hue_error);fixture.app.processEvents()
        w.grab().save(str(output/'hue-error-corner-connected.png'))
    finally:fixture.tearDown()

if __name__=='__main__':capture()
