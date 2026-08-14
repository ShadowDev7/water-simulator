import math
import random
import sys
import pygame
import pymunk

WIDTH, HEIGHT = 1100, 750
FPS = 60

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED)
pygame.display.set_caption(
    "water plumber simulato r"
)
clock = pygame.time.Clock()
is_fullscreen = False

space = pymunk.Space()
space.gravity = (0, 850)  #down graviti

ui_wall = pymunk.Segment(space.static_body, (170, -200), (170, HEIGHT + 200), 5)
ui_wall.friction = 0.1
ui_wall.elasticity = 0.3
space.add(ui_wall)

COLLISION_WATER = 1
COLLISION_PIPE = 2

THEMES = {
    "BLUEPRINT": {
        "BG": (18, 22, 30),
        "GRID": (28, 35, 48),
        "WATER": (0, 185, 255),
        "WATER_GLOW": (180, 235, 255),
        "PIPE": (130, 145, 165),
        "VALVE": (230, 150, 40),
        "SINK": (0, 230, 130),
        "BARRIER": (200, 205, 220),
        "UI": (12, 15, 20),
        "ACCENT": (0, 210, 255),
        "CLOG": (255, 60, 80),
    },
    "NEON": {
        "BG": (5, 5, 12),
        "GRID": (20, 15, 35),
        "WATER": (255, 0, 128),
        "WATER_GLOW": (255, 150, 220),
        "PIPE": (120, 0, 255),
        "VALVE": (255, 200, 0),
        "SINK": (0, 255, 120),
        "BARRIER": (0, 240, 255),
        "UI": (10, 5, 20),
        "ACCENT": (255, 0, 255),
        "CLOG": (255, 30, 30),
    }
}
current_theme_name = "BLUEPRINT"
PALETTE = THEMES[current_theme_name]

water_particles = []
splash_particles = []
ripples = []
pipes = []
spouts = []
sinks = []
barriers = []
vortices = []
sponges = []
lasers = []
motors = []
score = 0
score_multiplier = 1
spawning_water = True
clog_warning = False
slow_motion = False
zoom_level = 1.0
grid_snap = False
flow_rate = 0.1  
viscosity = 1.0

def point_to_segment_distance(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    if dx == 0 and dy == 0:
        return math.hypot(px - ax, py - ay)
    t = ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)
    t = max(0, min(1, t))
    nx, ny = ax + t * dx, ay + t * dy
    return math.hypot(px - nx, py - ny)

def spawn_water(x, y, boost=False):
    mass = 0.12
    radius = 5.5
    inertia = pymunk.moment_for_circle(mass, 0, radius)
    body = pymunk.Body(mass, inertia)
    
    vx = random.uniform(-6, 6)
    vy = random.uniform(200, 350) if boost else random.uniform(0, 50)
    body.position = (x + vx, y)
    body.velocity = (vx * 10, vy)

    shape = pymunk.Circle(body, radius)
    shape.friction = 0.1 / viscosity
    shape.elasticity = 0.05
    shape.collision_type = COLLISION_WATER

    space.add(body, shape)
    water_particles.append({
        "body": body,
        "shape": shape,
        "hue": random.randint(180, 220)
    })


class Spout:
    def __init__(self, x, y, booster=False):
        self.x = x
        self.y = y
        self.booster = booster
        self.is_dragging = False
        self.spawn_accumulator = 0.0
    
    def draw(self, surface):
        color = (255, 100, 0) if self.booster else (0, 230, 120)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), 18)
        pygame.draw.rect(surface, PALETTE["WATER"], (int(self.x) - 10, int(self.y), 20, 22))

    def contains_point(self, pt):
        return math.hypot(pt[0] - self.x, pt[1] - self.y) <= 18


