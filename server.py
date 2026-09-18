import asyncio
import json
import math
import time
import uuid

from aiohttp import web

# ============================================================

# WEAPONS

# ============================================================

WEAPONS = {
"pistol": {
"damage": 150,
"cooldown": 0.5,
"bullets": 1,
"spread": 0,
"range": 5,
"bullet_size": 0.25,
"bullet_speed": 900
}
}

# ============================================================

# SKINS

# ============================================================

SKINS = {
"starter": {
"hp": 1000,
"regen_amount": 100,
"regen_delay": 3
}
}

# ============================================================

# SETTINGS

# ============================================================

PLAYER_SIZE = 120

MAP_WIDTH = 2000
MAP_HEIGHT = 1200

TICK_RATE = 60

# ============================================================

# PLAYER

# ============================================================

class Player:

```
def __init__(self, websocket):

    self.id = str(uuid.uuid4())

    self.websocket = websocket

    self.name = "Player"

    self.weapon = "pistol"
    self.skin = "starter"

    self.x = 0
    self.y = 0

    self.angle = 0

    self.input_x = 0
    self.input_y = 0

    self.aim_x = 0
    self.aim_y = 0

    self.shooting = False

    self.alive = True

    self.hp = 1000
    self.max_hp = 1000

    self.last_shot = 0
    self.last_damage = 0
    self.last_shot_time = 0

    self.room = None

def apply_skin(self):

    skin = SKINS.get(
        self.skin,
        SKINS["starter"]
    )

    self.max_hp = skin["hp"]
    self.hp = self.max_hp
```

# ============================================================

# ROOM

# ============================================================

class Room:

```
def __init__(self):

    self.id = str(uuid.uuid4())

    self.players = {}

    self.finished = False

def add(self, player):

    self.players[player.id] = player

    player.room = self

    if len(self.players) == 1:

        player.x = 300
        player.y = MAP_HEIGHT / 2

    else:

        player.x = MAP_WIDTH - 300
        player.y = MAP_HEIGHT / 2

def remove(self, player):

    self.players.pop(
        player.id,
        None
    )
```

# ============================================================

# GLOBALS

# ============================================================

waiting_players = {}
rooms = {}

# ============================================================

# DATA

# ============================================================

def get_weapon(name):

```
return WEAPONS.get(
    name,
    WEAPONS["pistol"]
)
```

def get_skin(name):

```
return SKINS.get(
    name,
    SKINS["starter"]
)
```

# ============================================================

# SEND

# ============================================================

async def send(player, data):

```
try:

    await player.websocket.send_str(
        json.dumps(data)
    )

except Exception:
    pass
```

async def broadcast_room(room, data):

```
if not room:
    return

await asyncio.gather(
    *[
        send(player, data)
        for player in room.players.values()
    ]
)
```

# ============================================================

# MATCHMAKING

# ============================================================

async def find_match(player):

```
if player.room:
    return

if waiting_players:

    opponent_id, opponent = next(
        iter(waiting_players.items())
    )

    del waiting_players[opponent_id]

    room = Room()

    room.add(opponent)
    room.add(player)

    rooms[room.id] = room

    await broadcast_room(
        room,
        {
            "type": "match_found"
        }
    )

    return

waiting_players[player.id] = player
```

# ============================================================

# MOVEMENT

# ============================================================

def move_player(player, dt):

```
if not player.alive:
    return

speed = 350

x = player.input_x
y = player.input_y

length = math.hypot(x, y)

if length > 1:

    x /= length
    y /= length

player.x += x * speed * dt
player.y += y * speed * dt

player.x = max(
    60,
    min(
        MAP_WIDTH - 60,
        player.x
    )
)

player.y = max(
    60,
    min(
        MAP_HEIGHT - 60,
        player.y
    )
)
```

# ============================================================

# AIM

# ============================================================

def update_aim(player):

```
dx = player.aim_x
dy = player.aim_y

if dx == 0 and dy == 0:
    return

player.angle = math.atan2(
    dy,
    dx
)
```

# ============================================================

# SHOOTING

# ============================================================

async def shoot(player):

```
if not player.alive:
    return

now = time.time()

weapon = get_weapon(
    player.weapon
)

if now - player.last_shot < weapon["cooldown"]:
    return

player.last_shot = now
player.last_shot_time = now

bullet_count = weapon["bullets"]
spread = weapon["spread"]

for i in range(bullet_count):

    if bullet_count == 1:

        angle = player.angle

    else:

        middle = (bullet_count - 1) / 2

        offset = (
            (i - middle) * spread
        )

        angle = player.angle + offset

    bullet = {

        "type": "bullet",

        "x": player.x,
        "y": player.y,

        "angle": angle,

        "range": weapon["range"],

        "size": weapon["bullet_size"],

        "speed": weapon["bullet_speed"],

        "damage": weapon["damage"],

        "owner": player.id
    }

    await broadcast_room(
        player.room,
        bullet
    )

    check_bullet_hit(
        player,
        bullet
    )
```

# ============================================================

# BULLET HIT

# ============================================================

def check_bullet_hit(shooter, bullet):

```
if not shooter.room:
    return

weapon = get_weapon(
    shooter.weapon
)

max_distance = (
    weapon["range"] * PLAYER_SIZE
)

for target in shooter.room.players.values():

    if target.id == shooter.id:
        continue

    if not target.alive:
        continue

    dx = target.x - bullet["x"]
    dy = target.y - bullet["y"]

    distance = math.hypot(
        dx,
        dy
    )

    if distance > max_distance:
        continue

    angle_to_target = math.atan2(
        dy,
        dx
    )

    angle_difference = abs(
        normalize_angle(
            angle_to_target
            - bullet["angle"]
        )
    )

    # Approximate player hitbox.
    if angle_difference < 0.15:

        deal_damage(
            shooter,
            target,
            weapon["damage"]
        )

        break
```

