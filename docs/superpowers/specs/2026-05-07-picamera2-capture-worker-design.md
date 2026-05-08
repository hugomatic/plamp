# Picamera2 Capture Worker Design

## Goal

Replace shell-based camera capture with a Python `Picamera2` backend owned by `plamp_web`, and route both manual and scheduled captures through one sequential in-process worker.

## Why This Change

The current camera path is:

- `POST /api/camera/captures`
- `plamp_web.camera_capture.capture_camera_image(...)`
- `scripts/camera-shot.sh`
- `rpicam-still` or `libcamera-still`

That path has three problems:

1. Camera control is outside the Python service.
2. Manual and automatic captures do not have one shared owner.
3. Shell-tool quirks can leak into Plamp behavior, as seen with long output path truncation on the Raspberry Pi host.

`Picamera2` is the intended direction because it keeps the camera stack in Python, makes metadata and controls easier to evolve, and gives the service one place to coordinate camera use.

## Scope

This change covers:

- Python `Picamera2` capture backend inside `plamp_web`
- one sequential worker queue for all captures
- manual capture API using the worker
- scheduled capture loop using `capture_every_seconds`
- runtime status for camera worker state

This change does not cover:

- live preview or streaming
- sidecar metadata files
- image analysis
- multi-process camera daemons
- a dual backend or fallback shell path

## Architecture

### Backend

Add a dedicated camera backend module under `plamp_web` that:

- loads `Picamera2` lazily
- configures a still capture
- applies camera settings from config
- captures to a temporary short path
- moves the final JPEG into the configured repo-relative capture directory
- returns the same capture metadata shape currently exposed by the API

The backend is Python-only. `scripts/camera-shot.sh` is no longer part of the normal service path.

### Worker

Add one in-process camera worker with these properties:

- exactly one worker thread
- queue-based command submission
- sequential capture execution
- one shared path for manual and scheduled captures
- no concurrent camera captures

This is not a separate system service. It is an internal `plamp_web` service object similar in spirit to the Pico monitor ownership model, but simpler.

### Scheduling

Camera scheduling becomes a real service concern:

- each configured camera may set `capture_every_seconds`
- `0` or missing means no automatic capture
- the worker loop maintains due times per configured camera
- scheduled captures enqueue `capture_kind="auto"`
- manual captures enqueue `capture_kind="manual"`

If multiple cameras are due at the same time, they are processed sequentially in camera-id order.

## Data and API Contract

### Config

Keep the existing camera config shape:

```json
{
  "cameras": {
    "rpicam_cam0": {
      "capture_dir": "grow/grows/grow-basil/captures",
      "capture_every_seconds": 3600,
      "autofocus_mode": "auto",
      "autofocus_delay_ms": 1500
    }
  }
}
```

No new required config is introduced for this migration.

### Capture Result

Keep the existing API response fields where they still make sense:

- `capture_id`
- `timestamp`
- `capture_kind`
- `image_url`
- `image_path`
- `camera_id`
- `brightness_mean`

Replace shell-specific fields with backend-specific fields:

- remove `camera_script`
- remove `camera_command`
- remove `camera_stderr`
- replace shell summary with a Python/backend summary that can include:
  - `backend: "picamera2"`
  - `camera_id`
  - `captured_at`
  - optional autofocus or capture metadata if available

The image URLs and capture listing behavior stay unchanged.

### Runtime Status

Expose camera worker runtime state in `/api/runtime` and the settings page. Minimum useful fields:

- `state`
- `available`
- `last_capture_at`
- `last_error`
- `queue_depth`
- `scheduled_cameras`

## Error Handling

Failures must be explicit and local:

- if `Picamera2` is not importable, capture requests fail with a clear `502` or `500` describing the missing dependency
- if no camera is available, capture requests fail clearly
- if the target `capture_dir` is invalid, behavior stays as it is now
- if a capture fails, the worker continues running and records the last error
- manual capture returns the error to the caller
- scheduled capture logs the error and updates runtime state

There is no fallback to shell tools.

## Testing

Tests must cover:

- `Picamera2` backend import failure
- successful capture path writing into configured capture directory
- worker serialization for manual requests
- scheduled capture enqueue/execution
- API response shape after backend migration
- runtime status exposure

Use fakes or patches for `Picamera2`. Do not depend on real camera hardware in unit tests.

## Migration Notes

The short-path temp capture workaround remains conceptually useful, but it moves into the Python backend:

- capture to a short temporary path such as `/tmp/plamp-...jpg`
- rename into the final grow path only after a successful capture

This keeps the public behavior stable while removing the shell script from the main path.
