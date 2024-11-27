from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from socketio import AsyncServer, ASGIApp
from redis.asyncio import Redis
import asyncio
from contextlib import asynccontextmanager

# Configurações
MAX_INTERACTIONS = 3
RESERVATION_TIMEOUT = 120
PRIORITY_TIMEOUT = 30
TIMER_UPDATE_INTERVAL = 1  # Atualizar os timers a cada segundo

# Redis e fila
redis_client: Redis = None
queue_lock = asyncio.Lock()
queue = []
priority_timers_data = {}  # Armazena o tempo restante para cada usuário prioritário

# Inicialização do Redis
async def initialize_redis():
    """Inicializar o cliente Redis."""
    global redis_client
    redis_client = Redis(host="localhost", port=6379, decode_responses=True)
    try:
        await redis_client.ping()
        print("Redis conectado com sucesso!")
    except Exception as e:
        print(f"Erro ao conectar ao Redis: {e}")

async def close_redis():
    """Fechar a conexão com o Redis."""
    if redis_client:
        await redis_client.close()

# Ciclo de vida do aplicativo
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Ciclo de vida do aplicativo."""
    await initialize_redis()
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

# Variáveis globais
active_users = set()
reservation_timers = {}
priority_timers = {}

# Fila de espera
async def add_to_queue(user_id: str):
    async with queue_lock:
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

# Endpoints REST
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
    await sio.emit("event_created", new_event)  # Emitir evento criado
    return new_event

@app.delete("/events/{event_id}")
async def delete_event(event_id: int):
    key = f"event:{event_id}"
    exists = await redis_client.exists(key)
    if not exists:
        raise HTTPException(status_code=404, detail="Evento não encontrado.")
    await redis_client.unlink(key)
    await sio.emit("event_deleted", {"id": event_id})  # Emitir evento deletado
    return {"message": "Evento removido com sucesso!"}

# WebSocket Handlers
@sio.on("connect")
async def connect(sid, environ):
    print(f"Usuário {sid} conectado.")
    await add_to_queue(sid)
    await update_priority_timers()
    await sio.emit("online_users", {"count": len(await get_queue())})

@sio.on("disconnect")
async def disconnect(sid):
    print(f"Usuário {sid} desconectado.")
    await remove_from_queue(sid)
    active_users.discard(sid)
    await update_priority_timers()

@sio.on("reserve")
async def reserve(sid, data):
    """Gerenciar reservas."""
    priority_users = await get_priority_users()
    if sid not in priority_users:
        await sio.emit("error", {"message": "Você não está entre os três primeiros na fila."}, room=sid)
        return

    if sid in active_users:
        await sio.emit("error", {"message": "Você já está interagindo."}, room=sid)
        return

    active_users.add(sid)
    event_id = data["eventId"]
    slots = int(await redis_client.hget(f"event:{event_id}", "slots"))
    if slots > 0:
        await redis_client.hincrby(f"event:{event_id}", "slots", -1)
        updated_event = {"id": event_id, "slots": slots - 1}
        await sio.emit("event_updated", updated_event)
        reservation_timers[sid] = asyncio.create_task(timeout_reservation(sid, event_id))
    else:
        await sio.emit("error", {"message": "Evento esgotado."}, room=sid)

@sio.on("confirm_reservation")
async def confirm_reservation(sid, data):
    """Confirmar reserva."""
    if sid in reservation_timers:
        reservation_timers[sid].cancel()
        del reservation_timers[sid]
        active_users.discard(sid)

        event_id = data["eventId"]
        user_data = {"name": data["name"], "phone": data["phone"]}
        await redis_client.hset(f"user_data:{event_id}:{sid}", mapping=user_data)

        await sio.emit("reservation_confirmed", {"user": sid, "eventId": event_id})
        await update_priority_timers()

async def timeout_reservation(sid, event_id):
    """Timeout para reservas."""
    await asyncio.sleep(RESERVATION_TIMEOUT)
    await redis_client.hincrby(f"event:{event_id}", "slots", 1)
    active_users.discard(sid)
    del reservation_timers[sid]
    updated_event = {"id": event_id, "slots": int(await redis_client.hget(f"event:{event_id}", "slots"))}
    await sio.emit("event_updated", updated_event)

async def update_priority_timers():
    """Atualizar timers de prioridade."""
    priority_users = await get_priority_users()
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
    """Gerenciar timeout de 30 segundos para usuários prioritários."""
    while priority_timers_data.get(sid, 0) > 0:
        await asyncio.sleep(TIMER_UPDATE_INTERVAL)
        priority_timers_data[sid] -= TIMER_UPDATE_INTERVAL
        await sio.emit("timer_update", {"sid": sid, "time_remaining": priority_timers_data[sid]})
    await remove_from_queue(sid)
    await add_to_queue(sid)
    if sid in priority_timers_data:
        del priority_timers_data[sid]
    await update_priority_timers()

async def get_priority_users():
    """Obter usuários prioritários da fila."""
    queue = await get_queue()
    return queue[:MAX_INTERACTIONS]
