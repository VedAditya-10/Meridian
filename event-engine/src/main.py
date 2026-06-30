import os
import json
import uuid
import asyncio
import logging
import time
from datetime import datetime, timezone
import redis.asyncio as redis
from redis.exceptions import ResponseError as RedisResponseError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.models.event import Event
from src.models.store import Zone
from src.state_machine import EventStateMachine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("event-engine")

class EventPublisher:
    def __init__(self, async_session_maker, redis_client):
        self.async_session_maker = async_session_maker
        self.redis_client = redis_client
        self.queue = asyncio.Queue(maxsize=10000)
        self.worker_task = asyncio.create_task(self._worker())

    def publish(self, payload: dict):
        # Non-blocking publish to queue. If full, drop oldest to avoid OOM.
        try:
            self.queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("EventPublisher queue full. Dropping oldest event.")
            try:
                self.queue.get_nowait()
                self.queue.task_done()
            except Exception:
                pass
            try:
                self.queue.put_nowait(payload)
            except Exception as e:
                logger.error(f"Failed to enqueue event even after dropping: {e}")

    async def _worker(self):
        while True:
            try:
                payload = await self.queue.get()
                
                # Publish to Redis Pub/Sub for live dashboard
                try:
                    await self.redis_client.publish("live_events", json.dumps(payload))
                except Exception as e:
                    logger.error(f"Error publishing to Redis live_events: {e}")

                event_type = payload["event_type"]
                event_id = uuid.UUID(payload["id"]) if "id" in payload else uuid.uuid4()

                if event_type == "CANCEL_EXIT":
                    # Mark the exit event cancelled in Postgres
                    from sqlalchemy import update
                    exit_event_id_raw = payload.get("exit_event_id") or payload.get("metadata", {}).get("exit_event_id")
                    exit_event_id = uuid.UUID(exit_event_id_raw) if isinstance(exit_event_id_raw, str) else exit_event_id_raw
                    async with self.async_session_maker() as session:
                        await session.execute(
                            update(Event)
                            .where(Event.id == exit_event_id)
                            .values(cancelled=True)
                        )
                        await session.commit()
                    logger.info(f"DB updated: EXIT event {exit_event_id} marked as cancelled.")
                else:
                    # Insert normal event into postgres
                    async with self.async_session_maker() as session:
                        event_time = datetime.fromtimestamp(payload["timestamp"], tz=timezone.utc)
                        db_event = Event(
                            id=event_id,
                            store_id=payload["store_id"],
                            visitor_id=payload.get("visitor_id"),
                            zone_id=payload.get("zone_id"),
                            event_type=event_type,
                            timestamp=event_time,
                            metadata_payload=payload.get("metadata", {})
                        )
                        session.add(db_event)
                        await session.commit()
                self.queue.task_done()
            except Exception as e:
                logger.error(f"Error persisting event to DB: {e}")

async def periodic_zone_refresh(async_session_maker, state_machine, active_store_ids, interval: int = 30):
    """
    Reloads zone polygons from DB every 30 seconds.
    Allows live planogram edits without restarting the engine.
    """
    while True:
        await asyncio.sleep(interval)
        try:
            async with async_session_maker() as session:
                result = await session.execute(select(Zone).where(Zone.is_active == True, Zone.deleted_at.is_(None)))
                zones = result.scalars().all()
                
                # Group zones by store_id
                store_zones = {}
                for z in zones:
                    store_zones.setdefault(str(z.store_id), []).append({
                        "id": str(z.id),
                        "name": z.name,
                        "zone_type": z.zone_type,
                        "polygon": z.polygon
                    })
                
                # Reload zones for all active stores
                for store_id_str in list(active_store_ids):
                    z_list = store_zones.get(store_id_str, [])
                    state_machine.load_zones(store_id_str, z_list)
                    
            logger.info("Zone polygons refreshed for all stores.")
        except Exception as e:
            logger.error(f"Periodic zone refresh failed: {e}")

