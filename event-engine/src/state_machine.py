"""
Purpose: State Machine for tracking spatial movements and emitting business events.
Responsibilities:
- Maintain in-memory tracking of where each visitor is currently located.
- Perform high-speed point-in-polygon spatial calculations using `Shapely`.
- Emit strict domain events (`ENTRY`, `ZONE_ENTER`, `ZONE_DWELL`, `QUEUE_ABANDON`) when transitions occur.
- Supports per-camera zone filtering via `camera_ids` in zone polygon data.
- Uses normalized (0.0–1.0) coordinates so polygons are resolution-independent.
Dependencies: shapely
"""

import logging
import time
from typing import Any, Dict, List, Optional

from shapely.geometry import Point, Polygon

# from src.publisher import EventPublisher

logger = logging.getLogger(__name__)


class ZoneState:
    def __init__(self, zone_id: str, zone_type: str, zone_name: str, polygon_data):
        self.zone_id = zone_id
        self.zone_type = zone_type
        self.zone_name = zone_name

        # Polygon data can be:
        #   - Legacy: list of {"x": float, "y": float} points (store-wide, no camera filter)
        #   - New:    dict with "camera_ids": [...] and "points": [...{"x":float,"y":float}...]
        if isinstance(polygon_data, dict):
            self.camera_ids: Optional[List[str]] = polygon_data.get("camera_ids", None)
            points = polygon_data.get("points", [])
        else:
            # Legacy format — applies to all cameras
            self.camera_ids = None
            points = polygon_data

        # Pre-compile the Shapely Polygon for O(1) intersection checks later.
        # Coordinates are expected in normalized 0.0–1.0 space.
        self.polygon = Polygon([(pt['x'], pt['y']) for pt in points])


class VisitorState:
    def __init__(self, visitor_id: str, store_id: str, timestamp: float):
        self.visitor_id = visitor_id
        self.store_id = store_id
        self.current_zone_id: Optional[str] = None
        self.zone_entry_time: Optional[float] = None
        self.first_seen_time: float = timestamp
        self.last_seen_time: float = timestamp
        self.dwell_event_emitted: bool = False


