import unittest
from studio_qt.backend_adapter import MockLightingAdapter,AudioMeters
from studio_qt.controller import StudioController


class AdapterTests(unittest.TestCase):
    def test_discovery_and_status_are_simulated(self):
        a=MockLightingAdapter();found=[];a.device_status.connect(found.append);a.discover_devices()
        self.assertEqual({s.name for s in found},{'Corner Lamp','Philips Hue'})
        self.assertTrue(all(s.simulated for s in found))
    def test_invalid_commands_do_not_mutate_state(self):
        a=MockLightingAdapter();original=a.state.channels['Hue'].color
        for color in ['#GG0000','abc','']:
            with self.assertRaises(ValueError):a.set_rgb('Hue',color)
        for level in [-.1,1.1,float('nan')]:
            with self.assertRaises(ValueError):a.set_brightness('Hue',level)
        with self.assertRaises(ValueError):a.select_mode('invalid')
        with self.assertRaises(ValueError):a.apply_scene('invalid')
        self.assertEqual(a.state.channels['Hue'].color,original)
    def test_close_rejects_commands_and_suppresses_meters(self):
        a=MockLightingAdapter();meters=[];a.audio_meters.connect(meters.append);a.close();a.close()
        with self.assertRaises(RuntimeError):a.set_power('Hue',True)
        a.publish_demo_meters(AudioMeters(0,0,0,0));self.assertEqual(meters,[])
        self.assertEqual(list(a.commands),[('close',)])
    def test_bounded_audit_log(self):
        a=MockLightingAdapter()
        for n in range(300):a.set_brightness('Hue',n/300)
        self.assertEqual(len(a.commands),256)
    def test_injected_adapter_and_ui_models_agree(self):
        a=MockLightingAdapter();c=StudioController(adapter=a)
        c.set('mode','Manual');c.set('master_brightness',.4);c.set_hex('#112233');c.channel('Hue','follow',False);c.select_scene('Ocean Breeze')
        self.assertEqual(c.state.mode,a.state.mode);self.assertEqual(c.state.master_brightness,a.state.master_brightness)
        self.assertEqual(c.state.channels,a.state.channels)

if __name__=='__main__':unittest.main()
