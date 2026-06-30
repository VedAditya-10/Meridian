# Meridian - Single Store Analytics Platform
## Architecture & Implementation Plan

---

## 🎯 System Overview

**Meridian** is a single-store CCTV analytics platform designed for self-hosted deployment. Each retail store gets their own installation running on their local server/computer.

### Key Characteristics
- **Single Store System**: One installation = One store
- **Self-Hosted**: Runs on client's infrastructure
- **0-6 Cameras**: Flexible camera configuration per deployment
- **Unlimited Data Retention**: Historical data kept forever unless manually deleted
- **Real-Time Analytics**: Live dashboards with instant insights

---

## ⚠️ Implementation Principles (Read First)

These rules keep Meridian **simple and functional**. They align the plan with the **existing codebase** (event-engine, reid-service, edge-node) — do not reinvent what already works.

| Principle | Decision |
|-----------|----------|
| **Single store ID** | One fixed UUID (`MERIDIAN_STORE_ID` in config). No integer `id = 1` — avoids breaking analytics tables and microservices. |
| **Full Docker stack** | Use the **root `docker-compose.yml`** (Postgres + pgvector, Redis, reid-service, event-engine, backend-api, edge-node, frontend). The minimal compose sketch in older drafts is **invalid** — analytics will not run without Redis and worker services. |
| **Zone storage** | Keep `zones.store_id` + `polygon` JSONB (not `camera_id` FK). Filter per camera via `polygon.camera_ids`. Matches event-engine today. |
| **Coordinates** | All zone points **normalized 0.0–1.0** (`{"x": 0.1, "y": 0.2}`). Pixel coords silently break zone events. |
| **ENTRY_LINE geometry** | Store as a **thin rectangle polygon** (4 vertices), not a 2-point line. Works with `shapely.contains()` — no event-engine changes. |
| **Soft deletes** | Cameras and zones: set `deleted_at` / `is_active = false`. **Never** hard-delete zones (historical heatmaps reference them). **No** `ON DELETE CASCADE` from cameras → zones. |
| **Dwell threshold** | Global 15s in event-engine (`DWELL_THRESHOLD_SEC`). Per-zone dwell config is out of scope. |
| **Video FPS** | 2 FPS (file) / 5 FPS (live) in edge-node. Do not use 30 FPS. |

---

## 📐 Architecture Decisions

### What Changed from Multi-Store Codebase

| Original (Multi-Tenant) | Meridian (Single Store) |
|------------------------|-------------------------|
| Multiple stores per deployment | One store per deployment |
| Store CRUD (add many) | Store settings (edit only) |
| Store selector dropdown | No dropdown — load the single store |
| `GET /stores` list | `GET /api/v1/store` (singular) |
| Multi-tenancy in queries | All queries scoped to `MERIDIAN_STORE_ID` |

### What Stayed the Same
- Event pipeline: edge-node → Redis → reid-service → event-engine → Postgres
- Camera CRUD (0–6 limit)
- Zone polygons with `camera_ids` filter (per-camera zones without schema churn)
- Analytics dashboards + SSE live stream
- RTSP, video file, and webcam input
- `product_category` on zones (required for section-performance / revenue charts)
- `min_engaged_dwell_seconds` on store (required for dashboard engaged-visitor metrics)

---

## 🗄️ Database Schema (Authoritative)

> **One source of truth.** Sprint 3 and later sections reference this block — do not duplicate conflicting schemas elsewhere.

### Stores Table (Single Record)
```sql
-- Table name stays `stores` (existing). Exactly one row enforced in application code.
CREATE TABLE stores (
  id UUID PRIMARY KEY,  -- fixed MERIDIAN_STORE_ID from env/config
  name VARCHAR(255) NOT NULL DEFAULT 'My Store',
  address TEXT,
  phone VARCHAR(50),
  location VARCHAR(255),  -- legacy alias; prefer address for new UI
  timezone VARCHAR(50) NOT NULL DEFAULT 'Asia/Kolkata',
  min_engaged_dwell_seconds INTEGER NOT NULL DEFAULT 60,
  max_cameras INTEGER NOT NULL DEFAULT 6,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bootstrap inserts one row on first startup (see backend-api lifespan / seed script).
```

