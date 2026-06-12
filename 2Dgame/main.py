import math
import os
import sys
from array import array
from random import Random, choice, choices, randint, uniform

import pygame


SCREEN_WIDTH = 960
SCREEN_HEIGHT = 640
FPS = 60
PLAYER_SPEED = 260
PLAYER_SIZE = 34
PLAYER_MAX_HP = 100
TILE_SIZE = 64
BULLET_SPEED = 560
BULLET_SIZE = 10
BULLET_COOLDOWN = 0.22
SPEED_BONUS = 90
ENEMY_SIZE = 36
ENEMY_SPEED = 115
ENEMY_HP = 3
ENEMY_DAMAGE = 25
ENEMY_ATTACK_COOLDOWN = 0.8
SPAWN_COOLDOWN = 2.0
POWERUP_SIZE = 28
POWERUP_LIFETIME = 30.0
POWERUP_FLASH_TIME = 20.0
POWERUP_SPAWN_MIN = 4.0
POWERUP_SPAWN_MAX = 8.0
WEAPON_SPAWN_MIN = 7.0
WEAPON_SPAWN_MAX = 12.0
INVINCIBLE_TIME = 30.0
LASER_DURATION = 0.08
SAFE_BREAK_TIME = 10.0
KILL_TARGET_STEP = 15
SAFE_ZONE = pygame.Rect(336, 208, 288, 224)
WEAPON_TYPES = ("shotgun", "machine_gun", "laser")
REGULAR_POWERUP_TYPES = ("size", "speed", "damage", "heal", "super", "invincible")
BACKGROUND_PATH = os.path.join("assets", "battlefield.png")


