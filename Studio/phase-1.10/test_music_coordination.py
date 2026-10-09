"""No physical Bluetooth/audio use: shared-frame coordination regression tests."""
import colorsys
import unittest
from types import SimpleNamespace
from hue_driver import HueService
from music_coordination import AccentGenerator, MusicFrame, MusicLightingRouter, separation_value

STATE = dict(power=True, brightness=90, rgb=(15,180,80), mode='color', temperature=300)


def frame(rgb=(100,0,180), time=1., beat=False, energy=.04):
    return MusicFrame(rgb, .5, .3, .2, energy, beat, time)


class CoordinationTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.hue = HueService({}, STATE, True)
        self.router = MusicLightingRouter(SimpleNamespace(set_rgb=lambda *a, **k:self.calls.append((a,k))),self.hue)
        self.router.set_rgb(20,40,60)
        self.router.start_music()

    def test_primary_unchanged_and_distinct_related_accent(self):
        f=frame(); self.router.set_music_frame(f)
        self.assertEqual(self.calls[-1],(f.rgb, {'force':False}))
        accent=self.hue.master['rgb']
        primary_h=colorsys.rgb_to_hsv(*(x/255 for x in f.rgb))[0]
        accent_h=colorsys.rgb_to_hsv(*(x/255 for x in accent))[0]
        self.assertAlmostEqual((accent_h-primary_h)%1,60/360,delta=.01)
        self.assertNotEqual(f.rgb,accent)

    def test_same_color_exact_and_master_scaling(self):
        self.router.configure_music('Same Color',.25)
        self.router.set_music_frame(frame())
        self.assertEqual(self.hue.master['rgb'],frame().rgb)
        self.router.set_master(True,.5)
        self.assertEqual(self.calls[-1][0],(50,0,90))
        self.assertEqual(self.hue.desired()['brightness'],round(180/255*.5*254))

    def test_follow_off_keeps_manual_state(self):
        self.hue.update(follow=False)
        before=self.hue.desired()
        for t in range(20): self.router.set_music_frame(frame(time=t*.05,beat=t==3))
        self.assertEqual(before,self.hue.desired())
        self.assertEqual(self.hue.independent,STATE)

    def test_independent_restores_manual_and_freezes_audio_output(self):
        self.router.set_music_frame(frame())
        self.router.configure_music('Independent Devices',.5)
        self.assertEqual(self.calls[-1][0],(20,40,60))
        self.assertEqual(self.hue.desired()['color'],STATE['rgb'])
        count=len(self.calls)
        self.router.set_music_frame(frame((255,0,0)))
        self.assertEqual(len(self.calls),count)
        self.assertTrue(self.hue.follow)
        self.assertEqual(self.hue.independent,STATE)

    def test_stop_ignores_late_frames_and_restores_normal_routing(self):
        self.router.set_music_frame(frame())
        self.router.stop_music()
        self.assertEqual(self.calls[-1][0],(20,40,60))
        count=len(self.calls)
        self.router.set_music_frame(frame())
        self.assertEqual(len(self.calls),count)
        self.router.set_rgb(1,2,3)
        self.assertEqual(self.hue.master['rgb'],(1,2,3))
        self.assertNotIn('music_independent',self.hue.master)

    def test_disconnects_do_not_gate_output(self):
        self.hue.connected=False
        self.router.set_music_frame(frame())
        self.assertEqual(self.calls[-1][0],frame().rgb)
        self.hue.connected=True
        self.router.set_music_frame(frame((20,100,10),time=2))
        self.assertNotEqual(self.hue.master['rgb'],frame().rgb)

    def test_beats_attack_immediately_and_envelope_survives_coalescing(self):
        a=AccentGenerator(); b=AccentGenerator()
        for i in range(40):
            a.color(frame(time=i*.05),.25); b.color(frame(time=i*.05),.25)
        beat=a.color(frame(time=2,beat=True),.25)
        quiet=b.color(frame(time=2),.25)
        self.assertGreater(max(beat),max(quiet))
        for i in range(1,9):
            beat=a.color(frame(time=2+i*.05),.25)
            quiet=b.color(frame(time=2+i*.05),.25)
        self.assertGreater(max(beat),max(quiet))

    def test_smooth_hue_wrap_and_quiet_transition(self):
        a=AccentGenerator()
        a.color(frame((180,0,0),time=0),0)
        old=a.hue
        a.color(frame((0,180,0),time=.05,energy=.001),0)
        self.assertLess(abs((a.hue-old+.5)%1-.5),.03)
        self.assertGreater(abs(a.hue-old),0)

    def test_energy_darkness_and_complementary(self):
        a=AccentGenerator()
        for i in range(30): low=a.color(frame((30,0,0),time=i*.05),1)
        for i in range(30,60): high=a.color(frame((200,0,0),time=i*.05),1)
        self.assertGreater(max(high),max(low))
        self.assertEqual(high[0],0)
        self.assertAlmostEqual(high[1],high[2],delta=1)
        self.assertEqual(a.color(frame((0,0,0),time=3),1),(0,0,0))

    def test_settings_validation(self):
        for bad in (None,'bad',float('nan'),float('inf')): self.assertEqual(separation_value(bad),.25)
        self.assertEqual(separation_value(2),1)
        self.router.configure_music('bad',None)
        self.assertEqual(self.router.relationship,'Coordinated Colors')


class SharedAudioTests(unittest.TestCase):
    def test_single_capture_publishes_same_rgb_and_beat_to_all_consumers(self):
        import numpy as np
        import olive_rgb as app
        from unittest.mock import patch
        frames, meters, beats = [], [], []
        engine = app.MusicEngine(lambda *a:self.fail('legacy callback used twice'),
                                 lambda *a:meters.append(a), lambda:beats.append(True), lambda *_:None)
        engine.analysis_callback = frames.append
        engine._detect_beat = lambda energy: True
        engine.running = True
        class Recorder:
            count = 0
            def __enter__(self): return self
            def __exit__(self,*args): pass
            def record(self, numframes):
                self.count += 1
                if self.count == 2: engine.running = False
                wave = .08*np.sin(np.arange(numframes)*.1)
                return np.column_stack((wave,wave))
        recorder = Recorder()
        mic = SimpleNamespace(recorder=lambda **kw:recorder)
        with patch.object(app.sc,'default_speaker',return_value=SimpleNamespace(name='Mock audio')), \
             patch.object(app.sc,'get_microphone',return_value=mic) as capture, \
             patch.object(app.time,'sleep'):
            engine._run()
        self.assertEqual(capture.call_count,1)
        self.assertEqual(len(frames),2)
        self.assertEqual(len(beats),2)
        for f,meter in zip(frames,meters):
            self.assertTrue(f.beat)
            self.assertEqual(f.rgb,tuple(int(c) for c in meter[4]))
            self.assertEqual(f.energy,meter[3])
            self.assertAlmostEqual(f.bass+f.mids+f.treble,1.)


if __name__ == '__main__': unittest.main()
