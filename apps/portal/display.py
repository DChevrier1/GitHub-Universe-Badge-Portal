"""Small native renderer. One background in memory; bounded color cache."""
import math
try:
    from .font5x7 import GLYPHS
except (ImportError, ValueError):
    try:
        from ..pipboy.font5x7 import GLYPHS
    except (ImportError, ValueError):
        from font5x7 import GLYPHS


class PortalDisplay:
    def __init__(self, namespace):
        self.screen = namespace['screen']
        self.color = namespace['color']
        self.vec2 = namespace['vec2']
        self.shape = namespace['shape']
        self.image = namespace.get('image')
        self.asset = None
        self.asset_name = None
        self.colors = {}
        self.glyphs = {}
        self.art_error = False
        for ch, rows in GLYPHS.items():
            runs = []
            for y, bits in enumerate(rows):
                x = 0
                while x < 5:
                    if bits & (16 >> x):
                        start = x
                        while x < 5 and bits & (16 >> x): x += 1
                        runs.append((start, y, x-start))
                    else: x += 1
            self.glyphs[ch] = runs

    def pen(self, value):
        if value not in self.colors:
            if len(self.colors) >= 192: self.colors.clear()
            channels = [int(value[i:i+2],16) for i in range(1,len(value),2)]
            self.colors[value] = self.color.rgb(*channels)
        self.screen.pen = self.colors[value]

    def text(self, text, x, y, scale):
        for ch in text:
            for xx, yy, w in self.glyphs.get(ch.upper(), self.glyphs.get('?', [])):
                self.screen.rectangle(int(x+xx*scale),int(y+yy*scale),int(w*scale),int(scale))
            x += 6*scale

    def picture(self, src, x, y):
        name = src.rsplit('/', 1)[-1]
        if name != self.asset_name:
            self.asset = None
            self.asset_name = name
            if name not in ('space.png','abyss.png','city.png','reef.png'):
                return
            if self.image:
                for base in ('/system/apps/portal/assets/','assets/','/remote/apps/portal/assets/'):
                    try:
                        self.asset = self.image.load(base + name)
                        break
                    except (OSError, ValueError, RuntimeError):
                        pass
            self.art_error = self.asset is None
        if self.asset is not None:
            self.pen('#ffffff')
            self.screen.blit(self.asset, self.vec2(x,y))
        else:
            self.pen('#04152a');self.screen.rectangle(0,0,320,240)

    def draw(self, commands):
        for command in commands:
            kind = command[0]
            if kind == 'image':
                self.picture(*command[1:4])
                continue
            self.pen(command[5] if kind == 'ellipse' else command[2] if kind == 'poly' else command[-1])
            if kind == 'rect': self.screen.rectangle(*command[1:5])
            elif kind == 'line': self.screen.line(*command[1:5])
            elif kind == 'text': self.text(*command[1:5])
            elif kind == 'poly':
                self.screen.shape(self.shape.custom([self.vec2(x,y) for x,y in command[1]]))
            elif kind == 'ellipse':
                x,y,rx,ry,col,fill = command[1:]
                if rx <= 2 and ry <= 2:
                    self.screen.rectangle(x-rx,y-ry,rx*2+1,ry*2+1)
                else:
                    points = [(int(x+rx*math.cos(i*math.pi/12)),int(y+ry*math.sin(i*math.pi/12))) for i in range(24)]
                    if fill: self.screen.shape(self.shape.custom([self.vec2(*p) for p in points]))
                    else:
                        for i,p in enumerate(points): self.screen.line(*p,*points[(i+1)%24])
        if self.art_error:
            self.pen('#ffffff');self.text('REINSTALL PORTAL ARTWORK', 18, 24, 1)


class PortalInputs:
    def __init__(self,badge,namespace):
        self.badge = badge
        self.keys = [(action,namespace.get('BUTTON_'+action.upper())) for action in
                     ('up','down','left','right','select','back','menu','home')]

    def read(self):
        return [action for action,key in self.keys if key is not None and self.badge.pressed(key)]