class EventStateMachine:
    def __init__(self, publisher: Any):
        self.publisher = publisher

        # Principal Note: In a horizontally scaled deployment with multiple Event Engine
        # pods, this state MUST be externalized to Redis (using Hash Maps or JSON).
        # For V1 / Single-Worker deployment, an in-memory dictionary is used for zero latency.
        self.visitors: Dict[str, VisitorState] = {}

        # Recently exited visitors held temporarily to support seamless re-entry / session resumption
        # visitor_id -> { "state": VisitorState, "exit_time": float, "exit_event_id": str }
        self.recently_exited: Dict[str, dict] = {}
        self.RECENT_EXIT_TIMEOUT_SEC = 360.0  # 6 minutes re-entry window

        # Mapping of Store ID -> Compiled Shapely Zones
        self.store_zones: Dict[str, List[ZoneState]] = {}

        # Configuration: How long before a passing glance becomes a "Dwell" event
        self.DWELL_THRESHOLD_SEC = 15.0

        # Configuration: If a visitor is not seen for this long, emit EXIT and free memory
        import os
        self.VISITOR_TIMEOUT_SEC = float(os.getenv("VISITOR_TIMEOUT_SECONDS", "300.0"))

    def load_zones(self, store_id: str, zones_data: List[Dict[str, Any]]):
        """Loads and compiles store polygons into memory on startup."""
        self.store_zones[store_id] = [
            ZoneState(z['id'], z['zone_type'], z['name'], z['polygon']) for z in zones_data
        ]
        logger.info(f"Compiled {len(zones_data)} Shapely polygons for store {store_id}")

    def sweep_timeouts(self, current_time: float, store_id: str):
        """
        Called periodically to detect visitors who have gone silent (left the camera view).
        If a visitor hasn't been seen for VISITOR_TIMEOUT_SEC, emit an EXIT event and
        clean them from memory. This is what makes active_visitor_count work correctly.

        IMPORTANT: Only sweeps visitors belonging to the given store_id to prevent
        cross-store contamination of EXIT events.
        """
        import uuid
        timed_out = []
        for visitor_id, state in self.visitors.items():
            # Only sweep visitors belonging to this specific store
            if state.store_id != store_id:
                continue
            if current_time - state.last_seen_time >= self.VISITOR_TIMEOUT_SEC:
                timed_out.append(visitor_id)

        for visitor_id in timed_out:
            state = self.visitors[visitor_id]
            total_dwell = state.last_seen_time - state.first_seen_time
            exit_event_id = str(uuid.uuid4())
            self._emit_event(
                state.store_id,
                visitor_id,
                state.current_zone_id,
                "EXIT",
                state.last_seen_time,
                metadata={
                    "dwell_duration_seconds": round(total_dwell, 1),
                    "reason": "timeout",
                },
                event_id=exit_event_id
            )
            self.recently_exited[visitor_id] = {
                "state": state,
                "exit_time": state.last_seen_time,
                "exit_event_id": exit_event_id
            }
            del self.visitors[visitor_id]

        # Clean up stale recently_exited entries older than RECENT_EXIT_TIMEOUT_SEC
        stale_exits = [
            vid for vid, data in self.recently_exited.items()
            if current_time - data["exit_time"] > self.RECENT_EXIT_TIMEOUT_SEC
        ]
        for vid in stale_exits:
            del self.recently_exited[vid]

        if timed_out:
            logger.info(
                f"Sweep: emitted EXIT for {len(timed_out)} timed-out visitors. "
                f"{len(self.visitors)} still active."
            )

    def process_telemetry(self, telemetry: Dict[str, Any]):
        """
        Consumes resolved telemetry (raw bounding box + global visitor_id).
        Evaluates spatial transitions and emits high-level business events.
        """
        visitor_id = telemetry.get("visitor_id")
        if not visitor_id:
            # Silently drop telemetry if Identity Resolution (ReID) failed to attach an ID
            return

        store_id = telemetry["store_id"]
        camera_id = telemetry.get("camera_id", "")
        bbox = telemetry["bbox"]
        current_time = telemetry["timestamp"]
        frame_w = telemetry.get("frame_width", 1920) or 1920
        frame_h = telemetry.get("frame_height", 1080) or 1080

        # Spatial Reasoning: A person's location is determined by their feet,
        # which is the bottom-center point of the bounding box.
        feet_x = (bbox["x1"] + bbox["x2"]) / 2.0
        feet_y = bbox["y2"]

        # Normalize to 0.0–1.0 so zone polygons are resolution-independent.
        feet_x_norm = feet_x / frame_w
        feet_y_norm = feet_y / frame_h
        feet_point = Point(feet_x_norm, feet_y_norm)

        # 1. ENTRY / RESUME Detection
        if visitor_id not in self.visitors:
            recent = self.recently_exited.get(visitor_id)
            if recent and (current_time - recent["exit_time"] <= self.RECENT_EXIT_TIMEOUT_SEC):
                # Retrieve the old state and cancel the exit event in SQL
                state = recent["state"]
                self.publisher.publish({
                    "event_type": "CANCEL_EXIT",
                    "store_id": store_id,
                    "visitor_id": visitor_id,
                    "exit_event_id": recent["exit_event_id"]
                })
                self.recently_exited.pop(visitor_id, None)
                self.visitors[visitor_id] = state
                logger.info(f"Session resumed for visitor {visitor_id} (EXIT event {recent['exit_event_id']} cancelled)")
            else:
                self.recently_exited.pop(visitor_id, None)  # Clean if expired
                self.visitors[visitor_id] = VisitorState(visitor_id, store_id, current_time)
                self._emit_event(store_id, visitor_id, None, "ENTRY", current_time)

        state = self.visitors[visitor_id]
        state.last_seen_time = current_time

        # 2. Zone Intersection Search — only check zones applicable to this camera.
        all_zones = self.store_zones.get(store_id, [])
        # A zone applies to this camera if it has no camera_ids restriction OR if this
        # camera_id is listed in its camera_ids list.
        applicable_zones = [
            z for z in all_zones
            if z.camera_ids is None or camera_id in z.camera_ids
        ]

        intersecting_zone = None
        for z in applicable_zones:
            if z.polygon.contains(feet_point):
                intersecting_zone = z
                break

        # 3. State Transition Logic
        if intersecting_zone:
            new_zone_id = intersecting_zone.zone_id

            if state.current_zone_id != new_zone_id:
                # --- VISITOR CHANGED ZONES ---

                # Exit the old zone
                if state.current_zone_id:
                    old_zone = next((z for z in all_zones if z.zone_id == state.current_zone_id), None)
                    self._emit_event(store_id, visitor_id, state.current_zone_id, "ZONE_EXIT", current_time,
                                     metadata={"zone_name": old_zone.zone_name if old_zone else ""})

                # Enter the new zone
                state.current_zone_id = new_zone_id
                state.zone_entry_time = current_time
                state.dwell_event_emitted = False

                # High-level Business Event Translation
                if intersecting_zone.zone_type == "QUEUE":
                    self._emit_event(store_id, visitor_id, new_zone_id, "BILLING_QUEUE_JOIN", current_time,
                                     metadata={"zone_name": intersecting_zone.zone_name})
                else:
                    self._emit_event(store_id, visitor_id, new_zone_id, "ZONE_ENTER", current_time,
                                     metadata={"zone_name": intersecting_zone.zone_name})

            else:
                # --- VISITOR REMAINS IN ZONE ---
                # Check if they have dwelled long enough to trigger a DWELL event
                if not state.dwell_event_emitted and state.zone_entry_time:
                    dwell_duration = current_time - state.zone_entry_time
                    if dwell_duration >= self.DWELL_THRESHOLD_SEC:
                        self._emit_event(
                            store_id, visitor_id, new_zone_id, "ZONE_DWELL", current_time,
                            metadata={
                                "dwell_duration_seconds": dwell_duration,
                                "zone_name": intersecting_zone.zone_name
                            }
                        )
                        state.dwell_event_emitted = True

        else:
            # --- VISITOR IS IN NO MAN'S LAND (Dead Space) ---
            if state.current_zone_id:
                old_zone = next((z for z in all_zones if z.zone_id == state.current_zone_id), None)

                if old_zone and old_zone.zone_type == "QUEUE":
                    # They left the queue. We assume abandonment for V1.
                    # V2 logic would verify if they moved to a CHECKOUT_REGISTER zone immediately after.
                    self._emit_event(store_id, visitor_id, state.current_zone_id, "BILLING_QUEUE_ABANDON", current_time,
                                     metadata={"zone_name": old_zone.zone_name if old_zone else ""})
                else:
                    self._emit_event(store_id, visitor_id, state.current_zone_id, "ZONE_EXIT", current_time,
                                     metadata={"zone_name": old_zone.zone_name if old_zone else ""})

                state.current_zone_id = None
                state.zone_entry_time = None

    def _emit_event(self, store_id: str, visitor_id: str, zone_id: Optional[str], event_type: str, timestamp: float, metadata: Dict = None, event_id: Optional[str] = None):
        """Passes the generated domain event to the Publisher for Redis Streams integration."""
        import uuid
        event_payload = {
            "id": event_id or str(uuid.uuid4()),
            "store_id": store_id,
            "visitor_id": visitor_id,
            "zone_id": zone_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "metadata": metadata or {}
        }
        logger.debug(f"Event Engine Emitted: {event_type} | Visitor: {visitor_id} | Zone: {zone_id}")
        self.publisher.publish(event_payload)
