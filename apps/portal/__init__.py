"""Portal: a silent, standalone showcase for the Universe 2026 badge."""
import os
import sys
import math

for _path in ('/system/apps/portal','/remote/apps/portal'):
    try:
        os.stat(_path + '/core.py')
        if _path not in sys.path: sys.path.insert(0,_path)
        break
    except OSError:
        pass

try:
    from .core import Portal
    from .display import PortalDisplay, PortalInputs
except (ImportError, ValueError, KeyError):
    from core import Portal
    from display import PortalDisplay, PortalInputs


class PortalBadgeApp:
    def __init__(self,namespace):
        self.badge = namespace['badge']
        self.state_api = namespace.get('State')
        saved = {}
        if self.state_api:
            try: self.state_api.load('portal',saved)
            except (OSError,ValueError): pass
        self.core = Portal(saved)
        self.last_saved = self.core.serialize()
        self.display = PortalDisplay(namespace)
        self.inputs = PortalInputs(self.badge,namespace)
        self.light_writer = getattr(self.badge,'caselights',None)
        self.last_lights = None
        self.draw_elapsed = 1
        self.save_elapsed = 0
        self.battery_elapsed = 10
        self.telemetry = {}

    def save(self):
        saved = self.core.serialize()
        if self.state_api and saved != self.last_saved:
            try:
                self.state_api.save('portal',saved)
                self.last_saved = saved
            except (OSError,ValueError): pass

    def lights(self,values):
        if self.light_writer and values != self.last_lights:
            try:
                self.light_writer(*values)
                self.last_lights = values
            except (OSError,ValueError,TypeError,AttributeError,RuntimeError):
                self.light_writer = None

    def update(self):
        dt = max(0,min(.5,self.badge.ticks_delta/1000))
        actions = self.inputs.read()
        self.battery_elapsed += dt
        if self.battery_elapsed >= 10:
            self.battery_elapsed = 0
            try: self.telemetry['battery'] = self.badge.battery_level()
            except (OSError,ValueError,AttributeError): self.telemetry['battery'] = None
        if self.core.motion:
            try:
                ax,ay,az = self.badge.imu()[:3]
                norm = math.sqrt(ax*ax+ay*ay+az*az)
                if norm > 0:
                    sign = -1 if self.badge.upside_down() else 1
                    self.telemetry['tilt'] = (ax/norm*sign,az/norm*sign)
            except (OSError,ValueError,TypeError,AttributeError,IndexError):
                self.telemetry.pop('tilt',None)
        self.core.update(actions,dt,self.telemetry,False)
        if actions: self.save_elapsed = 0
        else: self.save_elapsed += dt
        # Do not save automatic scene changes every cycle. Save preferences after
        # input settles, and the current scene on normal Home exit.
        if actions: self._save_pending = True
        if getattr(self,'_save_pending',False) and self.save_elapsed >= 1:
            self.save(); self._save_pending = False
        self.draw_elapsed += dt
        if self.draw_elapsed >= .05 or actions:
            self.draw_elapsed = 0
            self.display.draw(self.core.render())
            self.lights(self.core.levels)
        if 'home' in actions: self.save()


_app = None


def on_exit():
    if _app:
        _app.lights((0,0,0,0))
        _app.save()


def _start():
    global _app
    namespace = dict(globals())
    for name in ('badge','screen','color','vec2','shape','image','run','State','HIRES','VSYNC',
                 'BUTTON_UP','BUTTON_DOWN','BUTTON_LEFT','BUTTON_RIGHT','BUTTON_SELECT',
                 'BUTTON_BACK','BUTTON_MENU','BUTTON_HOME'):
        try: namespace[name] = eval(name)
        except NameError: pass
    if not all(key in namespace for key in ('badge','screen','run')): return
    namespace['badge'].mode(namespace['HIRES'] | namespace['VSYNC'])
    namespace['screen'] = eval('screen')
    # MonaOS leaves its menu in X2 antialiasing mode. Portal draws pixel
    # artwork and its own glyphs, so explicitly reset this inherited state.
    image_api = namespace.get('image')
    if image_api is not None and hasattr(image_api, 'OFF'):
        namespace['screen'].antialias = image_api.OFF
    namespace['badge'].default_clear = None
    try:
        from badgeware import State
        namespace['State'] = State
    except ImportError: pass
    _app = PortalBadgeApp(namespace)
    namespace['run'](_app.update)


_start()
