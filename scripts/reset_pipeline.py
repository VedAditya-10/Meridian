#!/usr/bin/env python3
"""
Reset script: flush stale Redis streams and delete stale visitor data
from the previous (broken RTSP) run so we get a clean tracking baseline.
Run BEFORE starting the edge node for the first time.
"""
import subprocess, sys

def run(cmd):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout.strip() or result.stderr.strip())
    return result.returncode

print("=== Flushing stale Redis streams & consumer groups ===")
# Delete old streams so consumer groups start fresh
run('docker exec si_redis redis-cli DEL telemetry_raw telemetry_resolved')
# Re-create streams with the groups at the correct starting offset
run('docker exec si_redis redis-cli XGROUP CREATE telemetry_raw reid_group $ MKSTREAM')
run('docker exec si_redis redis-cli XGROUP CREATE telemetry_resolved event_engine_group $ MKSTREAM')
print("Redis streams reset.")

print("\n=== Truncating stale tracking data from DB ===")
sql = """
-- Remove old visitor data created during the broken RTSP run
-- We keep transactions, zones, stores - only reset tracking state
TRUNCATE visitor_embeddings;
DELETE FROM events;
DELETE FROM visitors;
-- Reset daily metrics
TRUNCATE daily_store_metrics;
"""
run(f'docker exec si_postgres psql -U postgres -d store_intelligence -c "{sql}"')
print("Database tracking data cleared.")

print("\n=== Done. Ready for fresh edge-node run. ===")
