"""Portal: four living worlds. Portable animation shared by badge and preview."""
import math

SCENES = ('space', 'abyss', 'city', 'reef')
NAMES = ('POCKET UNIVERSE', 'THE ABYSS', 'NEON SAN FRANCISCO', 'OCTOCAT REEF')
DESCRIPTIONS = (
    'An illuminated gateway, drifting stardust and a passing comet.',
    'Luminous jellyfish rise through the quiet of the deep ocean.',
    'The Golden Gate after dark. Traffic, fog and reflections on the bay.',
    'An Octocat diver, tropical fish, a forgotten wreck and unexpected visitors.',
)
ACCENTS = ('#b4b8ff', '#8aeeef', '#ffb398', '#cbffe8')
TAU = math.pi * 2


def clamp(value, low, high):
    return max(low, min(high, value))


class Portal:
    def __init__(self, state=None, config=None):
        saved = state if isinstance(state, dict) else {}
        scene = saved.get('scene', 0)
        self.scene = scene if type(scene) is int and 0 <= scene < 4 else 0
        self.held = saved.get('held') is True
        self.motion = saved.get('motion') is not False
        light = saved.get('light', 1)
        self.light = light if type(light) is int and 0 <= light <= 3 else 1
        duration = saved.get('duration', 28)
        self.duration = duration if duration in (18, 28, 45) else 28
        self.age = 0.0
        self.elapsed = 0.0
        self.hud = 5.0
        self.settings = False
        self.selected = 0
        self.transition = .45
        self.pending_scene = None
        self.surprise = -1.0
        self.surprise_kind = 0
        self.next_surprise = 8.0
        self.px = self.py = 0.0
        self.battery = None
        self.levels = (0, 0, 0, 0)

    def serialize(self):
        # Animation clocks are deliberately not saved: no continuous flash writes.
        return {'scene': self.scene, 'held': self.held, 'motion': self.motion,
                'light': self.light, 'duration': self.duration}

    def choose(self, scene):
        self.pending_scene = scene % 4
        self.transition = -.3
        self.hud = 3.5
        self.elapsed = 0

    def trigger(self):
        self.surprise = 0
        self.surprise_kind = (self.surprise_kind + 1) % 3
        self.next_surprise = self.age + 14

    def update(self, actions=(), dt=.05, telemetry=None, return_snapshot=True):
        dt = clamp(float(dt), 0, 1)
        telemetry = telemetry if isinstance(telemetry, dict) else {}
        self.battery = telemetry.get('battery', self.battery)
        for action in actions:
            if self.settings:
                if action in ('down', 'up'):
                    self.selected = (self.selected + (1 if action == 'down' else -1)) % 4
                elif action in ('back', 'menu', 'home'):
                    self.settings = False
                else:
                    activate = action in ('select', 'left', 'right')
                    if action.startswith('choice:') and action[7:].isdigit():
                        self.selected = clamp(int(action[7:]), 0, 3)
                        activate = True
                    if activate:
                        if self.selected == 0: self.light = (self.light + 1) % 4
                        elif self.selected == 1: self.motion = not self.motion
                        elif self.selected == 2: self.duration = (18, 28, 45)[((18, 28, 45).index(self.duration) + 1) % 3]
                        else: self.settings = False
                continue
            if action in ('select', 'portal:hold'):
                self.held = not self.held
                self.elapsed = 0
                self.hud = 3.5
            elif action in ('left', 'right'):
                current = self.pending_scene if self.pending_scene is not None else self.scene
                self.choose(current + (1 if action == 'right' else -1))
            elif action.startswith('scene:') and action[6:].isdigit():
                self.choose(int(action[6:]))
            elif action in ('up', 'portal:surprise'):
                self.trigger()
            elif action in ('down', 'menu', 'back', 'effects:open'):
                self.settings = True
                self.selected = 0
        self.age = (self.age + dt) % 100000
        if self.next_surprise - self.age > 99900:
            self.next_surprise -= 100000
        self.hud = max(0, self.hud - dt)
        if self.surprise >= 0:
            self.surprise += dt
            if self.surprise > 8: self.surprise = -1
        if self.age >= self.next_surprise:
            self.trigger()
        if self.pending_scene is not None:
            self.transition += dt
            if self.transition >= 0:
                self.scene = self.pending_scene
                self.pending_scene = None
                self.transition = .45
                self.surprise = -1
                self.next_surprise = self.age + 8
        elif self.transition > 0:
            self.transition = max(0, self.transition - dt)
        elif not self.held and not self.settings:
            self.elapsed += dt
            if self.elapsed >= self.duration: self.choose(self.scene + 1)
        # The adapter supplies bounded relative tilt; no assumptions about IMU units.
        tx, ty = 0, 0
        tilt = telemetry.get('tilt')
        if self.motion and isinstance(tilt, (tuple, list)) and len(tilt) >= 2:
            if all(isinstance(v, (int, float)) and math.isfinite(v) for v in tilt[:2]):
                tx, ty = clamp(tilt[0], -1, 1) * 5, clamp(tilt[1], -1, 1) * 4
        blend = min(1, dt * 3)
        self.px += (tx - self.px) * blend
        self.py += (ty - self.py) * blend
        cap = (0, .1, .22, .38)[self.light]
        if isinstance(self.battery, (int, float)) and self.battery < 20: cap *= .35
        self.levels = tuple(round(cap * (.3 + .35 * (1 + math.sin(self.age * .9 - i * .75 + self.scene))), 3) for i in range(4))
        return self.snapshot() if return_snapshot else None

    def labels(self):
        return ['CASE LIGHTS: ' + ('OFF', 'LOW', 'MEDIUM', 'BRIGHT')[self.light],
                'TILT: ' + ('ON' if self.motion else 'OFF'), 'SCENE LENGTH: %d SECONDS' % self.duration, 'DONE']

    def snapshot(self, include_content=False):
        options = ([{'label': label, 'action': 'choice:' + str(i)} for i, label in enumerate(self.labels())]
                   if self.settings else [{'label': 'Resume tour' if self.held else 'Hold this scene', 'action': 'portal:hold'},
                                         {'label': 'A little surprise', 'action': 'portal:surprise'}])
        return {'screen': 'portal-settings' if self.settings else 'portal-' + SCENES[self.scene],
                'title': ' '.join(word[:1] + word[1:].lower() for word in NAMES[self.scene].split()), 'description': DESCRIPTIONS[self.scene],
                'hint': 'SELECT: HOLD / TOUR · LEFT/RIGHT: SCENE · UP: SURPRISE · DOWN: SETTINGS',
                'theme': 'portal', 'scene': self.scene, 'scene_name': SCENES[self.scene],
                'held': self.held, 'progress': self.elapsed / self.duration,
                'selected_index': self.selected if self.settings else -1, 'options': options,
                'case_lights': list(self.levels), 'reminders_supported': False,
                'effects_open': self.settings, 'text': [NAMES[self.scene], 'HELD' if self.held else 'AUTO TOUR']}

    def render(self):
        scene = SCENES[self.scene]
        self.commands = [['image', '/portal-assets/' + scene + '.png', -8 + int(self.px), -8 + int(self.py), 336, 256]]
        (self.space, self.abyss, self.city, self.reef)[self.scene]()
        if self.settings:
            self.rect(10, 52, 300, 150, '#031324ec')
            self.text('PORTAL / SETTINGS', 23, 64, '#c8f8ed')
            for i, label in enumerate(self.labels()):
                if i == self.selected: self.rect(18, 83 + i * 25, 284, 22, '#294d66')
                self.text(('> ' if i == self.selected else '  ') + label, 24, 90 + i * 25, '#edf9ff')
        else:
            accent = ACCENTS[self.scene]
            if self.hud > 0:
                self.rect(0, 0, 320, 31, '#040c1dc0')
                self.text('PORTAL', 12, 9, '#f1f8ff')
                self.text('%02d / 04' % (self.scene + 1), 265, 9, accent)
                self.rect(0, 207, 320, 33, '#03101dc8')
                self.text(NAMES[self.scene], 12, 213, accent)
                self.text('HELD - SELECT TO TOUR' if self.held else 'SELECT TO HOLD THIS WORLD', 12, 226, '#cedde7')
            else:
                for i in range(4): self.rect(146 + i * 8, 231, 4, 2, accent if i == self.scene else '#71808c88')
                if self.held:
                    self.rect(297, 226, 2, 7, accent)
                    self.rect(302, 226, 2, 7, accent)
            if not self.held: self.rect(0, 239, int(320 * self.elapsed / self.duration), 1, accent)
        fade = (1 + self.transition / .3) if self.pending_scene is not None else self.transition / .45
        if fade > 0: self.rect(0, 0, 320, 240, '#020813%02x' % int(clamp(fade, 0, 1) * 255))
        return self.commands

    def rect(self, x, y, w, h, color): self.commands.append(['rect', int(x), int(y), int(w), int(h), color])
    def line(self, x, y, xx, yy, color): self.commands.append(['line', int(x), int(y), int(xx), int(yy), color])
    def ellipse(self, x, y, rx, ry, color, fill=True): self.commands.append(['ellipse', int(x), int(y), max(1, int(rx)), max(1, int(ry)), color, fill])
    def poly(self, points, color): self.commands.append(['poly', [[int(x), int(y)] for x, y in points], color, True])
    def text(self, value, x, y, color): self.commands.append(['text', value, x, y, 1, color])

    def particles(self, count, color, speed=4):
        for i in range(count):
            x = (i * 71 + math.sin(self.age * .25 + i) * 5 + self.px * (1 + i % 3)) % 320
            y = (i * 43 - self.age * speed * (1 + i % 3 * .25) + self.py) % 240
            self.rect(x, y, 1 + (i % 13 == 0), 1, color)

    def space(self):
        t = self.age
        cx, cy = 160 + self.px, 124 + self.py
        self.particles(27, '#a9c8e5', 1.1)
        for i in range(36):
            a = i * TAU / 36 + t * .075
            r = 80 + math.sin(t * .4 + i) * 1.3
            x, y = cx + math.cos(a) * r, cy + math.sin(a) * r
            self.line(x, y, cx + math.cos(a + .025) * r, cy + math.sin(a + .025) * r,
                      ('#c4deff', '#8a8eeb', '#e9cfff')[i % 3])
        for i in range(18):
            r = (i * 4.3 + t * 5) % 72
            a = i * 2.4 + t * .15
            self.rect(cx + math.cos(a) * r, cy + math.sin(a) * r * .85, 1, 1, '#dad8ff')
        for i in range(4):
            a = t * .13 + i * TAU / 4
            x, y = cx + math.cos(a) * 87, cy + math.sin(a) * 87
            self.ellipse(x, y, 3, 3, '#98bcff35')
            self.rect(x, y, 2, 2, '#eafcff')
        if 0 <= self.surprise < 5:
            u = self.surprise / 5
            x, y = -70 + u * 480, 18 + u * 154
            for i in range(14):
                self.line(x-i*4,y-i*1.6,x-i*4-4,y-i*1.6-2,'#bcdcff%02x' % (235-i*15))
            self.ellipse(x, y, 3, 2, '#b3eaff')
            self.rect(x, y, 1, 1, '#ffffff')

    def jelly(self, x, y, size, phase, violet=False):
        pulse = 1 + math.sin(self.age * 1.7 + phase) * .08
        r = size * pulse
        light = '#d2bbff' if violet else '#affcff'
        glow = '#ab7cff' if violet else '#55d9ed'
        self.ellipse(x, y, r * 1.45, r * .9, glow + '10')
        self.ellipse(x, y, r * 1.2, r * .65, glow + '22')
        for i in range(7):
            points = []
            sx = x + (i - 3) * size * .23
            for j in range(8):
                points.append((sx + math.sin(self.age * 1.2 + phase + j * .55 + i) * (2 + j * .5),
                               y + size * .2 + j * size * .24))
            for a,b in zip(points,points[1:]): self.line(*a, *b, glow + ('b0' if i % 2 else '65'))
        points = [(x-r,y+3)]
        for i in range(17):
            a = math.pi + i * math.pi / 16
            points.append((x + math.cos(a) * r, y + math.sin(a) * r * .75))
        points += [(x + r, y + 3)]
        self.poly(points, glow + '50')
        for i in range(16): self.line(*points[i+1], *points[i+2], light + 'c0')
        self.ellipse(x, y-2, r*.7, r*.24, light+'25')
        for i in range(5):
            xx = x + (i-2) * r * .37
            self.ellipse(xx,y+2,r*.19,3,light+'b0')
        self.ellipse(x-r*.25,y-r*.4,r*.26,2,'#f0ffffa0')

    def abyss(self):
        t = self.age
        self.particles(26, '#69b3cd80', 3)
        self.jelly(261 + math.sin(t*.3)*8 + self.px, 64 + math.sin(t*.5)*7, 14, 2, True)
        self.jelly(59 + math.sin(t*.25)*10 + self.px*1.4, 143 + math.sin(t*.4)*10, 21, 4, True)
        self.jelly(170 + math.sin(t*.22)*13 + self.px*2, 90 + math.sin(t*.45)*10 + self.py, 37, 0)
        if self.surprise >= 0:
            x = -90 + self.surprise * 65
            y = 183 + math.sin(self.surprise) * 8
            self.ray(x,y,38,'#4b9bb055')

    def city(self):
        t = self.age
        for i in range(24):
            x = (i * 47 + math.sin(t * .5 + i) * 3) % 320
            y = 166 + i * 29 % 61
            w = 3 + i % 9
            self.rect(x,y,w,1,('#e6a28d45','#8095c74a','#b66d9a65')[i%3])
        for i in range(11):
            x = (i * 31 + t * (8 if i%2 else -6)) % 348 - 14
            y = 179 - x * .14 + i%2 * 3
            self.rect(x+self.px,y+self.py,2,1,'#fff0be' if i%2 else '#fa6f91')
        # Thin transparent fog ribbons preserve the recognisable bridge silhouette.
        for i in range(4):
            x = ((t * (1.3+i*.2) + i*88) % 470) - 70
            self.ellipse(x,147+i*5,58+i*9,2+i%2,'#bfc5e00b')
        if 0 <= self.surprise < 6:
            for center in ((214,60,0),(125,44,1.3),(280,86,2.6)):
                x,y,delay=center
                age=self.surprise-delay
                if not 0 <= age < 2.5: continue
                radius=age*18
                alpha=int(220*(1-age/2.5))
                for i in range(14):
                    a=i*TAU/14
                    self.line(x+math.cos(a)*radius*.72,y+math.sin(a)*radius*.72+age*3,
                              x+math.cos(a)*radius,y+math.sin(a)*radius+age*3,
                              ('#f9c793','#c5bcff','#a0efdf')[int(delay)%3]+'%02x'%alpha)

    def fish(self, x, y, size, color, direction=1, stripe=False):
        d=direction
        self.poly([(x-size*d,y),(x-size*1.8*d,y-size*.7),(x-size*1.8*d,y+size*.7)],color)
        self.ellipse(x,y,size,size*.56,color)
        self.poly([(x-size*.3*d,y-size*.4),(x-size*.2*d,y-size),(x+size*.5*d,y-size*.4)],color)
        if stripe:
            self.line(x-size*.3*d,y-size*.5,x-size*.3*d,y+size*.5,'#fff8dd')
            self.line(x+size*.3*d,y-size*.45,x+size*.3*d,y+size*.45,'#fff8dd')
        self.rect(x+size*.65*d,y-1,1,1,'#0b263e')

    def ray(self,x,y,size,color):
        wing=math.sin(self.age*2)*size*.22
        self.poly([(x-size,y+wing),(x-size*.3,y-size*.25),(x,y-size*.18),
                   (x+size*.3,y-size*.25),(x+size,y+wing),(x+size*.25,y+size*.3),
                   (x,y+size*.16),(x-size*.25,y+size*.3)],color)
        self.line(x,y+size*.1,x-size*.2,y+size*1.15,color)

    def diver(self,x,y):
        t=self.age
        # Octocat's curled tentacles, cat ears and pale face remain recognizable.
        for i in range(5):
            sx=x+(i-2)*4
            curl=math.sin(t*1.5+i)*3
            self.poly([(sx-2,y+14),(sx+3,y+16),(sx+6+curl,y+26),
                       (sx+3+curl,y+30),(sx-1+curl,y+28),(sx+2+curl,y+25)],'#123242')
            self.line(sx,y+17,sx+3+curl,y+26,'#397280')
        self.ellipse(x,y+10,12,13,'#e5b661')
        self.ellipse(x+2,y+10,8,11,'#f6d782')
        self.rect(x-12,y+11,24,3,'#1b5262')
        self.ellipse(x,y-9,23,23,'#c3fff330')
        self.ellipse(x,y-9,22,22,'#91e4db',False)
        self.poly([(x-17,y-11),(x-16,y-29),(x-5,y-23),(x+6,y-23),(x+16,y-29),(x+18,y-9)],'#112a3a')
        self.ellipse(x,y-9,18,17,'#102d3d')
        self.ellipse(x,y-6,13,10,'#efc5a1')
        self.ellipse(x-5,y-7,2,4,'#173444')
        self.ellipse(x+5,y-7,2,4,'#173444')
        self.line(x-3,y,x,y+2,'#99666b');self.line(x,y+2,x+3,y,'#99666b')
        self.ellipse(x-9,y-21,6,2,'#efffffc0')
        self.line(x+19,y-5,x+24,y+3,'#75b5b6')
        self.ellipse(x+24,y+7,4,9,'#456e83')
        for i in range(5):
            rise=(t*11+i*17)%82
            self.ellipse(x+21+math.sin(t+i)*3,y-20-rise,1+i%3,1+i%3,'#c8fff08c',False)

    def reef(self):
        t=self.age
        self.particles(16,'#c4f5df75',4)
        for i in range(9):
            direction=1 if i%2 else -1
            x=((i*49+t*(6+i%3)*direction)%385)-32
            y=49+i*15+math.sin(t*1.2+i)*3
            self.fish(x+self.px*(1+i%2),y,4+i%3,('#ffd36b','#ff9469','#9ae4ed')[i%3],direction,i%3==1)
        for i in range(7):
            x=(t*3+i*9)%350-15
            self.fish(x,43+math.sin(i)*6,2,'#b9e7dc',1)
        self.diver(108+math.sin(t*.4)*10+self.px*2,117+math.sin(t*.9)*5+self.py)
        # Treasure chest stays part of the wreck, opening for one of the discoveries.
        self.rect(212,195,19,11,'#574b38');self.rect(213,196,17,3,'#bd9861')
        self.rect(215,195,2,11,'#e9c77a');self.rect(226,195,2,11,'#d1b978')
        if self.surprise >= 0:
            u=self.surprise
            if self.surprise_kind == 1:
                self.poly([(212,194),(212,187),(230,187),(231,194)],'#ba9b66')
                self.ellipse(222,192,17,9,'#f9e89d20')
                for i in range(12):
                    yy=194-(u*14+i*7)%60
                    xx=221+math.sin(i+u)*12
                    self.rect(xx,yy,2,2,'#ffe6a6')
            elif self.surprise_kind == 2:
                x=-38+u*50;y=62+math.sin(u)*8
                self.ellipse(x,y,15,10,'#719579')
                self.ellipse(x+2,y,11,8,'#a7bf85')
                for dx in (-9,8):
                    self.poly([(x+dx,y-5),(x+dx-8,y-15-math.sin(t*2)*3),(x+dx+4,y-10)],'#8bc5a5')
                    self.poly([(x+dx,y+5),(x+dx-7,y+16+math.sin(t*2)*3),(x+dx+4,y+10)],'#80bca1')
                self.ellipse(x+18,y,5,4,'#b7d6a3');self.rect(x+20,y-1,1,1,'#153f4d')
                self.line(x-7,y,x+9,y,'#638b70')
            else:
                x=360-u*52
                self.ray(x,169+math.sin(u)*9,28,'#24586ad0')
                self.ellipse(x-6,164+math.sin(u)*9,1,1,'#a9e1dc')