class Sink:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 260
        self.height = 60
        self.is_dragging = False

        self.body = pymunk.Body(body_type=pymunk.Body.STATIC)
        self.body.position = (self.x, self.y)
        self.shape = pymunk.Poly.create_box(self.body, (self.width, self.height))
        self.shape.sensor = True
        space.add(self.body, self.shape)

    def update_position(self, x, y):
        self.x = x
        self.y = y
        self.body.position = (x, y)

    def contains_point(self, pt):
        rect = pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)
        return rect.collidepoint(pt)

    def destroy(self):
        if self.shape in space.shapes:
            space.remove(self.shape)
        if self.body in space.bodies:
            space.remove(self.body)

    def draw(self, surface):
        rect = pygame.Rect(int(self.x - self.width // 2), int(self.y - self.height // 2), self.width, self.height)
        pygame.draw.rect(surface, PALETTE["SINK"], rect, border_radius=8)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=2, border_radius=8)
        font_s = pygame.font.SysFont("sans", 16, bold=True)
        txt_sink = font_s.render("DRAIN RECEIVER", True, (10, 30, 15))
        txt_rect = txt_sink.get_rect(center=rect.center)
        surface.blit(txt_sink, txt_rect)


class Barrier:
    def __init__(self, x, y, angle=0.0, glass=False):
        self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.body.position = (x, y)
        self.body.angle = angle
        self.scale_x = 1.0  
        self.scale_y = 1.0  
        self.glass = glass
        self.health = 100.0
        self.shape = None
        self.is_dragging = False

        space.add(self.body)
        self.build_geometry()

    def build_geometry(self):
        if self.shape and self.shape in space.shapes:
            space.remove(self.shape)

        base_length = 160
        base_thickness = 8
        L = base_length * self.scale_x
        thickness = base_thickness * self.scale_y

        self.shape = pymunk.Segment(self.body, (-L / 2, 0), (L / 2, 0), thickness / 2)
        self.shape.friction = 0.3
        self.shape.elasticity = 0.2
        self.shape.collision_type = COLLISION_PIPE
        space.add(self.shape)

    def destroy(self):
        if self.shape and self.shape in space.shapes:
            space.remove(self.shape)
        if self.body in space.bodies:
            space.remove(self.body)

    def contains_point(self, pt):
        p1 = self.body.local_to_world(self.shape.a)
        p2 = self.body.local_to_world(self.shape.b)
        return point_to_segment_distance(pt, (p1.x, p1.y), (p2.x, p2.y)) <= (self.shape.radius + 2)

    def draw(self, surface):
        p1 = self.body.local_to_world(self.shape.a)
        p2 = self.body.local_to_world(self.shape.b)
        color = (180, 220, 255) if self.glass else PALETTE["BARRIER"]
        pygame.draw.line(surface, color, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), int(self.shape.radius * 2))
        pygame.draw.circle(surface, PALETTE["ACCENT"], (int(p1.x), int(p1.y)), 4)
        pygame.draw.circle(surface, PALETTE["ACCENT"], (int(p2.x), int(p2.y)), 4)


class Vortex:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.is_dragging = False

    def contains_point(self, pt):
        return math.hypot(pt[0] - self.x, pt[1] - self.y) <= 25

    def draw(self, surface):
        pygame.draw.circle(surface, (150, 0, 255), (int(self.x), int(self.y)), 25, 3)
        pygame.draw.circle(surface, (200, 100, 255), (int(self.x), int(self.y)), 10)


