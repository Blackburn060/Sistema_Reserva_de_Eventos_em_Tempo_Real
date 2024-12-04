from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from socketio import AsyncServer, ASGIApp
from redis.asyncio import Redis
import asyncio
from contextlib import asynccontextmanager

# Configurações padrão
DEFAULT_MAX_INTERACTIONS = 3
DEFAULT_PRIORITY_TIMEOUT = 30
DEFAULT_RESERVATION_TIMEOUT = 5
TIMER_UPDATE_INTERVAL = 1 

MAX_INTERACTIONS = DEFAULT_MAX_INTERACTIONS
PRIORITY_TIMEOUT = DEFAULT_PRIORITY_TIMEOUT
RESERVATION_TIMEOUT = DEFAULT_RESERVATION_TIMEOUT

redis_client: Redis = None
queue_lock = asyncio.Lock()
queue = []
priority_timers_data = {}

active_users_lock = asyncio.Lock()
reservation_timers_lock = asyncio.Lock()
priority_timers_lock = asyncio.Lock()
priority_timers_data_lock = asyncio.Lock()

active_users = set()
reservation_timers = {}
priority_timers = {}

async def initialize_redis():
    global redis_client
    redis_client = Redis(host="localhost", port=6379, decode_responses=True)
    try:
        await redis_client.ping()
        print("Redis conectado com sucesso!")
    except Exception as e:
        print(f"Erro ao conectar ao Redis: {e}")

async def close_redis():
    if redis_client:
        await redis_client.close()

async def initialize_settings():
    global MAX_INTERACTIONS, PRIORITY_TIMEOUT, RESERVATION_TIMEOUT
    max_users = await redis_client.get("max_users")
    choice_timeout = await redis_client.get("choice_timeout")
    reservation_timeout = await redis_client.get("reservation_timeout")

    MAX_INTERACTIONS = int(max_users) if max_users else DEFAULT_MAX_INTERACTIONS
    PRIORITY_TIMEOUT = int(choice_timeout) if choice_timeout else DEFAULT_PRIORITY_TIMEOUT
    RESERVATION_TIMEOUT = int(reservation_timeout) if reservation_timeout else DEFAULT_RESERVATION_TIMEOUT

@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_redis()
    await initialize_settings()
    yield
    await close_redis()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

sio = AsyncServer(async_mode="asgi", cors_allowed_origins=["http://localhost:4200"])
app.mount("/socket.io", ASGIApp(sio))

async def add_to_queue(user_id: str):
    async with queue_lock:
        if user_id not in queue:
            queue.append(user_id)
            print(f"Usuário {user_id} adicionado à fila.")

async def remove_from_queue(user_id: str):
    async with queue_lock:
        if user_id in queue:
            queue.remove(user_id)
            print(f"Usuário {user_id} removido da fila.")

async def get_queue():
    async with queue_lock:
        return list(queue)

@app.get("/events")
async def get_events():
    keys = await redis_client.keys("event:*")
    events = []
    for key in keys:
        data = await redis_client.hgetall(key)
        event_id = key.split(":")[1]
        events.append({
            "id": int(event_id),
            "name": data["name"],
            "slots": int(data["slots"]),
            "date": data["date"],
        })
    return events

@app.post("/events")
async def create_event(event: dict):
    if not event.get("name") or not event.get("slots") or not event.get("date"):
        raise HTTPException(status_code=400, detail="Nome, número de vagas e data são obrigatórios.")
    event_id = await redis_client.incr("event_counter")
    await redis_client.hset(f"event:{event_id}", mapping={
        "name": event["name"],
        "slots": event["slots"],
        "date": event["date"]
    })
    new_event = {"id": event_id, "name": event["name"], "slots": event["slots"], "date": event["date"]}
    await sio.emit("event_created", new_event)
    return new_event

@app.delete("/events/{event_id}")
async def delete_event(event_id: int):
    key = f"event:{event_id}"
    exists = await redis_client.exists(key)
    if not exists:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    await redis_client.unlink(key)
    await sio.emit("event_deleted", {"id": event_id})
    return {"message": "Evento removido com sucesso!"}

@app.get("/settings")
async def get_settings():
    max_users = await redis_client.get("max_users")
    choice_timeout = await redis_client.get("choice_timeout")
    reservation_timeout = await redis_client.get("reservation_timeout")
    return {
        "maxUsers": int(max_users) if max_users else DEFAULT_MAX_INTERACTIONS,
        "choiceTimeout": int(choice_timeout) if choice_timeout else DEFAULT_PRIORITY_TIMEOUT,
        "reservationTimeout": int(reservation_timeout) if reservation_timeout else DEFAULT_RESERVATION_TIMEOUT,
    }

@app.post("/settings")
async def update_settings(settings: dict):
    global MAX_INTERACTIONS, PRIORITY_TIMEOUT, RESERVATION_TIMEOUT
    if "maxUsers" in settings:
        MAX_INTERACTIONS = settings["maxUsers"]
        await redis_client.set("max_users", MAX_INTERACTIONS)
    if "choiceTimeout" in settings:
        PRIORITY_TIMEOUT = settings["choiceTimeout"]
        await redis_client.set("choice_timeout", PRIORITY_TIMEOUT)
    if "reservationTimeout" in settings:
        RESERVATION_TIMEOUT = settings["reservationTimeout"]
        await redis_client.set("reservation_timeout", RESERVATION_TIMEOUT)
    return {"message": "Configurações atualizadas com sucesso!"}

