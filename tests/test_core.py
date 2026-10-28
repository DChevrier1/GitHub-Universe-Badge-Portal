import unittest, json
from apps.portal.core import Portal, SCENES

class PortalTests(unittest.TestCase):

    def advance(self, app, seconds):
        for _ in range(int(seconds * 20)):
            app.update(dt=0.05, return_snapshot=False)

    def test_tour_visits_every_scene_and_hold_keeps_animation_alive(self):
        app = Portal({'duration': 18})
        seen = set()
        for _ in range(80 * 20):
            app.update(dt=0.05, return_snapshot=False)
            seen.add(app.scene)
        self.assertEqual(seen, set(range(4)))
        app.update(['select'], dt=0)
        original = app.scene
        first = app.render()
        self.advance(app, 60)
        self.assertEqual(app.scene, original)
        self.assertNotEqual(app.render(), first)
        restored = Portal(app.serialize())
        self.assertTrue(restored.held)
        self.assertEqual(restored.scene, original)
        restored.update(['select'], dt=0)
        self.advance(restored, 20)
        self.assertEqual(restored.scene, (original + 1) % 4)

    def test_manual_changes_preserve_hold_and_surprises_do_not_change_preferences(self):
        app = Portal({'held': True})
        for i in (1, 2, 3, 0):
            app.update(['right'], dt=0)
            self.advance(app, 1)
            self.assertEqual(app.scene, i)
            self.assertTrue(app.held)
        before = app.serialize()
        for _ in range(3):
            app.update(['up'], dt=0)
            self.assertEqual(app.surprise, 0)
            self.assertEqual(app.serialize(), before)
            self.advance(app, 2)
        self.assertEqual(app.surprise_kind, 0)

    def test_settings_pause_cycle_and_lights_off_is_persistent(self):
        app = Portal()
        self.advance(app, 1)
        app.update(['down'], dt=0)
        for _ in range(3):
            app.update(['select'], dt=0)
        self.assertEqual(app.light, 0)
        self.advance(app, 40)
        self.assertEqual(app.scene, 0)
        self.assertEqual(app.levels, (0, 0, 0, 0))
        restored = Portal(app.serialize())
        restored.update(dt=0.5)
        self.assertEqual(restored.levels, (0, 0, 0, 0))
        self.assertFalse(restored.snapshot()['reminders_supported'])

    def test_relative_tilt_is_smoothed_bounded_and_optional(self):
        app = Portal()
        app.update(dt=0.05, telemetry={'tilt': [1e+20, -1e+20]})
        self.assertTrue(0 < app.px < 5)
        self.assertTrue(-4 < app.py < 0)
        self.advance(app, 5)
        self.assertLess(abs(app.px), 0.01)
        app.update(dt=0.1, telemetry={'tilt': [float('nan'), 0]})
        self.assertLess(abs(app.px), 0.01)
        app.motion = False
        app.update(dt=1, telemetry={'tilt': [1, 1]})
        self.assertEqual((app.px, app.py), (0, 0))

    def test_every_scene_renders_bounded_commands_and_uses_its_own_art(self):
        for i, scene in enumerate(SCENES):
            app = Portal({'scene': i, 'held': True})
            self.advance(app, 1)
            for surprise in range(3):
                app.update(['up'], dt=0.1)
                self.advance(app, 1)
                commands = app.render()
                self.assertEqual(commands[0][1], '/portal-assets/' + scene + '.png')
                self.assertLess(len(commands), 330)
                self.assertLess(len(json.dumps(commands)), 30000)
            self.assertEqual(set(app.serialize()), {'scene', 'held', 'motion', 'light', 'duration'})

    def test_bad_saved_state_defaults_safely(self):
        app = Portal({'scene': 'reef', 'light': 999, 'duration': -5, 'held': 'yes'})
        self.assertEqual(app.serialize(), {'scene': 0, 'held': False, 'motion': True, 'light': 1, 'duration': 28})

    def test_automatic_surprises_continue_after_long_running_clock_wrap(self):
        app = Portal({'held': True})
        app.age = 99999.9
        app.next_surprise = 100002
        self.advance(app, 3)
        self.assertLess(app.age, 4)
        self.assertLess(app.surprise, 2)
        self.assertGreater(app.next_surprise, app.age)
        self.assertLess(app.next_surprise, 100)
