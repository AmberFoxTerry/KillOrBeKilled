import asyncio
import json
import math
import time
import uuid

from aiohttp import web, WSMsgType

HOST = "0.0.0.0"
PORT = 10000

TICK_RATE = 60
TICK_TIME = 1 / TICK_RATE

waiting_players = []
rooms = {}

WEAPONS = {
"pistol": {
"damage": 150,
"cooldown": 0.5,
"bullets": 1,
"spread": 0,
"range": 5.0,
"bullet_size": 0.25,
}
}

SKINS = {
"starter": {
"hp": 1000,
"regeneration_amount": 100,
"regeneration_delay": 3.0,
}
}

class Player:
def **init**(self, ws):
self.id = str(uuid.uuid4())
self.ws = ws

```
    self.name = "Player"
    self.weapon = "pistol"
    self.skin = "starter"

    self.room = None

    self.x = 0.0
    self.y = 0.0
    self.angle = 0.0

    self.input_x = 0.0
    self.input_y = 0.0
    self.aim_x = 0.0
    self.aim_y = 0.0
    self.shooting = False

    self.alive = True

    self.max_hp = 1000
    self.hp = 1000

    self.last_shot = 0.0
    self.last_damage = 0.0
    self.last_regeneration = 0.0
```

class Room:
def **init**(self, player1, player2):
self.id = str(uuid.uuid4())

```
    self.players = [player1, player2]

    player1.room = self
    player2.room = self

    player1.x = -100.0
    player1.y = 0.0

    player2.x = 100.0
    player2.y = 0.0

    player1.alive = True
    player2.alive = True

    player1.last_damage = time.monotonic()
    player2.last_damage = time.monotonic()

    self.started = False
    self.finished = False
    self.result_sent = False
```

def get_weapon(player):
return WEAPONS.get(player.weapon, WEAPONS["pistol"])

def get_skin(player):
return SKINS.get(player.skin, SKINS["starter"])

async def send_json(ws, data):
if ws.closed:
return

```
try:
    await ws.send_json(data)
except Exception:
    pass
```

async def broadcast_room(room, data):
if room is None:
return

```
await asyncio.gather(
    *(send_json(player.ws, data) for player in room.players),
    return_exceptions=True
)
```

def distance(x1, y1, x2, y2):
return math.hypot(x2 - x1, y2 - y1)

def player_radius(player):
return 60.0

def update_player_angle(player):
dx = player.aim_x - player.x
dy = player.aim_y - player.y

```
if abs(dx) < 0.001 and abs(dy) < 0.001:
    return

player.angle = math.atan2(dy, dx)
```

def apply_damage(attacker, target, damage):
if not target.alive:
return None

```
target.hp -= damage
target.hp = max(0, target.hp)

target.last_damage = time.monotonic()
target.last_regeneration = target.last_damage

if target.hp <= 0:
    target.hp = 0
    target.alive = False
    return attacker

return None
```

def find_bullet_hit(attacker, room):
weapon = get_weapon(attacker)

```
max_distance = weapon["range"] * 120.0

direction_x = math.cos(attacker.angle)
direction_y = math.sin(attacker.angle)

closest_target = None
closest_distance = max_distance

for target in room.players:
    if target is attacker:
        continue

    if not target.alive:
        continue

    target_x = target.x - attacker.x
    target_y = target.y - attacker.y

    projection = (
        target_x * direction_x
        + target_y * direction_y
    )

    if projection < 0:
        continue

    if projection > max_distance:
        continue

    closest_x = attacker.x + direction_x * projection
    closest_y = attacker.y + direction_y * projection

    side_distance = distance(
        closest_x,
        closest_y,
        target.x,
        target.y
    )

    hit_radius = player_radius(target) * weapon["bullet_size"]

    if side_distance <= hit_radius:
        if projection < closest_distance:
            closest_target = target
            closest_distance = projection

return closest_target, closest_distance
```

async def shoot(player):
room = player.room

```
if room is None:
    return

if room.finished:
    return

if not player.alive:
    return

now = time.monotonic()
weapon = get_weapon(player)

if now - player.last_shot < weapon["cooldown"]:
    return

player.last_shot = now

update_player_angle(player)

bullet_distance = weapon["range"] * 120.0

target, hit_distance = find_bullet_hit(player, room)

if target is not None:
    bullet_distance = hit_distance

await broadcast_room(
    room,
    {
        "type": "bullet",
        "player_id": player.id,
        "x": player.x,
        "y": player.y,
        "angle": player.angle,
        "range": bullet_distance,
        "speed": 900
    }
)

if target is None:
    return

winner = apply_damage(
    player,
    target,
    weapon["damage"]
)

if winner is None:
    return

await end_match(room, winner)
```

async def end_match(room, winner):
if room.finished:
return

```
room.finished = True

if room.result_sent:
    return

room.result_sent = True

for player in room.players:
    await send_json(
        player.ws,
        {
            "type": "match_over",
            "winner": winner.id,
            "you": player.id
        }
    )

await asyncio.sleep(2)

for player in room.players:
    player.room = None

    if not player.ws.closed:
        try:
            await player.ws.close()
        except Exception:
            pass

rooms.pop(room.id, None)
```

