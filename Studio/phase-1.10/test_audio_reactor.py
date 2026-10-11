"""Stage 1 display-only contracts: measured data, shared painter, no hardware."""
import math
import sys
import time
import unittest
from unittest.mock import patch
from PySide6.QtCore import QThread
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from music_coordination import MusicFrame
from studio_qt.widgets.audio_reactor import AudioReactor
import test_music_live as fixtures


def measured(energy=.04,bands=(.6,.3,.1),timestamp=10.):
    return MusicFrame((255,0,0),*bands,energy,False,timestamp)


class ReactorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);cls.app.setQuitOnLastWindowClosed(False)

    def setUp(self):
        self.widget=AudioReactor();self.widget.resize(720,240)
        self.errors=[];self.hook=patch.object(sys,'excepthook',lambda *exc:self.errors.append(exc[1]));self.hook.start()

    def tearDown(self):
        try:
            self.widget.close();self.widget.deleteLater();self.app.processEvents();self.assertEqual(self.errors,[])
        finally:self.hook.stop()

    def live(self):self.widget.enable_live();return self.widget

    def test_interpolation_is_rms_scaled_and_not_72_fft_bins(self):
        a,meters=AudioReactor.live_targets(measured(),10.)
        self.assertEqual(len(a),72);self.assertEqual(meters[:3],[.6,.3,.1])
        intensity=(20*math.log10(.04)+60)/48
        self.assertAlmostEqual(a[0],.6*intensity);self.assertAlmostEqual(a[-1],.1*intensity)
        self.assertTrue(all(x>=y for x,y in zip(a,a[1:])))
        self.assertAlmostEqual(meters[3],intensity)
        quiet,_=AudioReactor.live_targets(measured(energy=.004),10.)
        self.assertTrue(all(x<y for x,y in zip(quiet,a)))

    def test_silence_ignores_nonzero_band_proportions(self):
        for rms in (0.,1e-6,float('nan'),float('inf'),-.1):
            targets,meters=AudioReactor.live_targets(measured(energy=rms,bands=(1/3,)*3),10.)
            self.assertEqual(targets,[0.]*72);self.assertEqual(meters,[0.]*4)

    def test_attack_decay_and_peak_hold(self):
        w=self.live();w.live_frame=measured()
        target,_=w.live_targets(w.live_frame,10.)
        w.advance_live(.034,10.)
        self.assertGreater(w.levels[0],0);self.assertLess(w.levels[0],target[0])
        peak=w.peaks[0];w.live_frame=measured(energy=0)
        w.advance_live(.1,10.1)
        self.assertLess(w.levels[0],peak);self.assertEqual(w.peaks[0],peak)
        w.advance_live(.1,10.2);w.advance_live(.1,10.3)
        self.assertLess(w.peaks[0],peak);self.assertGreaterEqual(w.peaks[0],w.levels[0])
        self.assertEqual(w.phase,0);self.assertEqual(w.frames,0)

    def test_stale_data_decays_and_releases_timer(self):
        w=self.live();w.live_frame=measured();w.advance_live(.1,10.)
        before=list(w.levels);w.advance_live(.1,11.1)
        self.assertIsNone(w.live_frame);self.assertTrue(all(a<b for a,b in zip(w.levels,before)))
        self.assertTrue(any(w.levels))
        for n in range(100):w.advance_live(.1,11.2+n*.1)
        self.assertEqual(w.levels,[0.]*72);self.assertEqual(w.peaks,[0.]*72)
        self.assertEqual(w.meter_values,[0.]*4);self.assertFalse(w._live_timer.isActive())
        for timestamp in (float('nan'),8.,12.):
            self.assertEqual(w.live_targets(measured(timestamp=timestamp),10.),([0.]*72,[0.]*4))

    def test_reset_and_clear_have_no_synthetic_fallback(self):
        w=self.live();w.set_live_frame(measured(timestamp=time.monotonic()))
        w.advance_live(.1,time.monotonic());self.assertTrue(w._live_timer.isActive())
        w.clear_live_frame();self.assertTrue(any(w.levels));w.advance_live(.1,time.monotonic())
        w.reset_live();self.assertIsNone(w.live_frame)
        self.assertEqual(w.levels+w.peaks,[0.]*144);self.assertFalse(w._live_timer.isActive())
        QTest.qWait(80);self.assertEqual(w.levels,[0.]*72)

    def test_gui_timer_updates_only_display_state(self):
        w=self.live();threads=[];original=w.advance_live
        def advance(dt,now):threads.append(QThread.currentThread());original(dt,now)
        w.advance_live=advance;frame=measured(timestamp=time.monotonic());w.set_live_frame(frame)
        QTest.qWait(120)
        self.assertTrue(threads);self.assertTrue(all(thread==self.app.thread() for thread in threads))
        self.assertIs(w.live_frame,frame);self.assertTrue(any(w.levels));self.assertEqual(w.frames,0)
        w.reset_live()

    def test_live_uses_exact_same_painter_for_identical_display_data(self):
        demo=self.widget;live=AudioReactor();live.resize(demo.size());live.enable_live()
        try:
            levels=[.5]*72;peaks=[.6]*72;meters=[.2,.3,.1,.4]
            for widget in (demo,live):widget.meter_values=meters[:]
            width,height=demo.width(),demo.height();bottom=height-42
            extents={demo:bottom-20,live:(bottom-20)*.70}
            tops={widget:bottom-.5*extent for widget,extent in extents.items()}
            # Render into explicitly scaled images: grab() uses the screen DPR,
            # while QImage.copy() takes physical pixels, not logical coordinates.
            for scale in (1.,1.25,2.):
                with self.subTest(device_pixel_ratio=scale):
                    def render(widget):
                        image=QImage(round(width*scale),round(height*scale),QImage.Format.Format_ARGB32_Premultiplied)
                        image.setDevicePixelRatio(scale);image.fill(0);widget.render(image)
                        return image
                    def region(image,y,h):
                        start=round(y*scale);end=round((y+h)*scale)
                        return image.copy(0,start,image.width(),end-start)
                    for widget in (demo,live):widget.levels=levels[:];widget.peaks=peaks[:]
                    demo_image,live_image=render(demo),render(live)
                    # Identical inputs must draw identical meters and identical
                    # gradient pixels where both bars occupy the same area.
                    self.assertEqual(region(demo_image,height-34,34),region(live_image,height-34,34))
                    self.assertEqual(region(demo_image,bottom-48,30),region(live_image,bottom-48,30))
                    # Compare the actual top difference, not the shared lower fill.
                    self.assertNotEqual(region(demo_image,tops[demo]-4,tops[live]-tops[demo]+8),
                                        region(live_image,tops[demo]-4,tops[live]-tops[demo]+8))
                    for widget in (demo,live):widget.levels=[0.]*72;widget.peaks=[0.]*72
                    empty={widget:render(widget) for widget in (demo,live)}
                    x=round(12*scale);y=round((tops[demo]+tops[live])/2*scale)
                    self.assertNotEqual(demo_image.pixel(x,y),empty[demo].pixel(x,y),'DEMO bar must reach the taller extent')
                    self.assertEqual(live_image.pixel(x,y),empty[live].pixel(x,y),'LIVE must reserve space above its shorter bars')
                    # With bars/peaks absent, this compares only the intentional
                    # independently positioned LIVE curve versus DEMO's wave.
                    self.assertNotEqual(region(empty[demo],40,70),region(empty[live],40,70))
                    for widget,extent in extents.items():
                        widget.peaks=peaks[:];peak_image=render(widget)
                        peak_y=bottom-.6*extent-4
                        self.assertNotEqual(region(peak_image,math.floor(peak_y)-2,5),
                                            region(empty[widget],math.floor(peak_y)-2,5),
                                            'Peak markers must appear at the mode-specific bar extent')
                        self.assertEqual(len(widget.gradients),72)
        finally:live.reset_live();live.close();live.deleteLater()

    def test_demo_generation_is_unchanged(self):
        w=self.widget;dt=.034;w.advance(dt,intensity=.8)
        for i,value in enumerate(w.levels):
            target=(.10+.83*abs(math.sin(dt*1.6+i*.14))**2*abs(math.cos(i*.06-dt*.7)))*.8
            expected=.1+(target-.1)*(1-math.exp(-dt/(.045 if target>.1 else .28)))
            self.assertAlmostEqual(value,expected)
        self.assertEqual(w.frames,1);self.assertEqual(w.phase,dt)
        self.assertFalse(hasattr(w,'_live_timer'))
        before=w.levels[:];w.advance(dt,playing=False);self.assertEqual(w.levels,before)


class ReactorWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixtures.MusicTests.setUpClass()
    def setUp(self):
        self.f=fixtures.MusicTests();self.f.setUp();self.errors=[]
        self.hook=patch.object(sys,'excepthook',lambda *exc:self.errors.append(exc[1]));self.hook.start()
    def tearDown(self):
        try:self.f.tearDown();self.assertEqual(self.errors,[])
        finally:self.hook.stop()

    def test_audio_stop_resets_display_and_close_stops_visual_timer(self):
        w=self.f.window();w.start_music()
        self.f.wait(lambda:w.reactor.live_frame is not None and any(w.reactor.levels))
        w.stop_music()
        self.assertIsNone(w.reactor.live_frame);self.assertEqual(w.reactor.levels,[0.]*72)
        self.assertFalse(w.reactor._live_timer.isActive());self.f.wait(lambda:not w.runtime.busy)
        w.start_music();self.f.wait(lambda:any(w.reactor.levels))
        w.close();self.f.wait(lambda:w._cleanup_done and not w.runtime.busy)
        self.assertFalse(w.reactor._live_timer.isActive())

    def test_audio_device_loss_resets_display_without_lingering_timer(self):
        w=self.f.window();w.start_music();self.f.wait(lambda:any(w.reactor.levels))
        self.f.options['error']='default output device disconnected'
        self.f.wait(lambda:not w.runtime.busy and not w.c.adapter.music_active)
        self.assertIsNone(w.reactor.live_frame);self.assertEqual(w.reactor.levels,[0.]*72)
        self.assertFalse(w.reactor._live_timer.isActive())

    def test_lamp_disconnect_preserves_capture_and_other_device_routing(self):
        w=self.f.window();self.f.f.connect_corner(w.c.adapter);self.f.f.connect_hue(w.c.adapter)
        w.start_music();self.f.wait(lambda:w.reactor.live_frame is not None)
        w.disconnect_hue();self.f.wait(lambda:w.c.adapter.hue_status=='disconnected')
        self.assertTrue(w.runtime.wanted);self.assertTrue(w.c.adapter.music_active)
        self.assertTrue(w.c.adapter.connected)
        self.f.wait(lambda:w.reactor.live_frame is not None and any(w.reactor.levels))


if __name__=='__main__':unittest.main()
