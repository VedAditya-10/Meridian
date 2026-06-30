import os
import json
import asyncio
import logging
import redis.asyncio as redis
from redis.exceptions import ResponseError as RedisResponseError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.matcher import IdentityMatcher, TRACK_CACHE

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("reid-service")

async def clean_track_cache_loop():
    import time
    while True:
        try:
            await asyncio.sleep(60)
            now_ts = time.time()
            cleaned_count = 0
            for k, (v_id, ts) in list(TRACK_CACHE.items()):
                if now_ts - ts > 30.0:
                    TRACK_CACHE.pop(k, None)
                    cleaned_count += 1
            if cleaned_count > 0:
                logger.info(f"Cleaned up {cleaned_count} stale TRACK_CACHE entries.")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Error in clean_track_cache_loop: {e}")

async def main():
    cleanup_task = asyncio.create_task(clean_track_cache_loop())
    logger.info("ReID Biometric Service is starting...")

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

    # Initialize DB connection
    engine = create_async_engine(db_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize Redis client
    r = redis.from_url(redis_uri)
    
    input_stream = "telemetry_raw"
    output_stream = "telemetry_resolved"
    group_name = "reid_group"
    
    # Create consumer group if not exists
    try:
        await r.xgroup_create(input_stream, group_name, id="0", mkstream=True)
        logger.info(f"Created consumer group {group_name} on {input_stream}")
    except RedisResponseError as e:
        if "BUSYGROUP" in str(e):
            logger.info("Consumer group already exists.")
        else:
            logger.error(f"Error creating consumer group: {e}")

    logger.info("Awaiting embedding requests from edge nodes...")
    
    while True:
        try:
            # Read from stream
            messages = await r.xreadgroup(group_name, "reid_worker_1", {input_stream: ">"}, count=10, block=1000)
            
            for stream, msgs in messages:
                async with async_session() as session:
                    matcher = IdentityMatcher(session)
                    for msg_id, msg_data in msgs:
                        # Parse msg_data (everything is bytes in raw redis depending on config, but redis.asyncio decodes strings if configured or returns bytes)
                        # Convert byte keys/values to strings
                        msg = {k.decode('utf-8') if isinstance(k, bytes) else k: v.decode('utf-8') if isinstance(v, bytes) else v for k, v in msg_data.items()}
                        
                        try:
                            telemetry = {
                                "store_id": msg["store_id"],
                                "camera_id": msg["camera_id"],
                                "session_id": msg.get("session_id", ""),
                                "track_id": msg["track_id"],
                                "bbox": json.loads(msg["bbox"]),
                                "frame_width": int(msg["frame_width"]) if "frame_width" in msg else 1920,
                                "frame_height": int(msg["frame_height"]) if "frame_height" in msg else 1080,
                                "embedding": json.loads(msg["embedding"]) if msg.get("embedding") else None,
                                "quality_score": float(msg["quality_score"]),
                                "timestamp": float(msg["timestamp"])
                            }
                            
                            visitor_id = await matcher.resolve_identity(telemetry)
                            
                            if visitor_id:
                                # Publish resolved telemetry
                                resolved_payload = {
                                    "store_id": telemetry["store_id"],
                                    "camera_id": telemetry["camera_id"],
                                    "visitor_id": visitor_id,
                                    "bbox": json.dumps(telemetry["bbox"]),
                                    "frame_width": str(telemetry["frame_width"]),
                                    "frame_height": str(telemetry["frame_height"]),
                                    "timestamp": str(telemetry["timestamp"])
                                }
                                await r.xadd(output_stream, resolved_payload, maxlen=50000, approximate=True)
                                
                                # Publish to Pub/Sub for Live Dashboard
                                try:
                                    await r.publish("live_telemetry", json.dumps(resolved_payload))
                                except Exception as e:
                                    logger.error(f"Failed to publish to live_telemetry pub/sub: {e}")
                                
                                logger.debug(f"Resolved track {telemetry['track_id']} -> visitor {visitor_id}")
                                
                        except Exception as e:
                            logger.error(f"Error processing message {msg_id}: {e}")
                        
                        # Acknowledge message
                        await r.xack(input_stream, group_name, msg_id)
                    
        except Exception as e:
            logger.error(f"Redis stream error: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
