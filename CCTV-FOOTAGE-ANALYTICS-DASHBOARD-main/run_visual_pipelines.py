import subprocess
import os
import sys
import time

cameras = [
    {"id": "cam-1", "path": "CCTV sources/entry 1.mp4"},
    {"id": "cam-2", "path": "CCTV sources/entry 2.mp4"},
    {"id": "cam-3", "path": "CCTV sources/billing_area.mp4"},
    {"id": "cam-4", "path": "CCTV sources/zone.mp4"},
]

print("=========================================================================")
print("  Store Intelligence Platform - Parallel Visual Pipeline Runner  ")
print("=========================================================================")
print("Connecting to local Redis at: localhost:6379")
print("Press Ctrl+C in this window at any time to close all pipelines.")
print("-------------------------------------------------------------------------")

processes = []
try:
    for i, cam in enumerate(cameras):
        # Verify video source exists
        if not os.path.exists(cam["path"]):
            print(f"ERROR: Video source file not found: {cam['path']}")
            continue

        env = os.environ.copy()
        env["REDIS_URI"] = "redis://localhost:6379/0"
        env["STORE_ID"] = "a1b2c3d4-0001-4000-8000-000000000001"
        env["CAMERA_ID"] = cam["id"]
        env["VIDEO_PATH"] = cam["path"]
        env["REID_MODEL_PATH"] = "edge-node/weights/fastreid_r50.onnx"
        env["SHOW_VIDEO"] = "true"
        
        # Add python path to ensure edge-node imports resolve correctly
        env["PYTHONPATH"] = os.path.abspath("edge-node")

        print(f"Starting pipeline {i+1}/4: {cam['id']} ({cam['path']}) ...")
        proc = subprocess.Popen([sys.executable, "edge-node/src/main.py"], env=env)
        processes.append(proc)
        # Small delay to stagger YOLO model initialization memory spike
        time.sleep(1.0)

    print("-------------------------------------------------------------------------")
    print(f"Successfully launched {len(processes)} visual pipeline windows.")
    print("Keep this terminal open to keep the processes running.")
    
    # Wait for all processes to complete
    for p in processes:
        p.wait()

except KeyboardInterrupt:
    print("\n[Ctrl+C] Terminating all active visual pipelines...")
finally:
    for p in processes:
        if p.poll() is None:
            p.terminate()
            p.wait()
    print("All processes successfully cleaned up.")