# WebSocket Handlers
@sio.on("connect")
async def connect(sid, environ):
    print(f"Usuário {sid} conectado.")
    await add_to_queue(sid)
    await update_priority_timers()
    online_users = len(await get_queue())
    await sio.emit("online_users", {"count": online_users})

@sio.on("disconnect")
async def disconnect(sid):
    print(f"Usuário {sid} desconectado.")
    await remove_from_queue(sid)
    async with active_users_lock:
        active_users.discard(sid)
    await update_priority_timers()

@sio.on("reserve")
async def reserve(sid, data):
    priority_users = await get_priority_users()
    if sid not in priority_users:
        return {"success": False, "message": "Você não está entre os primeiros na fila."}

    async with active_users_lock:
        if sid in active_users:
            return {"success": False, "message": "Você já está interagindo."}
        active_users.add(sid)

    event_id = data["eventId"]
    event_key = f"event:{event_id}"

    if not await redis_client.exists(event_key):
        async with active_users_lock:
            active_users.discard(sid)
        return {"success": False, "message": "Evento não encontrado."}

    slots = int(await redis_client.hget(event_key, "slots"))

    if slots > 0:
        new_slots = await redis_client.hincrby(event_key, "slots", -1)
        if new_slots < 0:
            await redis_client.hincrby(event_key, "slots", 1)
            async with active_users_lock:
                active_users.discard(sid)
            return {"success": False, "message": "Evento esgotado."}

        updated_event = {"id": event_id, "slots": new_slots}

        await sio.emit("event_updated", updated_event)
        async with reservation_timers_lock:
            reservation_timers[sid] = asyncio.create_task(timeout_reservation(sid, event_id))
        return {"success": True}
    else:
        async with active_users_lock:
            active_users.discard(sid)
        return {"success": False, "message": "Evento esgotado."}

@sio.on("confirm_reservation")
async def confirm_reservation(sid, data):
    async with reservation_timers_lock:
        if sid in reservation_timers:
            reservation_timers[sid].cancel()
            del reservation_timers[sid]
        else:
            await sio.emit("error", {"message": "Nenhuma reserva pendente para confirmar."}, room=sid)
            return

    async with active_users_lock:
        active_users.discard(sid)

    event_id = data["eventId"]
    user_data = {"name": data["name"], "phone": data["phone"]}
    await redis_client.hset(f"user_data:{event_id}:{sid}", mapping=user_data)

    await sio.emit("reservation_confirmed", {"user": sid, "eventId": event_id})
    await update_priority_timers()

@sio.on("cancel_reservation")
async def cancel_reservation(sid, data):
    event_id = data["eventId"]
    event_key = f"event:{event_id}"

    if not await redis_client.exists(event_key):
        await sio.emit("error", {"message": "Evento não encontrado."}, room=sid)
        return

    slots = int(await redis_client.hincrby(event_key, "slots", 1))

    updated_event = {"id": event_id, "slots": slots}
    await sio.emit("event_updated", updated_event)

    async with reservation_timers_lock:
        if sid in reservation_timers:
            reservation_timers[sid].cancel()
            del reservation_timers[sid]

    async with active_users_lock:
        active_users.discard(sid)

    await remove_from_queue(sid)
    await add_to_queue(sid)

    print(f"Reserva cancelada e vaga restaurada para o evento {event_id}.")
    await update_priority_timers()

async def timeout_reservation(sid, event_id):
    await asyncio.sleep(RESERVATION_TIMEOUT)
    slots = int(await redis_client.hincrby(f"event:{event_id}", "slots", 1))
    updated_event = {"id": event_id, "slots": slots}
    await sio.emit("event_updated", updated_event)

    async with reservation_timers_lock:
        del reservation_timers[sid]

    async with active_users_lock:
        active_users.discard(sid)

    await sio.emit("reservation_timeout", {"eventId": event_id}, room=sid)

    await remove_from_queue(sid)
    await add_to_queue(sid)
    await update_priority_timers()

async def update_priority_timers():
    priority_users = await get_priority_users()
    async with priority_timers_data_lock, priority_timers_lock:
        for sid in list(priority_timers):
            if sid not in priority_users:
                priority_timers[sid].cancel()
                del priority_timers[sid]
                del priority_timers_data[sid]

        for sid in priority_users:
            if sid not in priority_timers_data:
                priority_timers_data[sid] = PRIORITY_TIMEOUT
                priority_timers[sid] = asyncio.create_task(timeout_priority(sid))

    await sio.emit("queue_update", {
        "queue": await get_queue(),
        "priority": priority_users,
        "timers": {sid: priority_timers_data[sid] for sid in priority_users},
    })

async def timeout_priority(sid):
    while True:
        await asyncio.sleep(TIMER_UPDATE_INTERVAL)
        async with priority_timers_data_lock:
            if sid not in priority_timers_data:
                break
            priority_timers_data[sid] -= TIMER_UPDATE_INTERVAL
            if priority_timers_data[sid] <= 0:
                break
            await sio.emit("timer_update", {"sid": sid, "time_remaining": priority_timers_data[sid]})

    async with priority_timers_data_lock, priority_timers_lock:
        if sid in priority_timers_data:
            del priority_timers_data[sid]
        if sid in priority_timers:
            del priority_timers[sid]

    await remove_from_queue(sid)
    await add_to_queue(sid)
    await update_priority_timers()

async def get_priority_users():
    queue = await get_queue()
    return queue[:MAX_INTERACTIONS]