async def send_state(room):
players = []

```
for player in room.players:
    players.append(
        {
            "id": player.id,
            "name": player.name,
            "x": player.x,
            "y": player.y,
            "angle": player.angle,
            "hp": player.hp,
            "max_hp": player.max_hp,
            "skin": player.skin,
            "weapon": player.weapon,
            "alive": player.alive
        }
    )

await broadcast_room(
    room,
    {
        "type": "state",
        "players": players
    }
)
```

def update_movement(player):
if not player.alive:
return

```
speed = 180.0

length = math.hypot(
    player.input_x,
    player.input_y
)

if length > 1:
    player.input_x /= length
    player.input_y /= length

player.x += player.input_x * speed * TICK_TIME
player.y += player.input_y * speed * TICK_TIME
```

def regenerate_player(player):
if not player.alive:
return

```
skin = get_skin(player)
now = time.monotonic()

last_activity = max(
    player.last_damage,
    player.last_shot
)

if now - last_activity < skin["regeneration_delay"]:
    return

if player.hp >= player.max_hp:
    return

if now - player.last_regeneration < skin["regeneration_delay"]:
    return

player.hp += skin["regeneration_amount"]
player.hp = min(
    player.hp,
    player.max_hp
)

player.last_regeneration = now
```

async def game_loop(room):
while not room.finished:
for player in room.players:
update_player_angle(player)
update_movement(player)
regenerate_player(player)

```
        if player.shooting:
            await shoot(player)

    await send_state(room)

    await asyncio.sleep(TICK_TIME)
```

async def start_room(room):
if room.started:
return

```
room.started = True
rooms[room.id] = room

await broadcast_room(
    room,
    {
        "type": "match_found",
        "room": room.id
    }
)

await asyncio.sleep(0.2)

await send_state(room)

asyncio.create_task(game_loop(room))
```

async def try_matchmake():
while len(waiting_players) >= 2:
player1 = waiting_players.pop(0)
player2 = waiting_players.pop(0)

```
    if player1.ws.closed:
        continue

    if player2.ws.closed:
        continue

    room = Room(player1, player2)

    await start_room(room)
```

async def handle_message(player, data):
message_type = data.get("type")

```
if message_type == "player_info":
    name = data.get("name", "Player")
    weapon = data.get("weapon", "pistol")
    skin = data.get("skin", "starter")

    if not isinstance(name, str):
        name = "Player"

    if not isinstance(weapon, str):
        weapon = "pistol"

    if not isinstance(skin, str):
        skin = "starter"

    if weapon not in WEAPONS:
        weapon = "pistol"

    if skin not in SKINS:
        skin = "starter"

    player.name = name[:32]
    player.weapon = weapon
    player.skin = skin

    skin_data = get_skin(player)

    player.max_hp = skin_data["hp"]
    player.hp = player.max_hp

    return

if message_type == "play":
    if player.room is not None:
        return

    if player not in waiting_players:
        waiting_players.append(player)

    await try_matchmake()

    return

if message_type == "input":
    if player.room is None:
        return

    if player.room.finished:
        return

    try:
        input_x = float(data.get("x", 0))
        input_y = float(data.get("y", 0))
        aim_x = float(data.get("aim_x", player.x))
        aim_y = float(data.get("aim_y", player.y))
    except (TypeError, ValueError):
        return

    player.input_x = max(-1.0, min(1.0, input_x))
    player.input_y = max(-1.0, min(1.0, input_y))

    player.aim_x = max(-5000.0, min(5000.0, aim_x))
    player.aim_y = max(-5000.0, min(5000.0, aim_y))

    player.shooting = bool(data.get("shooting", False))

    update_player_angle(player)
```

async def websocket_handler(request):
ws = web.WebSocketResponse()
await ws.prepare(request)

```
player = Player(ws)

try:
    async for message in ws:
        if message.type == WSMsgType.TEXT:
            try:
                data = json.loads(message.data)
            except json.JSONDecodeError:
                continue

            if not isinstance(data, dict):
                continue

            await handle_message(player, data)

        elif message.type == WSMsgType.ERROR:
            break

except Exception:
    pass

finally:
    if player in waiting_players:
        waiting_players.remove(player)

    room = player.room

    if room is not None and not room.finished:
        room.finished = True

        other_players = [
            p for p in room.players
            if p is not player and p.alive
        ]

        if other_players:
            winner = other_players[0]

            await send_json(
                winner.ws,
                {
                    "type": "match_over",
                    "winner": winner.id,
                    "you": winner.id
                }
            )

        rooms.pop(room.id, None)

        for p in room.players:
            p.room = None

return ws
```

async def health(request):
return web.json_response(
{
"status": "ok",
"players_waiting": len(waiting_players),
"rooms": len(rooms)
}
)

app = web.Application()

app.router.add_get("/", health)
app.router.add_get("/ws", websocket_handler)

if **name** == "**main**":
web.run_app(
app,
host=HOST,
port=PORT
)