class Sponge:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 60
        self.height = 60
        self.soaked = 0
        self.is_dragging = False

    def contains_point(self, pt):
        rect = pygame.Rect(self.x - self.width // 2, self.y - self.height // 2, self.width, self.height)
        return rect.collidepoint(pt)

    def draw(self, surface):
        rect = pygame.Rect(int(self.x - self.width // 2), int(self.y - self.height // 2), self.width, self.height)
        pygame.draw.rect(surface, (220, 200, 50), rect, border_radius=6)
        pygame.draw.rect(surface, (255, 255, 255), rect, width=1, border_radius=6)
        
        #absorbion counter
        font_s = pygame.font.SysFont("sans", 12, bold=True)
        txt = font_s.render(str(self.soaked), True, (50, 50, 0))
        txt_rect = txt.get_rect(center=rect.center)
        surface.blit(txt, txt_rect)


class Laser:
    def __init__(self, x1, y1, x2, y2):
        self.x1, self.y1 = x1, y1
        self.x2, self.y2 = x2, y2
        self.triggered = False
        self.is_dragging = False

    def contains_point(self, pt):
        return point_to_segment_distance(pt, (self.x1, self.y1), (self.x2, self.y2)) <= 8

    def draw(self, surface):
        color = (255, 50, 50) if not self.triggered else (50, 255, 50)
        pygame.draw.line(surface, color, (int(self.x1), int(self.y1)), (int(self.x2), int(self.y2)), 3)


class Pipe:
    def __init__(self, x, y, pipe_type="STRAIGHT", angle=0.0):
        self.pipe_type = pipe_type
        self.body = pymunk.Body(body_type=pymunk.Body.KINEMATIC)
        self.body.position = (x, y)
        self.body.angle = angle
        self.scale = 1.0  
        self.shapes = []
        self.is_dragging = False
        self.valve_open = True
        self.motorized = False

        space.add(self.body)
        self.build_geometry()

    def build_geometry(self):
        for s in list(self.shapes):
            if s in space.shapes:
                space.remove(s)
        self.shapes.clear()

        thickness = 8
        s_factor = self.scale

        if self.pipe_type == "STRAIGHT":
            L, W = 150 * s_factor, 52
            w1 = pymunk.Segment(self.body, (-L / 2, -W / 2), (L / 2, -W / 2), thickness / 2)
            w2 = pymunk.Segment(self.body, (-L / 2, W / 2), (L / 2, W / 2), thickness / 2)
            self.shapes.extend([w1, w2])

        elif self.pipe_type == "FUNNEL":
            L, W_in, W_out = 160 * s_factor, 80, 28
            w1 = pymunk.Segment(self.body, (-L / 2, -W_in / 2), (L / 2, -W_out / 2), thickness / 2)
            w2 = pymunk.Segment(self.body, (-L / 2, W_in / 2), (L / 2, W_out / 2), thickness / 2)
            self.shapes.extend([w1, w2])

        elif self.pipe_type == "ELBOW":
            R_out, R_in = 70 * s_factor, 22 * s_factor
            segments = 6
            for i in range(segments):
                a1 = (math.pi / 2) * (i / segments)
                a2 = (math.pi / 2) * ((i + 1) / segments)
                p1_o = (R_out * math.cos(a1) - 35 * s_factor, R_out * math.sin(a1) - 35 * s_factor)
                p2_o = (R_out * math.cos(a2) - 35 * s_factor, R_out * math.sin(a2) - 35 * s_factor)
                w_o = pymunk.Segment(self.body, p1_o, p2_o, thickness / 2)
                p1_i = (R_in * math.cos(a1) - 35 * s_factor, R_in * math.sin(a1) - 35 * s_factor)
                p2_i = (R_in * math.cos(a2) - 35 * s_factor, R_in * math.sin(a2) - 35 * s_factor)
                w_i = pymunk.Segment(self.body, p1_i, p2_i, thickness / 2)
                self.shapes.extend([w_o, w_i])

        elif self.pipe_type == "SPLITTER":
            w1 = pymunk.Segment(self.body, (0, -25 * s_factor), (-60 * s_factor, 45 * s_factor), thickness / 2)
            w2 = pymunk.Segment(self.body, (0, -25 * s_factor), (60 * s_factor, 45 * s_factor), thickness / 2)
            self.shapes.extend([w1, w2])

        elif self.pipe_type == "U-BEND":
            w1 = pymunk.Segment(self.body, (-45 * s_factor, -40 * s_factor), (-45 * s_factor, 40 * s_factor), thickness / 2)
            w2 = pymunk.Segment(self.body, (-45 * s_factor, 40 * s_factor), (45 * s_factor, 40 * s_factor), thickness / 2)
            w3 = pymunk.Segment(self.body, (45 * s_factor, 40 * s_factor), (45 * s_factor, -40 * s_factor), thickness / 2)
            self.shapes.extend([w1, w2, w3])

        elif self.pipe_type == "VALVE":
            L, W = 150 * s_factor, 52
            w1 = pymunk.Segment(self.body, (-L / 2, -W / 2), (L / 2, -W / 2), thickness / 2)
            w2 = pymunk.Segment(self.body, (-L / 2, W / 2), (L / 2, W / 2), thickness / 2)
            self.shapes.extend([w1, w2])
            if not self.valve_open:
                gate = pymunk.Segment(self.body, (0, -W / 2), (0, W / 2), thickness)
                self.shapes.append(gate)

        for s in self.shapes:
            s.friction = 0.2
            s.elasticity = 0.1
            s.collision_type = COLLISION_PIPE
            space.add(s)

    def toggle_valve(self):
        if self.pipe_type == "VALVE":
            self.valve_open = not self.valve_open
            self.build_geometry()

    def destroy(self):
        for s in self.shapes:
            if s in space.shapes:
                space.remove(s)
        if self.body in space.bodies:
            space.remove(self.body)

    def contains_point(self, pt):
        for s in self.shapes:
            p1 = self.body.local_to_world(s.a)
            p2 = self.body.local_to_world(s.b)
            if point_to_segment_distance(pt, (p1.x, p1.y), (p2.x, p2.y)) <= (s.radius + 2):
                return True
        return False

    def draw(self, surface):
        color = PALETTE["VALVE"] if self.pipe_type == "VALVE" else PALETTE["PIPE"]
        for s in self.shapes:
            p1 = self.body.local_to_world(s.a)
            p2 = self.body.local_to_world(s.b)
            pygame.draw.line(surface, color, (int(p1.x), int(p1.y)), (int(p2.x), int(p2.y)), int(s.radius * 2))

        if self.pipe_type == "VALVE":
            c = self.body.position
            v_color = (0, 230, 100) if self.valve_open else (255, 60, 60)
            pygame.draw.circle(surface, v_color, (int(c.x), int(c.y)), 12)
            pygame.draw.circle(surface, (255, 255, 255), (int(c.x), int(c.y)), 12, 2)


pipes.append(Pipe(280, 200, "FUNNEL", angle=0.4))
pipes.append(Pipe(520, 360, "VALVE", angle=-0.2))
barriers.append(Barrier(400, 520, angle=0.3))
spouts.append(Spout(220, 90))
sinks.append(Sink(780, 650))
vortices.append(Vortex(600, 300))
sponges.append(Sponge(350, 400))

selected_obj = None 
mouse_offset = (0, 0)
active_tool = "SELECT"

running = True
while running:
    #physics
    dt = (1.0 / FPS) if not slow_motion else (0.25 / FPS)
    space.step(dt)

    # pipe
    for p in pipes:
        if getattr(p, "motorized", False):
            p.body.angle += 0.02

    #vortex
    for v in vortices:
        for p_item in water_particles:
            pos = p_item["body"].position
            dist = math.hypot(v.x - pos.x, v.y - pos.y)
            if dist < 120 and dist > 5:
                fx = (v.x - pos.x) / dist * 400
                fy = (v.y - pos.y) / dist * 400
                p_item["body"].apply_force_at_local_point((fx, fy))

    # water
    if spawning_water:
        for spout in spouts:
            spout.spawn_accumulator += flow_rate * dt
            while spout.spawn_accumulator >= 1.0:
                spawn_water(spout.x, spout.y, boost=spout.booster)
                spout.spawn_accumulator -= 1.0

    # sinks
    for p_item in water_particles[:]:
        body = p_item["body"]
        pos = body.position
        
        # Check Sinks
        drained = False
        for sink in sinks:
            rect = pygame.Rect(sink.x - sink.width // 2, sink.y - sink.height // 2, sink.width, sink.height)
            if rect.collidepoint((pos.x, pos.y)):
                drained = True
                for _ in range(4):
                    splash_particles.append({
                        "x": pos.x, "y": pos.y,
                        "vx": random.uniform(-150, 150), "vy": random.uniform(-200, -50),
                        "life": 0.5
                    })
                ripples.append({"x": pos.x, "y": pos.y, "radius": 5, "alpha": 255})
                break
        if drained:
            space.remove(body, p_item["shape"])
            water_particles.remove(p_item)
            score += 1 * score_multiplier
            continue

        #oh my god this is getting tiring
        absorbed = False
        for sponge in sponges:
            rect = pygame.Rect(sponge.x - sponge.width // 2, sponge.y - sponge.height // 2, sponge.width, sponge.height)
            if rect.collidepoint((pos.x, pos.y)):
                absorbed = True
                sponge.soaked += 1
                break
        if absorbed:
            space.remove(body, p_item["shape"])
            water_particles.remove(p_item)
            continue

    # splashies
    for sp in splash_particles[:]:
        sp["x"] += sp["vx"] * dt
        sp["y"] += sp["vy"] * dt
        sp["vy"] += 800 * dt
        sp["life"] -= dt
        if sp["life"] <= 0:
            splash_particles.remove(sp)

    # Ripples update
    for r in ripples[:]:
        r["radius"] += 40 * dt
        r["alpha"] -= 255 * dt * 2
        if r["alpha"] <= 0:
            ripples.remove(r)

    # Check for Pressure Clog
    stuck_particles = sum(1 for p in water_particles if p["body"].velocity.length < 15)
    clog_warning = stuck_particles > 150 

    # input handling
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_F11:
                is_fullscreen = not is_fullscreen
                if is_fullscreen:
                    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.FULLSCREEN)
                else:
                    screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED)
                    
            elif event.key == pygame.K_SPACE:
                spawning_water = not spawning_water

            elif event.key == pygame.K_t: # Slow motion toggle feature
                slow_motion = not slow_motion

            elif event.key == pygame.K_n: # Neon theme toggle feature
                current_theme_name = "NEON" if current_theme_name == "BLUEPRINT" else "BLUEPRINT"
                PALETTE = THEMES[current_theme_name]

            elif event.key == pygame.K_c: # Duplicate selected object feature
                if selected_obj:
                    if isinstance(selected_obj, Pipe):
                        pipes.append(Pipe(selected_obj.body.position.x + 20, selected_obj.body.position.y + 20, selected_obj.pipe_type, selected_obj.body.angle))
                    elif isinstance(selected_obj, Barrier):
                        barriers.append(Barrier(selected_obj.body.position.x + 20, selected_obj.body.position.y + 20, selected_obj.body.angle, selected_obj.glass))
            
            # flow rate
            elif event.key == pygame.K_UP:
                flow_rate = min(20, flow_rate + 0.2)
            elif event.key == pygame.K_DOWN:
                flow_rate = max(0.1, flow_rate - 0.2)

            # resizing
            elif event.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_MINUS, pygame.K_LEFTBRACKET, pygame.K_RIGHTBRACKET):
                target = selected_obj if isinstance(selected_obj, (Pipe, Barrier)) else None
                if target:
                    if isinstance(target, Barrier):
                        if event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                            target.scale_x = min(3.5, target.scale_x + 0.15)
                        elif event.key == pygame.K_MINUS:
                            target.scale_x = max(0.3, target.scale_x - 0.15)
                        elif event.key == pygame.K_RIGHTBRACKET:
                            target.scale_y = min(3.5, target.scale_y + 0.15)
                        elif event.key == pygame.K_LEFTBRACKET:
                            target.scale_y = max(0.3, target.scale_y - 0.15)
                        target.build_geometry()
                    elif isinstance(target, Pipe):
                        if event.key in (pygame.K_EQUALS, pygame.K_PLUS):
                            target.scale = min(2.5, target.scale + 0.1)
                        elif event.key == pygame.K_MINUS:
                            target.scale = max(0.4, target.scale - 0.1)
                        target.build_geometry()

            elif event.key in (pygame.K_a, pygame.K_d):
                target = selected_obj if isinstance(selected_obj, (Pipe, Barrier)) else None
                if target:
                    rot = -0.15 if event.key == pygame.K_a else 0.15
                    target.body.angle += rot

        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos

            # Left Click
            if event.button == 1:
                if mx < 170: # Clicked in UI Panel
                    btn_labels = [
                        "+ STRAIGHT", "+ ELBOW", "+ FUNNEL", "+ VALVE", "+ SPLITTER", 
                        "+ U-BEND", "+ SPOUT", "+ BOOSTER", "+ DRAINER", "+ BARRIER", 
                        "+ GLASS", "+ VORTEX", "+ SPONGE", "ERASER", "CLEAR ALL"
                    ]
                    for i, label in enumerate(btn_labels):
                        btn_y = 20 + i * 32
                        if btn_y <= my <= btn_y + 28:
                            if label == "+ STRAIGHT": pipes.append(Pipe(350, 250, "STRAIGHT"))
                            elif label == "+ ELBOW": pipes.append(Pipe(350, 250, "ELBOW"))
                            elif label == "+ FUNNEL": pipes.append(Pipe(350, 250, "FUNNEL"))
                            elif label == "+ VALVE": pipes.append(Pipe(350, 250, "VALVE"))
                            elif label == "+ SPLITTER": pipes.append(Pipe(350, 250, "SPLITTER")) 
                            elif label == "+ U-BEND": pipes.append(Pipe(350, 250, "U-BEND")) 
                            elif label == "+ SPOUT": spouts.append(Spout(350, 250, booster=False))
                            elif label == "+ BOOSTER": spouts.append(Spout(350, 250, booster=True))
                            elif label == "+ DRAINER": sinks.append(Sink(350, 350))
                            elif label == "+ BARRIER": barriers.append(Barrier(350, 250, glass=False))
                            elif label == "+ GLASS": barriers.append(Barrier(350, 250, glass=True))
                            elif label == "+ VORTEX": vortices.append(Vortex(350, 250))
                            elif label == "+ SPONGE": sponges.append(Sponge(350, 250))
                            elif label == "ERASER": active_tool = "ERASER"
                            elif label == "CLEAR ALL":
                                water_particles.clear()
                                pipes.clear()
                                spouts.clear()
                                sinks.clear()
                                barriers.clear()
                                vortices.clear()
                                sponges.clear()
                                selected_obj = None
                            break
                else:
                    if active_tool == "ERASER":
                        # Delete whatever is clicked
                        for s in spouts[:]:
                            if s.contains_point((mx, my)): spouts.remove(s)
                        for sn in sinks[:]:
                            if sn.contains_point((mx, my)):
                                sn.destroy()
                                sinks.remove(sn)
                        for b in barriers[:]:
                            if b.contains_point((mx, my)):
                                b.destroy()
                                barriers.remove(b)
                        for p in pipes[:]:
                            if p.contains_point((mx, my)):
                                p.destroy()
                                pipes.remove(p)
                        for v in vortices[:]:
                            if v.contains_point((mx, my)): vortices.remove(v)
                        for sp in sponges[:]:
                            if sp.contains_point((mx, my)): sponges.remove(sp)
                    else:
                        found = False
                        for spout in reversed(spouts):
                            if spout.contains_point((mx, my)):
                                selected_obj = spout
                                spout.is_dragging = True
                                mouse_offset = (spout.x - mx, spout.y - my)
                                found = True
                                break
                        
                        if not found:
                            for sink in reversed(sinks):
                                if sink.contains_point((mx, my)):
                                    selected_obj = sink
                                    sink.is_dragging = True
                                    mouse_offset = (sink.x - mx, sink.y - my)
                                    found = True
                                    break

                        if not found:
                            for barrier in reversed(barriers):
                                if barrier.contains_point((mx, my)):
                                    selected_obj = barrier
                                    barrier.is_dragging = True
                                    mouse_offset = (barrier.body.position.x - mx, barrier.body.position.y - my)
                                    found = True
                                    break

                        if not found:
                            for v in reversed(vortices):
                                if v.contains_point((mx, my)):
                                    selected_obj = v
                                    v.is_dragging = True
                                    mouse_offset = (v.x - mx, v.y - my)
                                    found = True
                                    break

                        if not found:
                            for sp in reversed(sponges):
                                if sp.contains_point((mx, my)):
                                    selected_obj = sp
                                    sp.is_dragging = True
                                    mouse_offset = (sp.x - mx, sp.y - my)
                                    found = True
                                    break

                        if not found:
                            for pipe in reversed(pipes):
                                if pipe.contains_point((mx, my)):
                                    if pipe.pipe_type == "VALVE" and math.hypot(mx - pipe.body.position.x, my - pipe.body.position.y) < 18:
                                        pipe.toggle_valve()
                                    else:
                                        selected_obj = pipe
                                        pipe.is_dragging = True
                                        mouse_offset = (pipe.body.position.x - mx, pipe.body.position.y - my)
                                    break

            # Right Click: Delete objects directly
            elif event.button == 3:
                for spout in spouts[:]:
                    if spout.contains_point((mx, my)):
                        spouts.remove(spout)
                        if selected_obj == spout: selected_obj = None
                        break
                for sink in sinks[:]:
                    if sink.contains_point((mx, my)):
                        sink.destroy()
                        sinks.remove(sink)
                        if selected_obj == sink: selected_obj = None
                        break
                for barrier in barriers[:]:
                    if barrier.contains_point((mx, my)):
                        barrier.destroy()
                        barriers.remove(barrier)
                        if selected_obj == barrier: selected_obj = None
                        break
                for pipe in pipes[:]:
                    if pipe.contains_point((mx, my)):
                        pipe.destroy()
                        pipes.remove(pipe)
                        if selected_obj == pipe: selected_obj = None
                        break
                for v in vortices[:]:
                    if v.contains_point((mx, my)):
                        vortices.remove(v)
                        if selected_obj == v: selected_obj = None
                        break
                for sp in sponges[:]:
                    if sp.contains_point((mx, my)):
                        sponges.remove(sp)
                        if selected_obj == sp: selected_obj = None
                        break

            # Mouse Wheel: Rotate objects
            elif event.button in (4, 5):
                target = selected_obj if isinstance(selected_obj, (Pipe, Barrier)) else None
                if target:
                    rot = 0.15 if event.button == 4 else -0.15
                    target.body.angle += rot

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1 and selected_obj:
                if hasattr(selected_obj, "is_dragging"):
                    selected_obj.is_dragging = False
                selected_obj = None

        elif event.type == pygame.MOUSEMOTION:
            if selected_obj and getattr(selected_obj, "is_dragging", False):
                mx, my = event.pos
                if isinstance(selected_obj, (Pipe, Barrier)):
                    selected_obj.body.position = (mx + mouse_offset[0], my + mouse_offset[1])
                elif isinstance(selected_obj, Spout):
                    selected_obj.x = mx + mouse_offset[0]
                    selected_obj.y = my + mouse_offset[1]
                elif isinstance(selected_obj, Sink):
                    selected_obj.update_position(mx + mouse_offset[0], my + mouse_offset[1])
                elif isinstance(selected_obj, Vortex):
                    selected_obj.x = mx + mouse_offset[0]
                    selected_obj.y = my + mouse_offset[1]
                elif isinstance(selected_obj, Sponge):
                    selected_obj.x = mx + mouse_offset[0]
                    selected_obj.y = my + mouse_offset[1]

    #render
    screen.fill(PALETTE["BG"])

    # 1. Blueprint Grid Lines
    for x in range(0, WIDTH, 40):
        pygame.draw.line(screen, PALETTE["GRID"], (x, 0), (x, HEIGHT))
    for y in range(0, HEIGHT, 40):
        pygame.draw.line(screen, PALETTE["GRID"], (0, y), (WIDTH, y))

    #draw
    for sink in sinks: sink.draw(screen)
    for spout in spouts: spout.draw(screen)
    for barrier in barriers: barrier.draw(screen)
    for v in vortices: v.draw(screen)
    for sp in sponges: sp.draw(screen)
    for pipe in pipes: pipe.draw(screen)

    # Draw Splash Particles
    for sp in splash_particles:
        pygame.draw.circle(screen, PALETTE["WATER"], (int(sp["x"]), int(sp["y"])), 3)
    for r in ripples:
        surface_ring = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        pygame.draw.circle(surface_ring, (0, 230, 130, int(max(0, r["alpha"]))), (int(r["x"]), int(r["y"])), int(r["radius"]), 2)
        screen.blit(surface_ring, (0, 0))

    #Draw Cyan Box
    if selected_obj:
        if isinstance(selected_obj, Sink):
            rx = selected_obj.x - selected_obj.width // 2 - 6
            ry = selected_obj.y - selected_obj.height // 2 - 6
            rw = selected_obj.width + 12
            rh = selected_obj.height + 12
            pygame.draw.rect(screen, (0, 255, 255), (rx, ry, rw, rh), 2)
        elif isinstance(selected_obj, Spout):
            pygame.draw.rect(screen, (0, 255, 255), (selected_obj.x - 24, selected_obj.y - 20, 48, 48), 2)
        elif isinstance(selected_obj, Barrier):
            p1 = selected_obj.body.local_to_world(selected_obj.shape.a)
            p2 = selected_obj.body.local_to_world(selected_obj.shape.b)
            r = selected_obj.shape.radius + 6
            xs = [p1.x - r, p1.x + r, p2.x - r, p2.x + r]
            ys = [p1.y - r, p1.y + r, p2.y - r, p2.y + r]
            pygame.draw.rect(screen, (0, 255, 255), (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), 2)
        elif isinstance(selected_obj, Pipe):
            xs, ys = [], []
            for s in selected_obj.shapes:
                p1 = selected_obj.body.local_to_world(s.a)
                p2 = selected_obj.body.local_to_world(s.b)
                r = s.radius + 6
                xs.extend([p1.x - r, p1.x + r, p2.x - r, p2.x + r])
                ys.extend([p1.y - r, p1.y + r, p2.y - r, p2.y + r])
            if xs and ys:
                pygame.draw.rect(screen, (0, 255, 255), (min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)), 2)
        elif isinstance(selected_obj, Vortex):
            pygame.draw.rect(screen, (0, 255, 255), (selected_obj.x - 30, selected_obj.y - 30, 60, 60), 2)
        elif isinstance(selected_obj, Sponge):
            pygame.draw.rect(screen, (0, 255, 255), (selected_obj.x - 35, selected_obj.y - 35, 70, 70), 2)

    # the water particles
    for p_item in water_particles:
        body = p_item["body"]
        px, py = int(body.position.x), int(body.position.y)
        pygame.draw.circle(screen, PALETTE["WATER"], (px, py), 6)
        pygame.draw.circle(screen, PALETTE["WATER_GLOW"], (px - 2, py - 2), 2)

    # sidebar ui
    pygame.draw.rect(screen, PALETTE["UI"], (0, 0, 170, HEIGHT))
    pygame.draw.line(screen, PALETTE["ACCENT"], (170, 0), (170, HEIGHT), 2)

    font_ui = pygame.font.SysFont("monospace", 11, bold=True)
    screen.blit(font_ui.render("SPAWN TOOLS:", True, PALETTE["ACCENT"]), (10, 5))

    btn_labels = [
        "+ STRAIGHT", "+ ELBOW", "+ FUNNEL", "+ VALVE", "+ SPLITTER", 
        "+ U-BEND", "+ SPOUT", "+ BOOSTER", "+ DRAINER", "+ BARRIER", 
        "+ GLASS", "+ VORTEX", "+ SPONGE", "ERASER", "CLEAR ALL"
    ]
    for i, label in enumerate(btn_labels):
        btn_y = 20 + i * 32
        if "ERASER" in label:
            btn_color = (180, 50, 50) if active_tool == "ERASER" else (80, 30, 30)
        elif "CLEAR" in label:
            btn_color = (100, 30, 80)
        else:
            btn_color = (30, 38, 52)
            
        pygame.draw.rect(screen, btn_color, (10, btn_y, 150, 28), border_radius=4)
        pygame.draw.rect(screen, PALETTE["PIPE"], (10, btn_y, 150, 28), width=1, border_radius=4)
        screen.blit(font_ui.render(label, True, (220, 230, 240)), (14, btn_y + 7))

    # HUD Info Overlay
    flow_str = f"{flow_rate:g}" if flow_rate < 1.0 else f"{int(flow_rate)}"
    info = [
        f"SAVED WATER : {score}",
        f"PARTICLES   : {len(water_particles)}", 
        f"FLOW STATE  : {'ON' if spawning_water else 'OFF'}",
        f"SLOW-MO (T) : {'ON' if slow_motion else 'OFF'}",
        f"THEME (N)   : {current_theme_name}",
        f"FLOW RATE   : {flow_str} p/s",
        "-------------------",
        "L-CLICK: Drag/Spawn",
        "R-CLICK: Delete",
        "C-KEY : Duplicate",
        "T-KEY : Slow-Mo",
        "N-KEY : Neon Theme",
        "+ / - : Scale Length (X)",
        "[ / ] : Scale Thick (Y)",
        "WHEEL/A/D: Rotate",
        "SPACE: Toggle Flow",
        "UP/DOWN: Flow Rate",
        "F11: Fullscreen", 
    ]
    for i, line in enumerate(info):
        screen.blit(font_ui.render(line, True, (160, 175, 195)), (5, 505 + i * 14))

    # Clog Warning Banner
    font_s = pygame.font.SysFont("sans", 16, bold=True)
    if clog_warning:
        pygame.draw.rect(screen, PALETTE["CLOG"], (WIDTH // 2 - 160, 15, 320, 35), border_radius=6)
        warn_txt = font_s.render("CLOG", True, (255, 255, 255))
        screen.blit(warn_txt, (WIDTH // 2 - 140, 22))

    pygame.display.flip()

pygame.quit()
sys.exit()
