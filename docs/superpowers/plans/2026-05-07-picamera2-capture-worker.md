# Picamera2 Capture Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace shell-based camera capture with a Python `Picamera2` backend owned by `plamp_web`, and route both manual and scheduled captures through one sequential worker.

**Architecture:** `plamp_web.camera_capture` keeps capture-path and listing logic, while a new Python backend performs the actual still capture and a small worker in `plamp_web.server` owns sequential execution for manual and scheduled requests. The API and UI stay stable where possible, but shell-specific response fields are removed.

**Tech Stack:** Python, FastAPI, Picamera2, Pillow, unittest

---

## File Map

- Modify: `plamp_web/camera_capture.py`
- Modify: `plamp_web/server.py`
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_camera_capture.py`
- Modify: `tests/test_camera_api.py`
- Modify: `tests/test_pages.py`
- Modify: `README.md`
- Keep but demote from primary path: `scripts/camera-shot.sh`

### Task 1: Define backend behavior with failing tests

**Files:**
- Modify: `tests/test_camera_capture.py`
- Modify: `tests/test_camera_api.py`

- [ ] **Step 1: Write failing tests for Picamera2 backend behavior**

Add tests for:

- import failure produces a clear `CameraCaptureError`
- successful backend capture writes JPEG to configured `capture_dir`
- response metadata includes `camera_summary.backend == "picamera2"`
- shell-specific response fields are absent

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `uv run python -m unittest tests.test_camera_capture tests.test_camera_api -q`

Expected: failures because the code still depends on the shell script path and old metadata shape.

- [ ] **Step 3: Implement the minimal backend changes in `plamp_web/camera_capture.py`**

Add:

- lazy `Picamera2` import helper
- capture helper that saves to a short temp JPEG path
- move to final `image_path`
- backend-shaped summary data

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `uv run python -m unittest tests.test_camera_capture tests.test_camera_api -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plamp_web/camera_capture.py tests/test_camera_capture.py tests/test_camera_api.py
git commit -m "Use Picamera2 for camera capture"
```

### Task 2: Add sequential camera worker and runtime state

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `tests/test_camera_api.py`

- [ ] **Step 1: Write failing tests for queued capture ownership**

Add tests for:

- manual capture requests route through one worker-owned function
- worker state is visible in runtime output
- capture failure updates runtime state with `last_error`

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `uv run python -m unittest tests.test_camera_api -q`

Expected: failures because there is no camera worker or runtime state yet.

- [ ] **Step 3: Implement minimal worker support**

Add in `plamp_web/server.py`:

- a `CameraWorker` class
- queue-based manual capture submission
- worker status snapshot
- startup and shutdown integration

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `uv run python -m unittest tests.test_camera_api -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_camera_api.py
git commit -m "Add Picamera2 camera worker"
```

### Task 3: Implement scheduled captures through the same worker

**Files:**
- Modify: `plamp_web/server.py`
- Modify: `tests/test_camera_api.py`

- [ ] **Step 1: Write failing tests for automatic capture scheduling**

Add tests for:

- configured `capture_every_seconds > 0` becomes a scheduled camera
- due cameras enqueue `capture_kind="auto"`
- multiple due cameras are processed sequentially

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `uv run python -m unittest tests.test_camera_api -q`

Expected: failures because no scheduler loop exists.

- [ ] **Step 3: Implement the smallest scheduler loop inside the camera worker**

Use:

- per-camera due timestamps
- config reload on startup and after settings save
- ordered sequential processing

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `uv run python -m unittest tests.test_camera_api -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plamp_web/server.py tests/test_camera_api.py
git commit -m "Schedule automatic Picamera2 captures"
```

### Task 4: Update UI and docs to match the new backend

**Files:**
- Modify: `plamp_web/pages.py`
- Modify: `tests/test_pages.py`
- Modify: `README.md`

- [ ] **Step 1: Write failing tests for visible backend/runtime text changes**

Add tests for:

- camera UI and API test page no longer imply shell-script execution
- runtime view can show camera worker state

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `uv run python -m unittest tests.test_pages -q`

Expected: failures until the page copy and runtime rendering are updated.

- [ ] **Step 3: Implement minimal page and README updates**

Update:

- API test page copy
- settings/runtime copy
- README camera stack description

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `uv run python -m unittest tests.test_pages -q`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add plamp_web/pages.py tests/test_pages.py README.md
git commit -m "Document Picamera2 camera backend"
```

### Task 5: Full verification

**Files:**
- Verify: `plamp_web/camera_capture.py`
- Verify: `plamp_web/server.py`
- Verify: `plamp_web/pages.py`
- Verify: `tests/test_camera_capture.py`
- Verify: `tests/test_camera_api.py`
- Verify: `tests/test_pages.py`

- [ ] **Step 1: Run the full targeted verification suite**

Run: `uv run python -m unittest tests.test_camera_capture tests.test_camera_api tests.test_pages -q`

Expected: PASS

- [ ] **Step 2: Run one live capture on hardware if Picamera2 is installed**

Run: `curl -sS -X POST 'http://127.0.0.1:8000/api/camera/captures?camera_id=rpicam_cam0'`

Expected: JSON success with a real `image_path`

- [ ] **Step 3: Commit final integration if needed**

```bash
git add plamp_web/camera_capture.py plamp_web/server.py plamp_web/pages.py tests/test_camera_capture.py tests/test_camera_api.py tests/test_pages.py README.md
git commit -m "Migrate camera captures to Picamera2"
```
