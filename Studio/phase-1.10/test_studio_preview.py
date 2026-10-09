"""Phase 1 state/UI tests: no real backend or settings imports."""
import ast
from pathlib import Path
import tkinter as tk
import unittest
from studio_ui.state import StudioState, NAVIGATION, SCENES
from studio_ui.app import StudioPreview


class StateTests(unittest.TestCase):
    def test_scene_respects_independent_channel(self):
        state=StudioState();state.channels['Hue'].follow=False
        original=state.channels['Hue'].color
        state.select_scene('Ocean Breeze')
        self.assertEqual(state.channels['Corner'].color,SCENES['Ocean Breeze'][0])
        self.assertEqual(state.channels['Hue'].color,original)

    def test_favorites_toggle_and_do_not_leak_between_sessions(self):
        state=StudioState();state.toggle_favorite('BRAT Energy')
        self.assertIn('BRAT Energy',state.favorites)
        state.toggle_favorite('BRAT Energy');self.assertNotIn('BRAT Energy',state.favorites)
        state.toggle_favorite('MGK After Dark')
        self.assertIn('MGK After Dark',StudioState().favorites)

    def test_navigation_and_inspector_are_independent(self):
        state=StudioState();state.select_inspector('Setup');state.select_channel('Corner')
        for name in NAVIGATION:state.navigate(name);self.assertEqual(state.page,name)
        self.assertEqual(state.inspector,'Setup');self.assertEqual(state.selected_channel,'Corner')
        with self.assertRaises(ValueError):state.navigate('Not a page')

    def test_transition_validation(self):
        state=StudioState();state.set_transition(2.5,'Linear')
        self.assertEqual((state.transition_seconds,state.transition_curve),(2.5,'Linear'))
        state.set_transition(8,'Smooth');self.assertEqual(state.transition_seconds,5)
        with self.assertRaises(ValueError):state.set_transition(1,'Invalid')

    def test_color_hex_and_hsv(self):
        state=StudioState();state.set_hex('00ff00')
        self.assertEqual(state.channels['Hue'].color,'#00FF00')
        self.assertAlmostEqual(state.get_hsv()[0],1/3)
        state.set_hsv(0,1,1);self.assertEqual(state.channels['Hue'].color,'#FF0000')
        with self.assertRaises(ValueError):state.set_hex('bad')

    def test_preview_has_no_backend_imports_or_io(self):
        base=Path(__file__).parent
        for file in [base/'studio_preview.py',*(base/'studio_ui').glob('*.py')]:
            tree=ast.parse(file.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node,ast.Import):
                    for name in node.names:self.assertIn(name.name.split('.')[0],{'tkinter','time','math','colorsys'})
                if isinstance(node,ast.ImportFrom):
                    self.assertIn(node.module.split('.')[0],{'tkinter','dataclasses','studio_ui','state','widgets','theme'})
                if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                    self.assertNotIn(node.func.id,{'open','exec','eval'})


