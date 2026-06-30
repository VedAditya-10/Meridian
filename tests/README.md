# Store Intelligence Testing Strategy

This document outlines the testing approach for the Store Intelligence architecture, ensuring accurate metrics, robust event handling, and pipeline stability.

## 1. Unit Testing Strategy

### 1.1 Funnel Calculation
We use `pytest` to validate the business logic inside the `backend-api` service.
**Target Scenarios:**
- Ensure `conversion_rate_from_previous` does not throw divide-by-zero errors.
- Validate that the footfall accurately counts unique visitors rather than total events.
- Test double-counting prevention algorithms.

### 1.2 Anomaly Generation
**Target Scenarios:**
- Simulate a sudden drop in camera frame rate to trigger a `PIPELINE_STALL` anomaly.
- Simulate an unusual spike in footfall to trigger a `CROWD_SURGE` anomaly.
- Ensure anomalies are properly persisted to PostgreSQL and emitted via Redis Streams.

### 1.3 Event Generation (`event-engine`)
**Target Scenarios:**
- Mock incoming Redis events and verify correct database state transformations.
- Test session expiration logic (e.g., handling visitors who never generate an `EXIT` event).

## 2. Integration Testing

Since the architecture relies heavily on PostgreSQL, Redis, and ReID services:
- We utilize `pytest-asyncio` for async database queries.
- We mock Redis Streams using `fakeredis` or monkeypatching to verify event emission without requiring a live Redis cluster during CI.

## 3. End-to-End (E2E) Testing

Future iterations will incorporate Playwright to test the frontend dashboard:
- Ensure Server-Sent Events (SSE) reconnect automatically.
- Validate that KPI cards update in real-time when mock tracking events are injected into the backend.