### Cameras Table
```sql
CREATE TABLE cameras (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id UUID NOT NULL REFERENCES stores(id),
  name VARCHAR(255) NOT NULL,
  camera_type VARCHAR(50) NOT NULL DEFAULT 'rtsp_stream',  -- rtsp_stream | video_file | webcam
  rtsp_url TEXT,
  video_file_path TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'inactive',  -- active | inactive | error
  position_index INTEGER,  -- display order 1–6
  calibration_data JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  deleted_at TIMESTAMPTZ NULL,  -- soft delete; analytics history retained
  CONSTRAINT cameras_name_unique_active UNIQUE (store_id, name)  -- enforce in app when deleted_at IS NULL
);
```

### Zones Table
```sql
CREATE TABLE zones (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  store_id UUID NOT NULL REFERENCES stores(id),  -- NOT camera_id FK — use polygon.camera_ids
  name VARCHAR(255) NOT NULL,
  zone_type VARCHAR(50) NOT NULL,  -- ENTRY_LINE | DISPLAY | AISLE | QUEUE
  product_category VARCHAR(100),   -- required for revenue / section-performance charts
  polygon JSONB NOT NULL,
  -- polygon shape (all points normalized 0.0–1.0):
  -- {
  --   "camera_ids": ["<camera-uuid>"],
  --   "points": [{"x": 0.1, "y": 0.6}, {"x": 0.9, "y": 0.6}, ...]
  -- }
  is_active BOOLEAN NOT NULL DEFAULT TRUE,
  deleted_at TIMESTAMPTZ NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_zones_store_active ON zones (store_id, is_active) WHERE is_active = TRUE;
```

**Zone rules:**
- **DELETE** = soft delete only (`is_active = false`, `deleted_at = now()`). Event-engine loads `is_active = true` only.
- **ENTRY_LINE** = 4-vertex thin rectangle polygon (user draws a line; backend stores as narrow rect).
- **No CASCADE** from camera removal → zones stay for historical event/heatmap lookups.

### Analytics Tables (Unchanged)
- `visitors`, `visitor_embeddings` (pgvector)
- `events`
- `transactions`
- `daily_store_metrics`

---

## 🔌 API Endpoints

All routes use prefix **`/api/v1`**. The single store is resolved server-side — callers do not pass `store_id` on new endpoints.

### Store
```
GET    /api/v1/store                 # Get the one store (+ cameras)
PUT    /api/v1/store                 # Update name, address, phone, timezone
DELETE /api/v1/store/data            # Clear analytics (visitors, events, transactions, metrics)
                                     # Body: { "confirm": "DELETE" }
```

### Cameras (max 6 active)
```
GET    /api/v1/cameras               # List non-deleted cameras
POST   /api/v1/cameras               # Add camera (reject if count >= max_cameras)
GET    /api/v1/cameras/:id           # Camera detail
PUT    /api/v1/cameras/:id           # Update name, type, URLs, status
DELETE /api/v1/cameras/:id           # Soft delete (deleted_at); keep zones + analytics
POST   /api/v1/cameras/:id/test      # Test RTSP connection
GET    /api/v1/cameras/:id/snapshot  # JPEG frame for zone canvas (RTSP / video file)
```

### Zones
```
GET    /api/v1/cameras/:cameraId/zones?active=true
POST   /api/v1/cameras/:cameraId/zones
PUT    /api/v1/zones/:id
DELETE /api/v1/zones/:id             # Soft delete only
```

### Analytics (store resolved automatically)
```
GET    /api/v1/dashboard/store          # KPIs (was /dashboard/store/{id})
GET    /api/v1/dashboard/traffic        # Hourly footfall / exits
GET    /api/v1/dashboard/funnel
GET    /api/v1/heatmaps/zones
GET    /api/v1/dashboard/store/stream   # SSE live events + telemetry
```

**Legacy (remove after frontend migration):** `/api/v1/stores`, `/api/v1/stores/{id}/*` — keep temporarily, delegate to `MERIDIAN_STORE_ID`.

---

## 🎨 UI/UX Changes

### Navigation (Updated)
Remove store selector dropdown, update navigation:

```
┌─────────────────────────────────────┐
│  👁️ Meridian                        │  ← Brand name updated
├─────────────────────────────────────┤
│  INPUT                              │
│  📤 Video Input                     │
├─────────────────────────────────────┤
│  ANALYTICS                          │
│  📊 Overview                        │
│  🎥 Live Feeds                      │
│  🔥 Zone Heatmaps                   │
│  ⚠️  Anomalies                      │
├─────────────────────────────────────┤
│  SETTINGS                           │
│  ⚙️  Store Settings    ← Updated    │
└─────────────────────────────────────┘
```

### Store Settings Page (New Design)

