# Edge Cases & Detection Strategy

This document outlines how the Store Intelligence detection pipeline handles complex real-world edge cases.

## 1. Re-Entry Handling
**Problem:** A customer exits the store and re-enters 5 minutes later. Do we count them twice or resume their session?
**Strategy:** We leverage the **ReID (Re-Identification) Service**. When a person crosses the entry line, their ReID vector is extracted. The `reid-service` performs a similarity search (`pgvector`) against vectors recorded in the last 15 minutes. 
- If a match is found (Cosine distance < 0.25), the previous session is resumed, preventing duplicate footfall counting. 
- If the time elapsed exceeds 15 minutes, they are counted as a new session.

## 2. Staff Filtering Strategy
**Problem:** Employees cross the entry/exit lines constantly, artificially inflating footfall metrics.
**Strategy:** We implement a **Zone-Exclusion & Dwell-Time Heuristic**. 
- Staff members typically dwell in designated "Staff Only" zones (e.g., behind the register, stockroom doors) for extended periods. 
- The `event-engine` tracks cumulative dwell time in these restricted zones. If a tracking ID accumulates >10 minutes in a staff zone, they are flagged as `is_staff = true` and their future movements are filtered out of the primary conversion funnel metrics.

## 3. Occlusion Strategy
**Problem:** A customer is temporarily blocked by a shelf or another person, causing YOLOv8 to lose the bounding box.
**Strategy:** We rely on **ByteTrack's Kalman Filter**.
- ByteTrack predicts the velocity and trajectory of the bounding box. If a detection is missed for a few frames due to occlusion, the Kalman filter maintains the track ID based on predicted motion.
- We configure `track_buffer=30` frames (at 2 FPS, this allows for up to 15 seconds of occlusion recovery) before the track is formally considered "lost".

## 4. Group Movement Assumptions
**Problem:** A family of three walks in closely clustered together. YOLOv8 might draw a single bounding box around them.
**Strategy:** We acknowledge this as a limitation of standard object detection models. 
- To mitigate this, we use NMS (Non-Maximum Suppression) tuning to allow slightly overlapping bounding boxes.
- However, extremely tight clusters may still be counted as a single entity. Our system assumes that for conversion metrics, a tight family unit acts as a single "buying unit" anyway, making this an acceptable business tradeoff.

## 5. Track Recovery Assumptions
**Problem:** An identity is completely lost and a new track ID is generated for the same person.
**Strategy:** The ReID service acts as the ultimate source of truth. Even if ByteTrack assigns a new local ID (`track_id = 99`), when this track generates a significant event (like a zone entry), the ReID service vector match will map it back to the global `visitor_id`, ensuring session consistency across camera handoffs and lost tracks.