async def main():
    logger.info("Event Engine is starting...")

    redis_uri = os.getenv("REDIS_URI", "redis://redis:6379/0")

    # SQLALCHEMY_DATABASE_URI can be set directly (e.g. Neon cloud with ?ssl=require).
    db_url = os.getenv("SQLALCHEMY_DATABASE_URI")
    if not db_url:
        db_user = os.getenv("POSTGRES_USER", "postgres")
        db_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
        db_host = os.getenv("POSTGRES_SERVER", "postgres")
        db_name = os.getenv("POSTGRES_DB", "store_intelligence")
        db_url = f"postgresql+asyncpg://{db_user}:{db_pass}@{db_host}:5432/{db_name}"
    else:
        import urllib.parse
        if db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        parsed = urllib.parse.urlparse(db_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        new_query = {}
        if 'sslmode' in query_params or 'ssl' in query_params:
            new_query['ssl'] = 'require'
        db_url = urllib.parse.urlunparse((
            parsed.scheme, parsed.netloc, parsed.path, 
            parsed.params, urllib.parse.urlencode(new_query), parsed.fragment
        ))

    logger.info(f"Connecting to database at host: {db_url.split('@')[-1].split('/')[0] if '@' in db_url else 'configured'}")

    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    r = redis.from_url(redis_uri)
    
    publisher = EventPublisher(async_session, r)
    state_machine = EventStateMachine(publisher)
    
    # Load all zones from database to compile Shapely polygons
    logger.info("Loading store zones from database...")
    active_store_ids = []
    async with async_session() as session:
        result = await session.execute(select(Zone).where(Zone.is_active == True, Zone.deleted_at.is_(None)))
        zones = result.scalars().all()
        
        # Group zones by store_id
        store_zones = {}
        for z in zones:
            if z.store_id not in store_zones:
                store_zones[z.store_id] = []
            store_zones[z.store_id].append({
                "id": str(z.id),
                "name": z.name,
                "zone_type": z.zone_type,
                "polygon": z.polygon
            })
            
        for store_id, z_data in store_zones.items():
            state_machine.load_zones(str(store_id), z_data)
            active_store_ids.append(str(store_id))

    async def load_store_zones(store_id_str: str):
        logger.info(f"Dynamically loading zones for new store: {store_id_str}")
        try:
            async with async_session() as session:
                result = await session.execute(select(Zone).where(Zone.store_id == uuid.UUID(store_id_str), Zone.is_active == True, Zone.deleted_at.is_(None)))
                zones = result.scalars().all()
                
                z_data = []
                for z in zones:
                    z_data.append({
                        "id": str(z.id),
                        "name": z.name,
                        "zone_type": z.zone_type,
                        "polygon": z.polygon
                    })
                state_machine.load_zones(store_id_str, z_data)
                active_store_ids.append(store_id_str)
                logger.info(f"Successfully loaded {len(z_data)} zones for {store_id_str}")
        except Exception as ex:
            logger.error(f"Failed to dynamically load zones for store {store_id_str}: {ex}")
            
    # Start periodic zone refresh loop (interval = 30 seconds)
    asyncio.create_task(periodic_zone_refresh(async_session, state_machine, active_store_ids, interval=30))
    
    # Reuse the Redis client created on line 93 instead of re-instantiating
    input_stream = "telemetry_resolved"
    group_name = "event_engine_group"
    
    try:
        await r.xgroup_create(input_stream, group_name, id="0", mkstream=True)
        logger.info(f"Created consumer group {group_name} on {input_stream}")
    except RedisResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info("Consumer group already exists.")
        else:
            logger.error(f"Error creating consumer group: {e}")

    logger.info("Event Engine ready. Awaiting telemetry...")
    
    latest_store_timestamps = {}
    
    while True:
        try:
            messages = await r.xreadgroup(group_name, "ee_worker_1", {input_stream: ">"}, count=100, block=1000)
            
            for stream, msgs in messages:
                for msg_id, msg_data in msgs:
                    msg = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in msg_data.items()}
                    
                    try:
                        store_id = msg["store_id"]
                        if store_id not in active_store_ids:
                            await load_store_zones(store_id)

                        telemetry = {
                            "store_id": store_id,
                            "camera_id": msg["camera_id"],
                            "visitor_id": msg["visitor_id"],
                            "bbox": json.loads(msg["bbox"]),
                            "frame_width": int(msg["frame_width"]) if "frame_width" in msg else 1920,
                            "frame_height": int(msg["frame_height"]) if "frame_height" in msg else 1080,
                            "timestamp": float(msg["timestamp"])
                        }
                        
                        latest_store_timestamps[store_id] = max(
                            latest_store_timestamps.get(store_id, 0.0),
                            telemetry["timestamp"]
                        )
                        
                        state_machine.process_telemetry(telemetry)
                                
                    except Exception as e:
                        logger.error(f"Error processing telemetry {msg_id}: {e}")
                    
                    await r.xack(input_stream, group_name, msg_id)

            # After processing each batch, sweep for timed-out visitors across all stores.
            # This emits EXIT events for visitors who haven't been seen for VISITOR_TIMEOUT_SEC.
            for sid in active_store_ids:
                current_time = latest_store_timestamps.get(sid, time.time())
                state_machine.sweep_timeouts(current_time, sid)
                    
        except Exception as e:
            logger.error(f"Redis stream error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