```
┌─────────────────────────────────────────────────────────┐
│  Store Settings                                         │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  📍 Store Information                           │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  Store Name:  [My Retail Store        ]   💾   │   │
│  │  Address:     [123 Main St, City      ]        │   │
│  │  Phone:       [+1 234 567 8900        ]        │   │
│  │  Timezone:    [Asia/Kolkata      ▼]            │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  🎥 Camera Management (2/6 cameras)             │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  [+ Add New Camera]                             │   │
│  │                                                  │   │
│  │  ┌────────────────────────────────────────┐    │   │
│  │  │ 📹 Entrance Camera                     │    │   │
│  │  │ RTSP: rtsp://192.168.1.10/stream       │    │   │
│  │  │ Status: ● Active    Zones: 2           │    │   │
│  │  │ [Edit] [Configure Zones] [Remove]      │    │   │
│  │  └────────────────────────────────────────┘    │   │
│  │                                                  │   │
│  │  ┌────────────────────────────────────────┐    │   │
│  │  │ 📹 Checkout Camera                     │    │   │
│  │  │ Video File: /uploads/checkout.mp4      │    │   │
│  │  │ Status: ○ Inactive    Zones: 1         │    │   │
│  │  │ [Edit] [Configure Zones] [Remove]      │    │   │
│  │  └────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │  🗑️  Data Management                            │   │
│  ├─────────────────────────────────────────────────┤   │
│  │  Clear all analytics data (cannot be undone)   │   │
│  │  [🗑️ Clear All Data]                           │   │
│  └─────────────────────────────────────────────────┘   │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Add Camera Modal

```
┌───────────────────────────────────────────┐
│  Add New Camera                           │
├───────────────────────────────────────────┤
│                                            │
│  Camera Name *                            │
│  [Entrance Camera              ]          │
│                                            │
│  Camera Type *                            │
│  ○ RTSP Stream                            │
│  ○ Video File                             │
│  ○ Webcam                                 │
│                                            │
│  ┌─ If RTSP Stream ─────────────────┐    │
│  │  RTSP URL *                       │    │
│  │  [rtsp://192.168.1.10/stream]    │    │
│  │  [Test Connection]                │    │
│  └───────────────────────────────────┘    │
│                                            │
│  ┌─ If Video File ───────────────────┐   │
│  │  [📁 Choose File] video.mp4       │   │
│  └───────────────────────────────────┘    │
│                                            │
│  ┌─ If Webcam ──────────────────────┐    │
│  │  [🎥 Request Camera Access]       │   │
│  │  Device: [Built-in Webcam  ▼]     │   │
│  └───────────────────────────────────┘    │
│                                            │
│  ☑️ Configure zones after adding          │
│                                            │
│  [Cancel]              [Add Camera]       │
└───────────────────────────────────────────┘
```

### Zone Configuration Modal (Functional Canvas)

```
┌─────────────────────────────────────────────────────────┐
│  Configure Zones - Entrance Camera                     │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌────────────────────────────────────────────────┐    │
│  │                                                 │    │
│  │         [Live Camera Feed / Video Frame]       │    │
│  │                                                 │    │
│  │    🔴────────────────────🔴                    │    │
│  │    │   Entry Line (Zone 1)  │                  │    │
│  │    🔴────────────────────🔴                    │    │
│  │                                                 │    │
│  │         ┌─────────────┐                        │    │
│  │         │  Display    │  ← Zone 2              │    │
│  │         └─────────────┘                        │    │
│  │                                                 │    │
│  └────────────────────────────────────────────────┘    │
│                                                          │
│  Drawing Mode: [Select ▼] [Polygon] [Line] [Delete]   │
│                                                          │
│  Zones:                                                 │
│  ┌────────────────────────────────────────────────┐   │
│  │ ✓ Zone 1: Entry Line (ENTRY_LINE) [Edit][Del] │   │
│  │ ✓ Zone 2: Display Area (DISPLAY)  [Edit][Del] │   │
│  │ [+ Add New Zone]                               │   │
│  └────────────────────────────────────────────────┘   │
│                                                          │
│  [Cancel]                    [Save Zones]              │
└─────────────────────────────────────────────────────────┘
```

---

## 🔧 Implementation Tasks (Prioritized)

### SPRINT 1: Rebranding & Core Setup (Week 1)
**Goal**: Rebrand to Meridian and set up single-store architecture

- [ ] **1.1 Rebrand UI** (4 hours)
  - Change "Store Intel" → "Meridian" everywhere
  - Remove store selector dropdown from sidebar
  - Update favicon, page titles, meta tags
  - Remove "Purplle" references

- [ ] **1.2 Update Database** (2 hours)
  - Add columns to existing tables: `address`, `phone`, `max_cameras` on `stores`; `camera_type`, `status`, `video_file_path`, `position_index`, `deleted_at` on `cameras`; `is_active`, `deleted_at` on `zones`
  - Bootstrap: ensure exactly **one** store row (`MERIDIAN_STORE_ID`); seed if empty
  - Enable pgvector on startup (already in backend lifespan)

- [ ] **1.3 Backend API Updates** (4 hours)
  - Add `GET/PUT /api/v1/store`, `DELETE /api/v1/store/data`
  - Resolve all new routes via `MERIDIAN_STORE_ID` — no multi-store create/list
  - Keep legacy `/stores/{id}/*` as thin wrappers during frontend migration

- [ ] **1.4 Startup checks** (1 hour)
  - Backend: verify Postgres + pgvector + Redis reachable on boot (log clear errors)
  - Edge-node / pipeline: verify `yolov8n.pt` and ReID ONNX exist before processing

### SPRINT 2: Camera Management (Week 2)
**Goal**: Full camera CRUD with 0-6 limit

- [ ] **2.1 Camera List UI** (3 hours)
  - Display current cameras in Store Settings
  - Show camera count (X/6)
  - Empty state when 0 cameras

- [ ] **2.2 Add Camera Modal** (6 hours)
  - Form with camera name, type selection
  - RTSP URL input + test connection
  - Video file upload
  - Webcam selection with permission request
  - Validation: max 6 cameras, unique names

- [ ] **2.3 Edit Camera** (3 hours)
  - Edit modal to update name, RTSP URL
  - Toggle active/inactive status

- [ ] **2.4 Remove Camera** (2 hours)
  - Confirmation modal
  - Soft delete (keep analytics data)
  - Update camera count

- [ ] **2.5 Camera API Integration** (4 hours)
  - POST /api/cameras - Add camera
  - PUT /api/cameras/:id - Update
  - DELETE /api/cameras/:id - Remove
  - GET /api/cameras - List

### SPRINT 3: Zone Configuration (Week 3)
**Goal**: Functional zone drawing canvas with normalized coordinates

**Total Time: 23 hours** (increased from 15 hours to include critical missing tasks)

---

#### **Task 3.1: Camera Frame Display** (5 hours - NEW CRITICAL TASK)

**🔴 CRITICAL: Canvas needs visible background frame**

**RTSP Stream Cameras:**
- [ ] **Backend snapshot endpoint**
  ```python
  @app.get("/api/v1/cameras/{camera_id}/snapshot")
  async def get_camera_snapshot(camera_id: str):
      camera = get_camera(camera_id)
      if camera.camera_type != "rtsp_stream":
          raise HTTPException(400, "Not an RTSP camera")
      
      # Capture frame via OpenCV
      cap = cv2.VideoCapture(camera.rtsp_url)
      ret, frame = cap.read()
      cap.release()
      
      if not ret:
          raise HTTPException(500, "Failed to capture frame")
      
      # Encode as JPEG
      _, buffer = cv2.imencode('.jpg', frame)
      return Response(content=buffer.tobytes(), media_type="image/jpeg")
  ```

- [ ] **Frontend: Display snapshot**
  ```typescript
  <img 
    src={`/api/v1/cameras/${cameraId}/snapshot`} 
    onLoad={(e) => {
      const img = e.target as HTMLImageElement;
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      ctx.drawImage(img, 0, 0);
    }}
  />
  <canvas ref={canvasRef} style="position: absolute; top: 0; left: 0;" />
  ```

**Video File Cameras:**
- [ ] **Backend: Extract frame 0 or frame at 5 seconds**
  ```python
  @app.get("/api/v1/cameras/{camera_id}/snapshot")
  async def get_camera_snapshot(camera_id: str):
      camera = get_camera(camera_id)
      if camera.camera_type != "video_file":
          raise HTTPException(400, "Not a video file camera")
      
      cap = cv2.VideoCapture(camera.video_file_path)
      cap.set(cv2.CAP_PROP_POS_FRAMES, 150)  # Frame at 5 seconds (30fps)
      ret, frame = cap.read()
      cap.release()
      
      _, buffer = cv2.imencode('.jpg', frame)
      return Response(content=buffer.tobytes(), media_type="image/jpeg")
  ```
- [ ] Cache snapshot for 30 seconds to avoid re-extracting

**Webcam Cameras:**
- [ ] **Browser MediaStream API**
  ```typescript
  const stream = await navigator.mediaDevices.getUserMedia({ video: true });
  videoRef.current.srcObject = stream;
  
  // Draw video frame to canvas continuously
  const drawFrame = () => {
    ctx.drawImage(videoRef.current, 0, 0, canvas.width, canvas.height);
    requestAnimationFrame(drawFrame);
  };
  drawFrame();
  ```

- [ ] **Overlay canvas on video**
  ```html
  <div style="position: relative">
    <video ref={videoRef} autoPlay />
    <canvas 
      ref={canvasRef} 
      style="position: absolute; top: 0; left: 0; pointer-events: all" 
    />
  </div>
  ```

---

#### **Task 3.2: Zone Canvas Component** (10 hours)

**Core Canvas Implementation:**
- [ ] HTML5 Canvas overlay on camera frame
- [ ] Mouse event handlers (mousedown, mousemove, mouseup, click)
- [ ] Drawing states (idle, drawing_polygon, drawing_line, editing)

**🔴 CRITICAL: Coordinate Normalization (MANDATORY)**

- [ ] **Store polygon points as normalized (0.0-1.0)** — matches event-engine `ZoneState`
  ```typescript
  // When user clicks canvas
  const normalizedX = event.offsetX / canvas.width;
  const normalizedY = event.offsetY / canvas.height;
  zone.polygon.points.push({ x: normalizedX, y: normalizedY });
  zone.polygon.camera_ids = [cameraId];
  ```

- [ ] **Denormalize when displaying from API**
  ```typescript
  const points = zone.polygon.points; // [{ x: 0.1, y: 0.2 }, ...]
  const pixelCoords = points.map(({ x, y }) => [x * canvas.width, y * canvas.height]);
  // draw polygon with pixelCoords
  ```

- [ ] **Handle canvas resize gracefully**
  - Coordinates stay normalized (0.0-1.0) in database
  - On resize: re-fetch zones and denormalize to new canvas dimensions
  - Zones automatically scale correctly

- [ ] **Why normalization is critical:**
  > Event engine tracks person feet in normalized coordinates (0.0-1.0).
  > If zones are stored in pixels, `shapely.contains(point)` checks fail.
  > Result: ZERO zone events generated (silently breaks heatmaps & dwell time).

**Polygon Drawing Tool (DISPLAY, AISLE, QUEUE zones):**
- [ ] Click to place vertices (visual feedback: colored dots)
- [ ] Double-click or click first vertex to close polygon
- [ ] Minimum 3 vertices validation
- [ ] Display vertex indices for debugging
- [ ] Polygon fill with semi-transparent color
- [ ] Polygon stroke with zone type color

**Line Drawing Tool (ENTRY_LINE zones):**
- [ ] **Implementation: Thin Polygon Approach** (Option A - simpler)
  - User draws line by clicking start and end points
  - Internally convert to thin rectangle polygon
  - Width: 10 pixels normalized (10 / canvas.width)
  - Store as 4-vertex polygon: `[[x1,y1], [x2,y1+w], [x2,y2+w], [x1,y2]]`
  - Works with existing `shapely.contains()` in event engine
  
- [ ] **Visual representation:**
  - Display as line stroke (looks like a line to user)
  - Store as polygon (compatible with event engine)
  - Direction arrow indicator (shows entry direction)

- [ ] **Alternative: Option B (Proper line crossing)**
  - Store as 2 points: `[[x1,y1], [x2,y2]]`
  - Event engine implements crossing detection logic
  - More accurate but requires event-engine code changes
  - **Decision: Use Option A for now** (simpler, works with existing code)

**Edit/Delete Zones:**
- [ ] Click zone to select (highlight border in yellow)
- [ ] Drag vertices to reshape polygon
- [ ] Delete button removes selected zone (soft delete)
- [ ] Escape key to cancel editing

---

#### **Task 3.3: Zone Validation & Warnings** (3 hours)

**Minimum Zone Requirements Check:**
- [ ] When saving zones, check if at least one ENTRY_LINE exists
- [ ] **Warning (don't block save):**
  ```typescript
  const hasEntryLine = zones.some(z => z.zone_type === 'ENTRY_LINE');
  
  if (!hasEntryLine && camera.is_entrance_camera) {
    showWarning({
      title: "⚠️ No Entry Line Defined",
      message: "Footfall counting will be disabled for this camera. Add an ENTRY_LINE zone to track entries and exits.",
      type: "warning"
    });
  }
  ```
- [ ] User can still save (maybe they only want dwell tracking)
- [ ] Display warning icon next to camera in camera list if no ENTRY_LINE

**Coordinate Validation:**
- [ ] Verify all `polygon.points` are in 0.0–1.0 range after normalization
- [ ] Polygon zones: minimum 3 points required
- [ ] Line zones: exactly 2 points required (before converting to polygon)
- [ ] No self-intersecting polygons (optional nice-to-have)

**Zone Name Validation:**
- [ ] Unique names within a camera
- [ ] Auto-suggest names: "Entry Line 1", "Display Area 2", etc.
- [ ] Allow custom names (user can override)

---

#### **Task 3.4: Zone Management UI** (4 hours)

**Zone List Component:**
- [ ] Display all zones for current camera
- [ ] Zone cards with:
  - Zone name (editable inline)
  - Zone type with icon/color
  - Vertex count
  - Active/inactive toggle
  - Edit button (highlights zone on canvas)
  - Delete button (soft delete with confirmation)

**Zone Type Selection:**
- [ ] Dropdown or segmented control
- [ ] Zone types with visual indicators:
  ```
  🚪 ENTRY_LINE  - For footfall counting (crossing detection)
  📦 DISPLAY     - For dwell time tracking (product engagement)
  🛒 AISLE       - For browsing patterns
  🏁 QUEUE       - For checkout line management
  ```

**Drawing Mode Controls:**
- [ ] Button group: [Polygon] [Line] [Select] [Delete]
- [ ] Active mode highlighted
- [ ] Instructions text: "Click to place vertices. Double-click to finish."

**Save/Cancel Actions:**
- [ ] Save Zones button (validates, shows warnings, saves to API)
- [ ] Cancel button (discards unsaved changes, shows confirmation)
- [ ] Dirty state indicator (shows "Unsaved changes" warning)

---

#### **Task 3.5: Zone API Integration** (4 hours)

**API Endpoints:**

**Get zones for camera:**
```http
GET /api/v1/cameras/:cameraId/zones?active=true

Response 200:
[
  {
    "id": "uuid-1",
    "store_id": "meridian-store-uuid",
    "name": "Entry Line",
    "zone_type": "ENTRY_LINE",
    "product_category": null,
    "polygon": {
      "camera_ids": ["uuid-camera"],
      "points": [{"x": 0.0, "y": 0.6}, {"x": 1.0, "y": 0.6}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
    },
    "is_active": true,
    "created_at": "2024-01-15T10:30:00Z"
  }
]
```

**Create zone:**
```http
POST /api/v1/cameras/:cameraId/zones

Body:
{
  "name": "Entry Line",
  "zone_type": "ENTRY_LINE",
  "product_category": null,
  "polygon": {
    "camera_ids": ["uuid-camera"],
    "points": [{"x": 0.0, "y": 0.6}, {"x": 1.0, "y": 0.6}, {"x": 1.0, "y": 1.0}, {"x": 0.0, "y": 1.0}]
  }
}
```

**Update zone:**
```http
PUT /api/v1/zones/:id

Body:
{
  "name": "Main Entry Line",
  "polygon": { "camera_ids": ["uuid-camera"], "points": [...] }
}
```

**Delete zone (soft delete only):**
```http
DELETE /api/v1/zones/:id

UPDATE zones SET is_active = FALSE, deleted_at = NOW() WHERE id = :id
-- Never: DELETE FROM zones WHERE id = :id
```

**Why soft delete?**
- Historical events reference zone names/IDs
- Heatmap data for past dates needs zone definitions
- Analytics charts break if zones are hard deleted
- Example: User views "Yesterday's heatmap" → needs yesterday's active zones

**Event engine filtering:**
```python
# Load active zones for store; filter by camera_id via polygon.camera_ids in memory
active_zones = db.query(Zone).filter(
    Zone.store_id == MERIDIAN_STORE_ID,
    Zone.is_active == True,
).all()
# ZoneState already skips zones where camera_id not in polygon["camera_ids"]
```

---

#### **Sprint 3 Testing Checklist**

**Coordinate Normalization Tests:**
- [ ] Draw zone on 800x600 canvas → Save → Reload
- [ ] Resize canvas to 1920x1080 → Zone still aligns correctly
- [ ] Check database: `polygon.points` values are 0.0–1.0 (not pixels)
- [ ] Event engine test: Person feet at (0.5, 0.5) triggers ZONE_DWELL event

**Frame Display Tests:**
- [ ] RTSP camera: Snapshot loads and displays correctly
- [ ] Video file: Frame extraction works, displays still image
- [ ] Webcam: Live video stream displays, canvas overlay works

**Zone Drawing Tests:**
- [ ] Polygon: Draw 5-vertex polygon → Save → Reload → Vertices intact
- [ ] Line (ENTRY_LINE): Draw line → Save → Stored as 4-vertex polygon
- [ ] Edit: Drag vertex → Save → Reload → New position persisted
- [ ] Delete: Remove zone → `is_active = FALSE` in database

**Soft Delete Tests:**
- [ ] Delete zone today → Historical heatmap for yesterday still shows zone's data
- [ ] Event engine stops generating new events for deleted zone
- [ ] Deleted zones don't appear in zone list (unless "Show inactive" toggled)

**Validation Tests:**
- [ ] Save camera with no ENTRY_LINE → Warning displayed (not blocked)
- [ ] Try to save polygon with 2 vertices → Blocked with error message
- [ ] Try to save 0 zones → Allowed (camera can have no zones initially)
- [ ] Duplicate zone names → Blocked with error

---

#### **Database Schema**

See **🗄️ Database Schema (Authoritative)** at the top of this document. Do not maintain a second zones DDL here.

---

#### **🚨 Critical Implementation Notes for Sprint 3**

**1. COORDINATE NORMALIZATION IS MANDATORY**
```typescript
// ❌ WRONG: pixel values in polygon.points
zone.polygon.points = [{ x: 450, y: 320 }];

// ✅ CORRECT: normalized 0.0–1.0 in polygon.points
zone.polygon.points = points.map(([px, py]) => ({
  x: px / canvas.width,
  y: py / canvas.height,
}));
```

**2. SOFT DELETE ZONES, NOT HARD DELETE**
```python
# ❌ WRONG: Hard delete
db.delete(zone)
db.commit()

# ✅ CORRECT: Soft delete
zone.is_active = False
zone.deleted_at = datetime.utcnow()
db.commit()
```

**3. CAMERA FRAME MUST BE VISIBLE**
Do not leave canvas blank. Implement snapshot endpoint for RTSP/file cameras.

**4. ENTRY_LINE IS A POLYGON, NOT A LINE OBJECT**
Store as 4-vertex thin rectangle polygon to work with shapely.contains().

---

### SPRINT 4: Store Settings & Data Management (Week 4)
**Goal**: Complete Store Settings page

- [ ] **4.1 Store Info Form** (3 hours)
  - Editable store name, address, phone
  - Timezone dropdown (IANA timezones)
  - Save changes

- [ ] **4.2 Clear Data Functionality** (4 hours)
  - "Clear All Data" button in Settings
  - Confirmation modal (requires typing "DELETE")
  - API endpoint: DELETE /api/store/data
  - Clear: visitors, events, transactions, daily_metrics
  - Keep: store info, cameras, zones

- [ ] **4.3 Store API Integration** (2 hours)
  - GET /api/store - Get store details
  - PUT /api/store - Update store info
  - DELETE /api/store/data - Clear analytics

### SPRINT 5: Camera Display Updates (Week 5)
**Goal**: Dynamic 0-6 camera grid

- [ ] **5.1 Dynamic Camera Grid** (4 hours)
  - Responsive grid layout:
    - 0 cameras: Empty state
    - 1-2 cameras: 1 column
    - 3-4 cameras: 2 columns
    - 5-6 cameras: 3 columns
  - Update Live Feeds page

- [ ] **5.2 Camera Status Indicators** (2 hours)
  - Online/Offline badges
  - Processing/Idle status
  - Error states with tooltips

### SPRINT 6: Testing & Polish (Week 6)
**Goal**: Production-ready

- [ ] **6.1 End-to-End Testing** (8 hours)
  - Add camera (all 3 types: RTSP, file, webcam)
  - Configure zones
  - Remove camera (verify data retained)
  - Clear all data
  - Update store info

- [ ] **6.2 Error Handling** (4 hours)
  - Network errors
  - Invalid RTSP URLs
  - Camera limit reached
  - Form validation errors

- [ ] **6.3 Performance Optimization** (4 hours)
  - Load analytics data on startup
  - Optimize camera feed rendering
  - Database query optimization

- [ ] **6.4 Service health** (2 hours)
  - Add Docker healthchecks for `reid-service` and `event-engine`
  - Backend `/health` should report Redis + DB connectivity

- [ ] **6.5 Documentation** (4 hours)
  - User guide for camera setup
  - Zone configuration tutorial
  - Deployment guide
  - API documentation

---

## 🚀 Deployment Configuration

### Docker (use existing root compose)

**Do not use a minimal frontend+backend+db-only compose.** Analytics requires the full stack.

Use the repository root **`docker-compose.yml`**, which already includes:

| Service | Role |
|---------|------|
| `postgres` | **pgvector/pgvector:pg16** (not plain postgres:15) |
| `redis` | Streams + pub/sub between services |
| `reid-service` | Visitor identity matching |
| `event-engine` | Zone state machine → events |
| `backend-api` | REST + SSE |
| `edge-node` | CV pipeline (optional; or use dashboard upload) |
| `frontend-dashboard` | React UI (port 80) |

```bash
cp .env.example .env
# Set POSTGRES_PASSWORD, MERIDIAN_STORE_ID, CAMERA_LIST, etc.
docker compose up -d
```

Healthchecks exist on postgres, redis, backend-api, and frontend. Add checks for reid-service and event-engine when hardening (Sprint 6).

### Environment Variables (.env)
```bash
# Application
VITE_APP_NAME=Meridian
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_MAX_CAMERAS=6

# Single store (fixed UUID — same across edge-node, seed, API)
MERIDIAN_STORE_ID=a1b2c3d4-0001-4000-8000-000000000001
STORE_ID=a1b2c3d4-0001-4000-8000-000000000001  # edge-node alias

# Database (asyncpg URI built by backend from these)
POSTGRES_SERVER=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=<required>
POSTGRES_DB=store_intelligence

# Redis (required for analytics pipeline)
REDIS_URI=redis://redis:6379/0

# File uploads / video
UPLOAD_DIR=./uploads
MAX_FILE_SIZE_MB=500
VIDEO_SOURCE_DIR=./CCTV sources

# Edge processing (2 FPS file / 5 FPS live — do not set to 30)
FPS_TARGET=2

# RTSP
RTSP_TIMEOUT_SECONDS=10
```

---

## 📊 Success Criteria

### Functional Requirements
- ✅ Single store with editable name, address, phone
- ✅ Add/edit/remove cameras (0-6 limit enforced)
- ✅ Support RTSP streams, video files, and webcams
- ✅ Functional zone drawing canvas with polygon/line tools
- ✅ Remove camera keeps historical analytics data
- ✅ Clear all data button with confirmation
- ✅ Dynamic camera grid (0-6 cameras)

### Non-Functional Requirements
- ✅ Self-hosted deployment (Docker)
- ✅ Unlimited data retention
- ✅ Load analytics on startup (fast page switching)
- ✅ Python FastAPI backend
- ✅ Responsive UI (desktop focus)

---

## 🎯 Next Steps

**Immediate Actions** (Sprint 1):
1. Rebrand UI to Meridian; remove store dropdown
2. Add `MERIDIAN_STORE_ID` + `GET/PUT /api/v1/store` endpoints
3. Migrate schema columns (additive only — no table renames)
4. Use root `docker-compose.yml` for all dev/prod self-hosted installs

**Timeline**: 6 weeks to production-ready Meridian (Sprints 1–6 unchanged in scope).

---

## 📋 Plan Revision Log

| Issue | Resolution in this doc |
|-------|------------------------|
| Minimal docker-compose missing workers | Point to full root `docker-compose.yml` |
| postgres:15 without pgvector | Document `pgvector/pgvector:pg16` |
| Early schema missing normalization | Unified `polygon.points` normalized 0.0–1.0 |
| Camera canvas background | Sprint 3 Task 3.1 + `GET .../snapshot` |
| Zones missing `is_active`, `product_category` | In authoritative schema |
| Store missing `min_engaged_dwell_seconds` | In authoritative schema; timezone `Asia/Kolkata` |
| Zone hard delete | Soft delete only; event-engine filters `is_active` |
| ENTRY_LINE geometry | Thin rectangle polygon (Sprint 3 + principles) |
| CASCADE on zones | Removed; zones stay on `store_id` |
| VIDEO_PROCESSING_FPS=30 | Replaced with `FPS_TARGET=2` |
| No ENTRY_LINE warning | Sprint 3 Task 3.3 (unchanged) |
| Integer store id = 1 | Replaced with fixed UUID `MERIDIAN_STORE_ID` |