class GuiTests(unittest.TestCase):
    def setUp(self):
        self.root=tk.Tk();self.root.attributes('-alpha',0)
        self.errors=[];self.root.report_callback_exception=lambda *args:self.errors.append(args)
        self.app=StudioPreview(self.root);self.root.update()

    def tearDown(self):
        self.app.close()
        self.assertEqual(self.errors,[])

    def test_scene_favorite_and_transition(self):
        self.app.set_transition_seconds(0);self.app.set_curve('Instant')
        self.app.select_scene('BRAT Energy')
        self.root.after_cancel(self.app.after_id)
        self.app._tick()
        self.assertEqual(self.app.display_colors['Corner'].upper(),SCENES['BRAT Energy'][0])
        self.app.toggle_favorite('BRAT Energy');self.app.toggle_filter()
        self.assertIn('BRAT Energy',self.app.scene_pads)

    def test_inspector_state_survives_navigation_and_small_layout(self):
        self.app.show_inspector('Setup');self.app.choose_channel('Corner')
        for page in NAVIGATION:self.app.navigate(page);self.root.update()
        self.assertEqual(self.app.state.inspector,'Setup')
        self.assertEqual(self.app.state.selected_channel,'Corner')
        self.root.geometry('800x600');self.app.navigate('Studio');self.root.update()
        self.assertGreater(self.app.center.winfo_width(),250)
        self.assertGreater(self.app.inspector_shell.winfo_width(),200)
        self.assertEqual(len(self.app.scene_pads),8)

    def test_mock_controls_and_bad_hex(self):
        self.app.toggle_master();self.app.set_brightness(.3);self.app.set_mode('Static')
        self.assertFalse(self.app.state.master_power)
        self.assertEqual(self.app.state.master_brightness,.3)
        self.app.hex_var.set('invalid');self.app.apply_hex()
        self.assertIn('HEX',self.app.color_error.cget('text'))
        self.app.swatch('#112233');self.assertEqual(self.app.hex_var.get(),'#112233')
        self.app.toggle_channel('Hue');self.assertFalse(self.app.state.channels['Hue'].power)

    def tick_once(self):
        if self.app.after_id:self.root.after_cancel(self.app.after_id)
        self.app._tick()

    def test_rgb_editor_mixer_and_channel_controls(self):
        self.app.set_color_mode('RGB')
        for var,value in zip(self.app.rgb_vars,('14','125','240')):var.set(value)
        self.app.apply_rgb()
        self.assertEqual(self.app.state.channels['Hue'].color,'#0E7DF0')
        self.app.rgb_vars[0].set('300');self.app.apply_rgb()
        self.assertIn('0–255',self.app.color_error.cget('text'))
        self.app.toggle_mixer();self.root.update()
        self.assertTrue(self.app.mixer.winfo_ismapped())
        self.app.mix_component(0,255)
        self.assertEqual(self.app.state.channels['Hue'].color,'#FF7DF0')
        self.app.set_channel_brightness('Hue',.42)
        self.assertEqual(self.app.inspect_brightness._value.get(),.42)
        self.assertEqual(self.app.channel_sliders['Hue']._value.get(),.42)
        self.app.set_follow('Hue',False)
        self.assertFalse(self.app.inspect_follow.get());self.assertFalse(self.app.channel_follow['Hue'].get())

    def test_canvas_controls_support_keyboard(self):
        slider=self.app.master_slider;slider.focus_force();self.root.update()
        before=self.app.state.master_brightness
        slider.event_generate('<Right>');self.root.update()
        self.assertGreater(self.app.state.master_brightness,before)
        slider.event_generate('<End>');self.root.update();self.assertEqual(self.app.state.master_brightness,1.)
        self.app.master_button.focus_force();self.root.update()
        before=self.app.state.master_power
        self.app.master_button.event_generate('<space>');self.root.update()
        self.assertNotEqual(self.app.state.master_power,before)

    def test_transition_replacement_and_reduced_motion(self):
        from unittest.mock import patch
        self.app.transition_preset(2)
        self.app.select_scene('Ocean Breeze')
        started=self.app.transition[0]
        with patch('studio_ui.app.time.monotonic',return_value=started+1):self.tick_once()
        intermediate=dict(self.app.display_colors)
        self.app.select_scene('BRAT Energy')
        self.assertEqual(self.app.transition[1],intermediate)
        self.assertEqual(self.app.transition[2]['Corner'],SCENES['BRAT Energy'][0])
        self.app.state.motion=False;self.tick_once()
        self.assertIsNone(self.app.transition)
        self.assertEqual(self.app.display_colors['Corner'].upper(),SCENES['BRAT Energy'][0])
        phase=self.app.phase;levels=list(self.app.reactor.levels)
        self.tick_once()
        self.assertEqual(self.app.phase,phase);self.assertEqual(self.app.reactor.levels,levels)

    def test_all_target_sizes_keep_primary_controls_available(self):
        for width,height in ((1440,900),(1280,800),(1080,760),(800,600)):
            self.root.geometry(f'{width}x{height}');self.root.update()
            self.assertGreater(self.app.master_slider.winfo_width(),30)
            self.assertTrue(self.app.play_button.winfo_ismapped())
            self.assertGreater(self.app.play_button.winfo_width(),50)
            for button in self.app.mode_buttons.values():self.assertTrue(button.winfo_ismapped())
            self.assertGreaterEqual(self.app.inspector_shell.winfo_width(),264)
            self.assertGreaterEqual(min(pad.winfo_width() for pad in self.app.scene_pads.values()),100)

    def test_reactor_retains_items_and_static_frame(self):
        reactor=self.app.reactor
        reactor.draw(8.,True,.7);items=reactor.find_all()
        reactor.draw(8.1,True,.7)
        self.assertEqual(reactor.find_all(),items)
        coords=[reactor.coords(item) for item in items]
        reactor.draw(8.1,True,.7)
        self.assertEqual([reactor.coords(item) for item in items],coords)

    def test_compact_nav_and_keyboard_scroll_reveal(self):
        self.root.geometry('800x600');self.root.update()
        self.assertEqual(self.app.sidebar.winfo_width(),72)
        slider=self.app.inspect_brightness
        slider.focus_force();self.root.update()
        canvas=self.app.inspect_scroll.canvas
        self.assertGreater(canvas.yview()[0],0)
        self.assertGreaterEqual(slider.winfo_rooty(),canvas.winfo_rooty())
        self.assertLessEqual(slider.winfo_rooty()+slider.winfo_height(),canvas.winfo_rooty()+canvas.winfo_height())
        self.app.nav_buttons['Scenes'].focus_force();self.root.update()
        self.assertIn('Scenes',self.app.nav_tooltip.cget('text'))

    def test_accordion_and_disabled_button_preserve_state(self):
        self.app.set_channel_brightness('Hue',.39)
        self.app.toggle_device_controls();self.root.update()
        self.assertFalse(self.app.control_body.winfo_ismapped())
        self.app.toggle_device_controls();self.root.update()
        self.assertEqual(self.app.inspect_brightness._value.get(),.39)
        button=self.app.master_button;value=self.app.state.master_power
        button.configure(state='disabled');button.invoke()
        self.assertEqual(self.app.state.master_power,value)
        button.configure(state='normal');button.invoke()
        self.assertNotEqual(self.app.state.master_power,value)

    def test_shutdown_cancels_owned_callback(self):
        callback=self.app.after_id
        self.assertIn(callback,self.root.tk.call('after','info'))
        self.app.close();self.app.close()
        self.assertTrue(self.app.closed);self.assertIsNone(self.app.after_id)
        self.assertNotIn(callback,self.root.tk.call('after','info'))


if __name__=='__main__':unittest.main()