# ============================================================

# DAMAGE / DEATH

# ============================================================

def deal_damage(attacker, target, damage):

```
if not target.alive:
    return

target.hp -= damage

target.last_damage = time.time()

if target.hp > 0:
    return

target.hp = 0
target.alive = False

room = target.room

if not room:
    return

if room.finished:
    return

room.finished = True

winner = None

for player in room.players.values():

    if player.id != target.id:
        winner = player
        break

if not winner:
    return

asyncio.create_task(
    broadcast_room(
        room,
        {
            "type": "match_over",

            "winner": winner.id,

            "loser": target.id
        }
    )
)
```

# ============================================================

# ANGLE

# ============================================================

def normalize_angle(angle):

```
while angle > math.pi:
    angle -= math.pi * 2

while angle < -math.pi:
    angle += math.pi * 2

return angle
```

# ============================================================

# REGENERATION

# ============================================================

def regenerate(player, dt):

```
if not player.alive:
    return

skin = get_skin(
    player.skin
)

now = time.time()

delay = skin["regen_delay"]

# Recently damaged.
if now - player.last_damage < delay:
    return

# Recently fired.
if now - player.last_shot_time < delay:
    return

if player.hp >= player.max_hp:
    return

player.hp = min(
    player.max_hp,
    player.hp + (
        skin["regen_amount"] * dt
    )
)
```

# ============================================================

# GAME LOOP

# ============================================================

async def game_loop():

```
while True:

    start = time.time()

    for room in list(
        rooms.values()
    ):

        if room.finished:
            continue

        for player in list(
            room.players.values()
        ):

            move_player(
                player,
                1 / TICK_RATE
            )

            update_aim(player)

            regenerate(
                player,
                1 / TICK_RATE
            )

            if player.shooting:

                await shoot(
                    player
                )

        state = {

            "type": "state",

            "players": [

                {
                    "id": p.id,

                    "x": p.x,
                    "y": p.y,

                    "angle": p.angle,

                    "hp": p.hp,
                    "max_hp": p.max_hp,

                    "alive": p.alive,

                    "weapon": p.weapon,
                    "skin": p.skin
                }

                for p in room.players.values()
            ]
        }

        await broadcast_room(
            room,
            state
        )

    elapsed = time.time() - start

    await asyncio.sleep(
        max(
            0,
            (1 / TICK_RATE) - elapsed
        )
    )
```

# ============================================================

# WEBSOCKET

# ============================================================

async def websocket_handler(request):

```
ws = web.WebSocketResponse()

await ws.prepare(request)

player = Player(ws)

await send(
    player,
    {
        "type": "welcome",
        "id": player.id
    }
)

try:

    async for message in ws:

        if message.type != web.WSMsgType.TEXT:
            continue

        try:

            data = json.loads(
                message.data
            )

        except Exception:

            continue

        msg_type = data.get(
            "type"
        )

        # --------------------------------
        # PLAYER INFO
        # --------------------------------

        if msg_type == "player_info":

            weapon = data.get(
                "weapon",
                "pistol"
            )

            skin = data.get(
                "skin",
                "starter"
            )

            # Only accept valid IDs.
            # Client cannot send custom stats.

            if weapon in WEAPONS:
                player.weapon = weapon
            else:
                player.weapon = "pistol"

            if skin in SKINS:
                player.skin = skin
            else:
                player.skin = "starter"

            player.apply_skin()

        # --------------------------------
        # PLAY
        # --------------------------------

        elif msg_type == "play":

            await find_match(
                player
            )

        # --------------------------------
        # INPUT
        # --------------------------------

        elif msg_type == "input":

            try:

                x = float(
                    data.get(
                        "x",
                        0
                    )
                )

                y = float(
                    data.get(
                        "y",
                        0
                    )
                )

                player.input_x = max(
                    -1,
                    min(1, x)
                )

                player.input_y = max(
                    -1,
                    min(1, y)
                )

                player.aim_x = float(
                    data.get(
                        "aim_x",
                        0
                    )
                )

                player.aim_y = float(
                    data.get(
                        "aim_y",
                        0
                    )
                )

                player.shooting = bool(
                    data.get(
                        "shooting",
                        False
                    )
                )

            except Exception:

                pass

finally:

    waiting_players.pop(
        player.id,
        None
    )

    if player.room:

        room = player.room

        room.remove(
            player
        )

        if not room.players:

            rooms.pop(
                room.id,
                None
            )

return ws
```

# ============================================================

# HTTP

# ============================================================

async def index(request):

```
return web.Response(
    text="KillOrBeKilled server online."
)
```

app = web.Application()

app.router.add_get(
"/",
index
)

app.router.add_get(
"/ws",
websocket_handler
)

# ============================================================

# START / STOP

# ============================================================

async def start_game_loop(app):

```
app["game_task"] = asyncio.create_task(
    game_loop()
)
```

async def stop_game_loop(app):

```
app["game_task"].cancel()
```

app.on_startup.append(
start_game_loop
)

app.on_cleanup.append(
stop_game_loop
)

# ============================================================

# RUN

# ============================================================

if **name** == "**main**":

```
web.run_app(
    app,
    host="0.0.0.0",
    port=10000
)
```
