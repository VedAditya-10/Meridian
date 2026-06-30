"""
Purpose: Identity Resolution Service for Cross-Camera Tracking.
Responsibilities:
- Ingest raw edge telemetry containing biometric vectors.
- Query PostgreSQL `pgvector` to mathematically match embeddings against known visitors.
- Maintain identity profiles by resolving collisions or creating new visitor records.
- Limit embedding storage to prevent database bloat and slow searches.
Dependencies: pgvector, sqlalchemy
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.visitor import Visitor, VisitorEmbedding

logger = logging.getLogger(__name__)


# Global tracking cache to guarantee identity stability on the same camera
# Map of (camera_id, session_id, track_id) -> (visitor_id, last_seen_timestamp)
TRACK_CACHE = {}

# Max embeddings to store per visitor to prevent DB bloat
MAX_EMBEDDINGS_PER_VISITOR = 5


def find_most_redundant_embedding(embeddings: list) -> int:
    """
    Returns index of the embedding most similar to its peers.
    Since embeddings are L2 normalized, similarity is just the dot product.
    """
    if len(embeddings) <= 1:
        return 0

    max_avg_similarity = -1.0
    most_redundant_idx = 0

    for i, emb in enumerate(embeddings):
        similarities = []
        for j, other in enumerate(embeddings):
            if i != j:
                # Dot product as cosine similarity
                sim = sum(x * y for x, y in zip(emb, other))
                similarities.append(sim)
        
        avg_similarity = sum(similarities) / len(similarities) if similarities else 0.0
        if avg_similarity > max_avg_similarity:
            max_avg_similarity = avg_similarity
            most_redundant_idx = i

    return most_redundant_idx


class IdentityMatcher:
    def __init__(self, db: AsyncSession):
        self.db = db
        
        # Default to 0.48 for FastReID (configurable via REID_DISTANCE_THRESHOLD)
        import os
        self.DISTANCE_THRESHOLD = float(os.getenv("REID_DISTANCE_THRESHOLD", "0.48"))

    async def resolve_identity(self, telemetry: Dict[str, Any]) -> Optional[str]:
        """
        Takes raw telemetry from a camera edge node, queries the vector space to find
        the global visitor ID, and adapts the identity profile dynamically.
        """
        store_id = telemetry["store_id"]
        camera_id = telemetry["camera_id"]
        session_id = telemetry.get("session_id", "")
        track_id = str(telemetry["track_id"])
        embedding_list = telemetry.get("embedding")
        quality_score = telemetry.get("quality_score", 0.0)
        now_ts = telemetry["timestamp"]
        
        # 0. Check cache first to ensure same-camera continuity and avoid DB/CPU load
        cache_key = (camera_id, session_id, track_id)
        if cache_key in TRACK_CACHE:
            visitor_id, _ = TRACK_CACHE[cache_key]
            TRACK_CACHE[cache_key] = (visitor_id, now_ts)
            return str(visitor_id)

        # Clean old cache entries (older than 30 seconds) to prevent memory leak
        active_visitors_on_camera = set()
        for k, (v_id, ts) in list(TRACK_CACHE.items()):
            if now_ts - ts > 30.0:
                TRACK_CACHE.pop(k, None)
            elif k[0] == camera_id and k[1] == session_id and k[2] != track_id:
                active_visitors_on_camera.add(v_id)

        # Convert unix float timestamp from edge into UTC timezone-aware datetime
        event_time = datetime.fromtimestamp(now_ts, tz=timezone.utc)

        # Fail fast: If no embedding was sent, we cannot resolve biometric identity.
        if not embedding_list:
            return None

        # Convert standard Python list into a vector format expected by pgvector
        vector = [float(x) for x in embedding_list]

        # 1. Fast Vector Search for Nearest Neighbor
        # We use Cosine Distance (`<=>` operator in PostgreSQL pgvector).
        # We strictly scope the search to the specific `store_id` to prevent matching
        # someone in the New York store with someone in the Tokyo store.
        # We also EXCLUDE visitor IDs that are currently actively tracked on this SAME camera
        # under a DIFFERENT track ID, because one person cannot be in two places at once.
        if active_visitors_on_camera:
            stmt = (
                select(VisitorEmbedding, VisitorEmbedding.embedding.cosine_distance(vector).label("distance"))
                .join(Visitor)
                .where(Visitor.store_id == store_id)
                .where(Visitor.id.not_in(list(active_visitors_on_camera)))
                .order_by(VisitorEmbedding.embedding.cosine_distance(vector))
                .limit(1)
            )
        else:
            stmt = (
                select(VisitorEmbedding, VisitorEmbedding.embedding.cosine_distance(vector).label("distance"))
                .join(Visitor)
                .where(Visitor.store_id == store_id)
                .order_by(VisitorEmbedding.embedding.cosine_distance(vector))
                .limit(1)
            )

        result = await self.db.execute(stmt)
        row = result.first()

        visitor_id = None
        
        if row and row.distance <= self.DISTANCE_THRESHOLD:
            # --- 2a. MATCH FOUND ---
            matched_embedding = row.VisitorEmbedding
            visitor_id = matched_embedding.visitor_id
            logger.info(f"Identity Resolved: Match {visitor_id} (Distance: {row.distance:.3f})")
            
            # Update the visitor's `last_seen` timestamp to keep their session active
            visitor = await self.db.get(Visitor, visitor_id)
            if visitor:
                visitor.last_seen = event_time

        else:
            # --- 2b. NO MATCH: NEW VISITOR ---
            new_visitor_id = uuid.uuid4()
            dist_str = f" (nearest distance: {row.distance:.3f})" if row else " (no existing embeddings)"
            logger.info(f"New Identity Profile Created: {new_visitor_id}{dist_str}")
            
            new_visitor = Visitor(
                id=new_visitor_id,
                store_id=store_id,
                first_seen=event_time,
                last_seen=event_time,
                is_staff=False
            )
            self.db.add(new_visitor)
            visitor_id = new_visitor_id

        # Cache the resolved identity immediately
        TRACK_CACHE[cache_key] = (visitor_id, now_ts)

        # 3. Dynamic Profile Adaptation: Store embedding only for high-quality crops
        # AND only if the visitor doesn't already have too many embeddings
        if quality_score > 0.4:
            # Check current embedding count for this visitor
            count_stmt = select(func.count(VisitorEmbedding.id)).where(
                VisitorEmbedding.visitor_id == visitor_id
            )
            count_result = await self.db.execute(count_stmt)
            current_count = count_result.scalar() or 0
            
            if current_count < MAX_EMBEDDINGS_PER_VISITOR:
                new_embedding = VisitorEmbedding(
                    visitor_id=visitor_id,
                    embedding=vector,
                    quality_score=quality_score
                )
                self.db.add(new_embedding)
            else:
                # Load all existing embeddings to evaluate redundancy
                existing_stmt = select(VisitorEmbedding).where(
                    VisitorEmbedding.visitor_id == visitor_id
                )
                existing_result = await self.db.execute(existing_stmt)
                existing_embeddings = list(existing_result.scalars().all())
                
                all_vectors = [list(e.embedding) for e in existing_embeddings] + [vector]
                evict_idx = find_most_redundant_embedding(all_vectors)
                
                if evict_idx < len(existing_embeddings):
                    # Evict the redundant existing embedding and add the new one
                    await self.db.delete(existing_embeddings[evict_idx])
                    new_embedding = VisitorEmbedding(
                        visitor_id=visitor_id,
                        embedding=vector,
                        quality_score=quality_score
                    )
                    self.db.add(new_embedding)
                else:
                    logger.debug(f"New embedding for visitor {visitor_id} is redundant; skipping.")

        # Commit the transaction to persist the new identity or adapted embeddings
        try:
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Database error during identity resolution: {e}")
            return None

        return str(visitor_id)