class Player:
    def __init__(self, x, y):
        self.rect = pygame.Rect(x, y, PLAYER_SIZE, PLAYER_SIZE)
        self.color = (78, 161, 255)
        self.hp = PLAYER_MAX_HP
        self.aim_direction = pygame.Vector2(0, -1)
        self.shoot_timer = 0
        self.bullet_size_bonus = 0
        self.bullet_speed_bonus = 0
        self.damage_bonus = 0
        self.weapon_slots = ["normal", None]
        self.active_slot = 0
        self.weapon_levels = {
            "normal": {"size": 0, "speed": 0, "damage": 0},
            "shotgun": {"size": 0, "speed": 0, "damage": 0},
            "machine_gun": {"size": 0, "speed": 0, "damage": 0},
            "laser": {"size": 0, "speed": 0, "damage": 0},
        }
        self.super_damage_multiplier = 1.0
        self.super_fire_rate_multiplier = 1.0
        self.invincible_timer = 0

    def handle_movement(self, dt):
        keys = pygame.key.get_pressed()
        direction = pygame.Vector2(0, 0)

        if keys[pygame.K_w] or keys[pygame.K_UP]:
            direction.y -= 1
        if keys[pygame.K_s] or keys[pygame.K_DOWN]:
            direction.y += 1
        if keys[pygame.K_a] or keys[pygame.K_LEFT]:
            direction.x -= 1
        if keys[pygame.K_d] or keys[pygame.K_RIGHT]:
            direction.x += 1

        if direction.length_squared() > 0:
            direction = direction.normalize()

        self.rect.x += round(direction.x * PLAYER_SPEED * dt)
        self.rect.y += round(direction.y * PLAYER_SPEED * dt)
        self.rect.clamp_ip(pygame.Rect(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT))

    def update(self, dt):
        self.shoot_timer = max(0, self.shoot_timer - dt)
        self.invincible_timer = max(0, self.invincible_timer - dt)
        self.handle_movement(dt)
        self.update_aim()

    def update_aim(self):
        keys = pygame.key.get_pressed()
        keypad_direction = pygame.Vector2(0, 0)

        if keys[pygame.K_KP8]:
            keypad_direction.y -= 1
        if keys[pygame.K_KP2]:
            keypad_direction.y += 1
        if keys[pygame.K_KP4]:
            keypad_direction.x -= 1
        if keys[pygame.K_KP6]:
            keypad_direction.x += 1
        if keys[pygame.K_KP7]:
            keypad_direction = pygame.Vector2(-1, -1)
        if keys[pygame.K_KP9]:
            keypad_direction = pygame.Vector2(1, -1)
        if keys[pygame.K_KP1]:
            keypad_direction = pygame.Vector2(-1, 1)
        if keys[pygame.K_KP3]:
            keypad_direction = pygame.Vector2(1, 1)

        if keypad_direction.length_squared() > 0:
            self.aim_direction = keypad_direction.normalize()
            return

        mouse_direction = pygame.Vector2(pygame.mouse.get_pos()) - pygame.Vector2(self.rect.center)
        if mouse_direction.length_squared() > 16:
            self.aim_direction = mouse_direction.normalize()

    def can_shoot(self):
        return self.shoot_timer <= 0

    def shoot(self):
        self.shoot_timer = self.current_cooldown()
        size = self.current_bullet_size()
        speed = self.current_bullet_speed()
        damage = self.current_damage()
        weapon = self.current_weapon()

        if weapon == "shotgun":
            bullets = []
            for angle in (-24, -12, 0, 12, 24):
                direction = self.aim_direction.rotate(angle)
                bullets.append(Bullet(self.rect.center, direction, size * 2, speed, damage * 1.5))
            return bullets

        if weapon == "machine_gun":
            return [Bullet(self.rect.center, self.aim_direction, size * 1.5, speed, damage * 1.25)]

        if weapon == "laser":
            return [LaserShot(self.rect.center, self.aim_direction, size, damage * 0.75)]

        return [Bullet(self.rect.center, self.aim_direction, size, speed, damage)]

    def current_weapon(self):
        return self.weapon_slots[self.active_slot] or "normal"

    def switch_weapon(self):
        if self.weapon_slots[1] is None:
            return
        self.active_slot = 1 - self.active_slot

    def current_bullet_size(self):
        return BULLET_SIZE + self.bullet_size_bonus + self.weapon_levels[self.current_weapon()]["size"]

    def current_bullet_speed(self):
        speed_level = self.bullet_speed_bonus + self.weapon_levels[self.current_weapon()]["speed"]
        return BULLET_SPEED + speed_level * SPEED_BONUS

    def current_damage(self):
        damage_level = self.damage_bonus + self.weapon_levels[self.current_weapon()]["damage"]
        return (1 + damage_level) * self.super_damage_multiplier

    def current_cooldown(self):
        fire_rate = self.super_fire_rate_multiplier
        if self.current_weapon() == "machine_gun":
            fire_rate *= 2
        return BULLET_COOLDOWN / fire_rate

    def take_damage(self, amount):
        if self.invincible_timer > 0:
            return
        self.hp = max(0, self.hp - amount)

    def apply_powerup(self, powerup_type):
        if powerup_type == "size":
            self.bullet_size_bonus += 1
        elif powerup_type == "speed":
            self.bullet_speed_bonus += 1
        elif powerup_type == "damage":
            self.damage_bonus += 1
        elif powerup_type == "heal":
            self.hp = min(PLAYER_MAX_HP, self.hp + 50)
        elif powerup_type in WEAPON_TYPES:
            self.pick_weapon(powerup_type)
        elif powerup_type == "super":
            self.super_damage_multiplier *= 3
            self.super_fire_rate_multiplier *= 3
        elif powerup_type == "invincible":
            self.invincible_timer = INVINCIBLE_TIME

    def pick_weapon(self, weapon_type):
        if weapon_type in self.weapon_slots:
            self.upgrade_weapon(weapon_type)
            return

        if self.weapon_slots[1] is None:
            self.weapon_slots[1] = weapon_type
            self.active_slot = 1
            return

        self.weapon_slots[self.active_slot] = weapon_type
        self.weapon_levels[weapon_type] = {"size": 0, "speed": 0, "damage": 0}

    def upgrade_weapon(self, weapon_type):
        self.weapon_levels[weapon_type]["size"] += 1
        self.weapon_levels[weapon_type]["speed"] += 1
        self.weapon_levels[weapon_type]["damage"] += 1

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=8)
        border_color = (255, 238, 128) if self.invincible_timer > 0 else (18, 43, 82)
        pygame.draw.rect(surface, border_color, self.rect, width=3, border_radius=8)

        aim_end = pygame.Vector2(self.rect.center) + self.aim_direction * 34
        pygame.draw.line(surface, (102, 217, 255), self.rect.center, aim_end, width=3)
        pygame.draw.circle(surface, (102, 217, 255), aim_end, 4)


