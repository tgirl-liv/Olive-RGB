"""Developer-only screenshots using fake hardware, labelled as such.
Requires the LIVE test dependencies. Never constructs a real Bluetooth client.
"""
from pathlib import Path
from test_corner_live import LiveTests
from studio_qt.live_window import LiveStudioWindow


def capture():
    LiveTests.setUpClass();fixture=LiveTests();fixture.setUp()
    try:
        w=LiveStudioWindow(worker_factory=fixture.factory);fixture.windows.append(w);fixture.adapters.append(w.c.adapter);w.show()
        output=Path(__file__).parent/'live-validation-screenshots';output.mkdir(exist_ok=True)
        fixture.app.processEvents();w.live_status.setText('TEST TRANSPORT · disconnected · no physical hardware')
        w.grab().save(str(output/'live-disconnected.png'))
        w.connect_corner();fixture.wait(lambda:w.c.adapter.connected)
        for size in [(1440,900),(1280,800),(1080,760),(800,600)]:
            w.resize(*size);fixture.app.processEvents()
            w.live_status.setText('TEST TRANSPORT · connected to a mock lamp · no physical hardware')
            fixture.app.processEvents();w.grab().save(str(output/f'live-mocked-{size[0]}x{size[1]}.png'))
        w.disconnect_corner();fixture.wait(lambda:w.c.adapter.status=='disconnected');fixture.lamps[0].failure=True
        w.connect_corner();fixture.wait(lambda:w.c.adapter.status=='error');w.resize(1080,760);fixture.app.processEvents()
        w.live_status.setText('TEST TRANSPORT · '+w.c.adapter.message);w.grab().save(str(output/'live-mocked-error.png'))
    finally:fixture.tearDown()

if __name__=='__main__':capture()