class Bullet:
    def __init__(self, center, direction, size, speed, damage):
        self.rect = pygame.Rect(0, 0, round(size), round(size))
        self.rect.center = center
        self.direction = pygame.Vector2(direction)
        self.speed = speed
        self.damage = damage
        self.color = (70, 190, 255)

    def update(self, dt):
        self.rect.x += round(self.direction.x * self.speed * dt)
        self.rect.y += round(self.direction.y * self.speed * dt)

    def is_off_screen(self):
        return (
            self.rect.right < 0
            or self.rect.left > SCREEN_WIDTH
            or self.rect.bottom < 0
            or self.rect.top > SCREEN_HEIGHT
        )

    def draw(self, surface):
        pygame.draw.rect(surface, self.color, self.rect, border_radius=4)


class LaserShot:
    def __init__(self, start, direction, thickness, damage):
        self.start = pygame.Vector2(start)
        self.direction = pygame.Vector2(direction)
        self.end = get_ray_end(self.start, self.direction)
        self.thickness = max(2, round(thickness))
        self.damage = damage
        self.timer = LASER_DURATION
        self.hit_applied = False

    def update(self, dt):
        self.timer -= dt

    def is_done(self):
        return self.timer <= 0

    def hits(self, rect):
        expanded = rect.inflate(self.thickness, self.thickness)
        return expanded.clipline(self.start, self.end)

    def draw(self, surface):
        pygame.draw.line(surface, (112, 224, 255), self.start, self.end, width=self.thickness)
        pygame.draw.line(surface, (235, 252, 255), self.start, self.end, width=max(1, self.thickness // 3))


class Enemy:
    def __init__(self, x, y, hp):
        self.rect = pygame.Rect(x, y, ENEMY_SIZE, ENEMY_SIZE)
        self.hp = hp
        self.attack_timer = 0

    def update(self, dt, player):
        self.attack_timer = max(0, self.attack_timer - dt)

        direction = pygame.Vector2(player.rect.center) - pygame.Vector2(self.rect.center)
        if direction.length_squared() > 0:
            direction = direction.normalize()
            self.rect.x += round(direction.x * ENEMY_SPEED * dt)
            self.rect.y += round(direction.y * ENEMY_SPEED * dt)

        if self.rect.colliderect(player.rect) and self.attack_timer <= 0:
            if player.invincible_timer > 0:
                self.take_hit(max(1, player.current_damage()))
            else:
                player.take_damage(ENEMY_DAMAGE)
            self.attack_timer = ENEMY_ATTACK_COOLDOWN

    def take_hit(self, damage):
        self.hp -= damage

    def is_dead(self):
        return self.hp <= 0

    def draw(self, surface):
        pygame.draw.rect(surface, (221, 63, 63), self.rect, border_radius=7)
        pygame.draw.rect(surface, (90, 20, 26), self.rect, width=3, border_radius=7)


class PowerUp:
    COLORS = {
        "size": (93, 217, 255),
        "speed": (255, 207, 79),
        "damage": (181, 116, 255),
        "heal": (82, 215, 117),
        "shotgun": (255, 149, 79),
        "machine_gun": (255, 224, 102),
        "laser": (107, 232, 255),
        "super": (255, 102, 214),
        "invincible": (255, 245, 128),
    }
    LABELS = {
        "size": "B",
        "speed": "S",
        "damage": "D",
        "heal": "H",
        "shotgun": "SG",
        "machine_gun": "MG",
        "laser": "L",
        "super": "SS",
        "invincible": "I",
    }

    def __init__(self, powerup_type, x, y):
        self.type = powerup_type
        self.rect = pygame.Rect(x, y, POWERUP_SIZE, POWERUP_SIZE)
        self.age = 0

    def update(self, dt):
        self.age += dt

    def is_expired(self):
        return self.age >= POWERUP_LIFETIME

    def should_draw(self):
        if self.age < POWERUP_FLASH_TIME:
            return True

        flash_progress = (self.age - POWERUP_FLASH_TIME) / (POWERUP_LIFETIME - POWERUP_FLASH_TIME)
        flashes_per_second = 4 + flash_progress * 14
        return int((self.age - POWERUP_FLASH_TIME) * flashes_per_second) % 2 == 0

    def is_weapon(self):
        return self.type in WEAPON_TYPES

    def draw(self, surface, font):
        if not self.should_draw():
            return
        pygame.draw.rect(surface, self.COLORS[self.type], self.rect, border_radius=6)
        pygame.draw.rect(surface, (17, 24, 39), self.rect, width=2, border_radius=6)
        text = font.render(self.LABELS[self.type], True, (17, 24, 39))
        surface.blit(text, text.get_rect(center=self.rect.center))


class SoundManager:
    def __init__(self):
        self.enabled = pygame.mixer.get_init() is not None
        self.sounds = {}
        if not self.enabled:
            return

        self.sounds = {
            "normal": self.make_tone(520, 0.05, 0.28),
            "shotgun": self.make_noise_burst(0.08, 0.34),
            "machine_gun": self.make_tone(760, 0.035, 0.22),
            "laser": self.make_sweep(920, 360, 0.09, 0.26),
            "hit": self.make_tone(170, 0.045, 0.36),
            "pickup": self.make_sweep(520, 880, 0.1, 0.25),
            "switch": self.make_tone(360, 0.04, 0.2),
        }

    def play_weapon(self, weapon):
        self.play(weapon)

    def play(self, name):
        if self.enabled and name in self.sounds:
            self.sounds[name].play()

    def make_tone(self, frequency, duration, volume):
        sample_rate = 44100
        samples = int(sample_rate * duration)
        data = array("h")
        for i in range(samples):
            fade = 1 - i / samples
            value = math.sin(2 * math.pi * frequency * i / sample_rate)
            data.append(int(32767 * volume * fade * value))
        return pygame.mixer.Sound(buffer=data)

    def make_sweep(self, start_frequency, end_frequency, duration, volume):
        sample_rate = 44100
        samples = int(sample_rate * duration)
        data = array("h")
        phase = 0
        for i in range(samples):
            t = i / samples
            frequency = start_frequency + (end_frequency - start_frequency) * t
            phase += 2 * math.pi * frequency / sample_rate
            fade = 1 - t
            data.append(int(32767 * volume * fade * math.sin(phase)))
        return pygame.mixer.Sound(buffer=data)

    def make_noise_burst(self, duration, volume):
        sample_rate = 44100
        samples = int(sample_rate * duration)
        data = array("h")
        for i in range(samples):
            t = i / samples
            fade = (1 - t) ** 2
            value = uniform(-1, 1)
            data.append(int(32767 * volume * fade * value))
        return pygame.mixer.Sound(buffer=data)


def get_ray_end(start, direction):
    distances = []
    if direction.x > 0:
        distances.append((SCREEN_WIDTH - start.x) / direction.x)
    elif direction.x < 0:
        distances.append((0 - start.x) / direction.x)
    if direction.y > 0:
        distances.append((SCREEN_HEIGHT - start.y) / direction.y)
    elif direction.y < 0:
        distances.append((0 - start.y) / direction.y)

    distance = min(value for value in distances if value > 0)
    return start + direction * distance


def spawn_enemies(kill_count, use_base_count=False):
    enemies = []
    bonus = kill_count // 5
    enemy_count = randint(1, 3) if use_base_count else randint(1, 3) + bonus
    enemy_hp = ENEMY_HP + bonus

    for _ in range(enemy_count):
        side = choice(("top", "right", "bottom", "left"))
        if side == "top":
            x, y = randint(0, SCREEN_WIDTH - ENEMY_SIZE), 0
        elif side == "right":
            x, y = SCREEN_WIDTH - ENEMY_SIZE, randint(0, SCREEN_HEIGHT - ENEMY_SIZE)
        elif side == "bottom":
            x, y = randint(0, SCREEN_WIDTH - ENEMY_SIZE), SCREEN_HEIGHT - ENEMY_SIZE
        else:
            x, y = 0, randint(0, SCREEN_HEIGHT - ENEMY_SIZE)
        enemies.append(Enemy(x, y, enemy_hp))
    return enemies


def spawn_powerup():
    weights = (2, 2, 2, 3, 0.33, 0.7)
    powerup_type = choices(REGULAR_POWERUP_TYPES, weights=weights, k=1)[0]
    x = randint(40, SCREEN_WIDTH - POWERUP_SIZE - 40)
    y = randint(90, SCREEN_HEIGHT - POWERUP_SIZE - 40)
    return PowerUp(powerup_type, x, y)


def spawn_weapon_drop():
    powerup_type = choice(WEAPON_TYPES)
    x = randint(40, SCREEN_WIDTH - POWERUP_SIZE - 40)
    y = randint(90, SCREEN_HEIGHT - POWERUP_SIZE - 40)
    return PowerUp(powerup_type, x, y)


def count_regular_powerups(powerups):
    return sum(1 for powerup in powerups if not powerup.is_weapon())


def count_weapon_drops(powerups):
    return sum(1 for powerup in powerups if powerup.is_weapon())


def load_or_create_battlefield():
    if not os.path.exists(BACKGROUND_PATH):
        os.makedirs(os.path.dirname(BACKGROUND_PATH), exist_ok=True)
        battlefield = create_battlefield_image()
        pygame.image.save(battlefield, BACKGROUND_PATH)
    return pygame.image.load(BACKGROUND_PATH).convert()


def create_battlefield_image():
    rng = Random(7)
    surface = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
    surface.fill((39, 61, 46))

    for _ in range(700):
        x = rng.randrange(SCREEN_WIDTH)
        y = rng.randrange(SCREEN_HEIGHT)
        color = rng.choice(((43, 73, 48), (50, 83, 54), (34, 55, 43), (58, 76, 50)))
        pygame.draw.circle(surface, color, (x, y), rng.randrange(1, 3))

    for _ in range(26):
        rect = pygame.Rect(
            rng.randrange(-80, SCREEN_WIDTH),
            rng.randrange(-50, SCREEN_HEIGHT),
            rng.randrange(70, 180),
            rng.randrange(28, 80),
        )
        color = rng.choice(((87, 71, 48), (74, 65, 53), (63, 70, 57), (79, 84, 60)))
        pygame.draw.ellipse(surface, color, rect)

    for _ in range(55):
        x = rng.randrange(20, SCREEN_WIDTH - 20)
        y = rng.randrange(20, SCREEN_HEIGHT - 20)
        radius = rng.randrange(5, 13)
        pygame.draw.circle(surface, (76, 82, 86), (x, y), radius)
        pygame.draw.circle(surface, (43, 48, 52), (x + 2, y + 2), radius, width=2)

    for _ in range(14):
        start = (rng.randrange(SCREEN_WIDTH), rng.randrange(SCREEN_HEIGHT))
        end = (start[0] + rng.randrange(-180, 180), start[1] + rng.randrange(-130, 130))
        pygame.draw.line(surface, (78, 64, 45), start, end, width=rng.randrange(3, 8))

    vignette = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
    for radius in range(430, 760, 26):
        alpha = min(70, max(0, radius - 430) // 5)
        pygame.draw.ellipse(
            vignette,
            (0, 0, 0, alpha),
            pygame.Rect(
                SCREEN_WIDTH // 2 - radius,
                SCREEN_HEIGHT // 2 - radius // 2,
                radius * 2,
                radius,
            ),
            width=18,
        )
    surface.blit(vignette, (0, 0))
    return surface


def draw_world(surface, battlefield, safe_zone_active):
    surface.blit(battlefield, (0, 0))

    for x in range(0, SCREEN_WIDTH, TILE_SIZE):
        pygame.draw.line(surface, (35, 42, 54, 40), (x, 0), (x, SCREEN_HEIGHT))
    for y in range(0, SCREEN_HEIGHT, TILE_SIZE):
        pygame.draw.line(surface, (35, 42, 54, 40), (0, y), (SCREEN_WIDTH, y))

    if safe_zone_active:
        pygame.draw.rect(surface, (39, 91, 74), SAFE_ZONE, border_radius=8)
        pygame.draw.rect(surface, (105, 207, 151), SAFE_ZONE, width=3, border_radius=8)


def draw_hp_bar(surface, player):
    bar_rect = pygame.Rect(16, 16, 220, 20)
    fill_width = round(bar_rect.width * (player.hp / PLAYER_MAX_HP))
    fill_rect = pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height)

    pygame.draw.rect(surface, (16, 24, 36), bar_rect, border_radius=5)
    pygame.draw.rect(surface, (64, 196, 99), fill_rect, border_radius=5)
    pygame.draw.rect(surface, (226, 232, 240), bar_rect, width=2, border_radius=5)


def draw_hud(surface, font, player, enemy_count, kill_count, next_target, safe_break_timer, in_safe_zone):
    zone_text = "Safe Zone" if in_safe_zone else "Danger Zone"
    break_text = f"Break {safe_break_timer:.0f}s" if safe_break_timer > 0 else "Battle"
    weapon_text = player.current_weapon().replace("_", " ").title()
    slot_1 = player.weapon_slots[0].replace("_", " ").title()
    slot_2 = player.weapon_slots[1].replace("_", " ").title() if player.weapon_slots[1] else "Empty"
    invincible_text = f"Invincible {player.invincible_timer:.0f}s" if player.invincible_timer > 0 else "Invincible 0s"
    info = (
        f"HP: {player.hp}/{PLAYER_MAX_HP}    "
        f"Kills: {kill_count}/{next_target}    "
        f"Enemies: {enemy_count}    "
        f"Weapon: {weapon_text}    "
        f"{break_text}    "
        f"{invincible_text}    "
        f"{zone_text}"
    )
    upgrades = (
        f"Bullet +{player.bullet_size_bonus}    "
        f"Speed +{player.bullet_speed_bonus}    "
        f"Damage +{player.damage_bonus}    "
        f"Super damage x{player.super_damage_multiplier:.0f}    "
        f"Super fire x{player.super_fire_rate_multiplier:.0f}"
    )
    slots = f"Slot 1: {slot_1}    Slot 2: {slot_2}    Active Slot: {player.active_slot + 1}"
    controls = "Mouse/Numpad: Aim    Hold Space/Left Click: Shoot    Wheel/X: Switch    WASD/Arrows: Move"
    lines = [
        font.render(info, True, (226, 232, 240)),
        font.render(upgrades, True, (207, 215, 226)),
        font.render(slots, True, (207, 215, 226)),
        font.render(controls, True, (185, 195, 210)),
    ]
    background = pygame.Rect(
        16,
        44,
        max(line.get_width() for line in lines) + 24,
        sum(line.get_height() for line in lines) + 28,
    )
    pygame.draw.rect(surface, (11, 15, 22), background, border_radius=6)

    y = background.y + 7
    for line in lines:
        surface.blit(line, (background.x + 12, y))
        y += line.get_height() + 4


def draw_game_over(surface, font):
    title = font.render("Game Over - Press R to Restart or Esc to Quit", True, (255, 235, 235))
    background = pygame.Rect(0, 0, title.get_width() + 36, title.get_height() + 24)
    background.center = (SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    pygame.draw.rect(surface, (65, 18, 28), background, border_radius=8)
    surface.blit(title, title.get_rect(center=background.center))


def main():
    pygame.mixer.pre_init(44100, -16, 1, 512)
    pygame.init()
    pygame.display.set_caption("Top-down 2D Game Prototype")
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    battlefield = load_or_create_battlefield()
    clock = pygame.time.Clock()
    font = pygame.font.SysFont("consolas", 18)
    sounds = SoundManager()
    player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
    shots = []
    enemies = []
    powerups = []
    spawn_timer = 0
    powerup_timer = uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)
    weapon_timer = uniform(WEAPON_SPAWN_MIN, WEAPON_SPAWN_MAX)
    kill_count = 0
    next_kill_target = KILL_TARGET_STEP
    safe_break_timer = 0
    safe_zone_active = True
    base_count_next_spawn = True

    running = True
    while running:
        dt = clock.tick(FPS) / 1000
        in_safe_zone = safe_zone_active and SAFE_ZONE.contains(player.rect)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and player.hp > 0:
                if player.can_shoot():
                    player.update_aim()
                    shots.extend(player.shoot())
                    sounds.play_weapon(player.current_weapon())
            elif event.type == pygame.MOUSEWHEEL and player.hp > 0:
                player.switch_weapon()
                sounds.play("switch")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_x and player.hp > 0:
                player.switch_weapon()
                sounds.play("switch")
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_r and player.hp <= 0:
                player = Player(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2)
                shots.clear()
                enemies.clear()
                powerups.clear()
                spawn_timer = 0
                powerup_timer = uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)
                weapon_timer = uniform(WEAPON_SPAWN_MIN, WEAPON_SPAWN_MAX)
                kill_count = 0
                next_kill_target = KILL_TARGET_STEP
                safe_break_timer = 0
                safe_zone_active = True
                base_count_next_spawn = True

        if player.hp > 0:
            player.update(dt)
            if safe_zone_active and not SAFE_ZONE.contains(player.rect):
                safe_zone_active = False

            in_safe_zone = safe_zone_active and SAFE_ZONE.contains(player.rect)
            spawn_timer = max(0, spawn_timer - dt)
            powerup_timer = max(0, powerup_timer - dt)
            weapon_timer = max(0, weapon_timer - dt)
            safe_break_timer = max(0, safe_break_timer - dt)

            if pygame.key.get_pressed()[pygame.K_SPACE] and player.can_shoot():
                shots.extend(player.shoot())
                sounds.play_weapon(player.current_weapon())

            if not in_safe_zone and safe_break_timer <= 0 and not enemies and spawn_timer <= 0:
                enemies.extend(spawn_enemies(kill_count, base_count_next_spawn))
                base_count_next_spawn = False
                spawn_timer = SPAWN_COOLDOWN

            if powerup_timer <= 0 and count_regular_powerups(powerups) < 3:
                powerups.append(spawn_powerup())
                powerup_timer = uniform(POWERUP_SPAWN_MIN, POWERUP_SPAWN_MAX)

            if weapon_timer <= 0 and count_weapon_drops(powerups) < 2:
                powerups.append(spawn_weapon_drop())
                weapon_timer = uniform(WEAPON_SPAWN_MIN, WEAPON_SPAWN_MAX)

            for shot in shots[:]:
                shot.update(dt)
                if isinstance(shot, Bullet) and shot.is_off_screen():
                    shots.remove(shot)
                elif isinstance(shot, LaserShot) and shot.is_done():
                    shots.remove(shot)

            for powerup in powerups[:]:
                powerup.update(dt)
                if powerup.is_expired():
                    powerups.remove(powerup)

            for powerup in powerups[:]:
                if player.rect.colliderect(powerup.rect):
                    player.apply_powerup(powerup.type)
                    powerups.remove(powerup)
                    sounds.play("pickup")

            for enemy in enemies[:]:
                enemy.update(dt, player)

            for shot in shots[:]:
                if isinstance(shot, LaserShot):
                    if not shot.hit_applied:
                        for enemy in enemies:
                            if shot.hits(enemy.rect):
                                enemy.take_hit(shot.damage)
                                sounds.play("hit")
                        shot.hit_applied = True
                    continue

                for enemy in enemies:
                    if enemy.rect.colliderect(shot.rect):
                        enemy.take_hit(shot.damage)
                        sounds.play("hit")
                        if shot in shots:
                            shots.remove(shot)
                        break

            for enemy in enemies[:]:
                if enemy.is_dead():
                    enemies.remove(enemy)
                    kill_count += 1

            if kill_count >= next_kill_target:
                enemies.clear()
                shots.clear()
                safe_break_timer = SAFE_BREAK_TIME
                spawn_timer = SPAWN_COOLDOWN
                next_kill_target += KILL_TARGET_STEP
                base_count_next_spawn = True

        draw_world(screen, battlefield, safe_zone_active)
        for powerup in powerups:
            powerup.draw(screen, font)
        for shot in shots:
            shot.draw(screen)
        for enemy in enemies:
            enemy.draw(screen)
        player.draw(screen)
        draw_hp_bar(screen, player)
        draw_hud(screen, font, player, len(enemies), kill_count, next_kill_target, safe_break_timer, in_safe_zone)
        if player.hp <= 0:
            draw_game_over(screen, font)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
