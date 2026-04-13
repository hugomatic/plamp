# Camera Capture API Design

## Summary

Add the first camera feature as a neutral REST API for taking ad-hoc pictures. A capture should behave like an iPhone camera roll shot: take the picture now, store it in a general camera roll, and decide later whether it belongs in a grow album or journal.

This first slice does not add the polished main-page web button or grow gallery. It creates the API, storage foundation, and a small API test page for debugging and documentation.

## Goals

- Add a REST endpoint that takes one camera picture on demand.
- Store pictures outside grow folders so quick framing or visibility checks do not pollute grow history.
- Return enough metadata for a future UI to show the picture immediately.
- Keep the implementation compatible with the existing camera wrapper and metadata style used by `grow/capture_photo.py`.
- Leave grow album attachment and gallery browsing as follow-up slices.
- Add a camera API test page so the endpoint is easy to debug and has a browser-visible curl example.

## Non-Goals

- No polished product "Take picture" button on the main Plamp page in this slice.
- No grow gallery or album UI in this slice.
- No scheduled or hourly capture changes in this slice.
- No image analysis beyond optional brightness metadata, matching the current grow capture behavior.
- No migration of existing grow captures into the camera roll.

## API

Add:

```text
POST /api/camera/captures
```

Behavior:

- Runs the configured camera capture wrapper once.
- Writes a JPG into the neutral camera roll.
- Writes a JSON sidecar beside the image.
- Returns JSON metadata with an `image_url`, not raw image bytes.
- Returns a clear HTTP error if the camera wrapper is missing, fails, or does not produce a non-empty image.

Response shape:

```json
{
  "capture_id": "cap-abc123",
  "timestamp": "2026-04-12T22:10:00+00:00",
  "image_url": "/api/camera/captures/cap-abc123/image",
  "image_path": "data/camera/captures/2026-04-12/cap-abc123.jpg",
  "sidecar_path": "data/camera/captures/2026-04-12/cap-abc123.json",
  "camera_script": "/home/hugo/.openclaw/workspace/scripts/camera-shot.sh",
  "camera_command": ["/home/hugo/.openclaw/workspace/scripts/camera-shot.sh", "/abs/path/to/cap-abc123.jpg"],
  "camera_summary": {
    "timestamp": "2026-04-12_12-10-00",
    "image": "/abs/path/to/cap-abc123.jpg",
    "command": "rpicam-still ...",
    "exit_code": "0",
    "log": "/home/hugo/camera-logs/rpicam-2026-04-12_12-10-00.log"
  },
  "camera_stderr": "",
  "brightness_mean": 123.456
}
```

The exact timestamp and brightness values are generated at capture time. `POST /api/camera/captures` returns JSON so clients can inspect status, logs, and metadata. The image itself is fetched separately through `GET /api/camera/captures/{capture_id}/image`, which returns the JPEG bytes. Paths returned to clients should be repo-relative where possible, with absolute paths retained only inside command/debug fields where they reflect what was executed.

Add:

```text
GET /api/camera/captures/{capture_id}/image
```

Behavior:

- Returns the captured JPEG for a known capture ID.
- Returns 404 if the capture ID cannot be found in the camera roll.
- Does not create or mutate capture metadata.

## Storage

Use a neutral camera roll under local runtime data:

```text
data/camera/captures/YYYY-MM-DD/cap-<token>.jpg
data/camera/captures/YYYY-MM-DD/cap-<token>.json
```

`data/` is already local runtime data and ignored by git. This keeps ad-hoc captures separate from tracked grow config and separate from grow journal artifacts.

The JSON sidecar should use the same plain-file style as grow captures so future tools can list or attach captures without reading server logs.

## Configuration

The first slice should avoid inventing a full camera settings UI. Use this resolution order for the capture wrapper path:

1. A global camera config value if one already exists in `data/config.json`.
2. The current grow config path from `grow/grows/grow-thai-basil-siam-queen-2026-03-27/grow.json` as a transitional default.
3. A clear server error explaining that no camera capture script is configured.

If implementation finds there is no clean global config shape yet, it should add the smallest documented config shape needed, for example:

```json
{
  "camera": {
    "capture_script": "/home/hugo/.openclaw/workspace/scripts/camera-shot.sh"
  }
}
```

The design preference is to avoid hardcoding the wrapper path in Python code.

## API Test Page

Add a camera API test page for debugging and API documentation, not as the polished end-user capture control. Prefer a dedicated route such as:

```text
GET /camera/test
```

The page should:

- show the `POST /api/camera/captures` curl command using the current origin
- provide a button that sends the POST request
- show response status and formatted JSON
- show a preview of the captured image using the returned `image_url`
- keep the page clearly separate from `/timers/test`, which should remain focused on timer APIs

## Components

Add a small camera helper module, for example `plamp_web/camera_capture.py`, responsible for:

- resolving the camera script path
- creating capture IDs and destination paths
- running the wrapper subprocess
- waiting for a non-empty output image
- computing brightness metadata when Pillow can open the file
- writing the sidecar JSON
- returning the metadata dict with `image_url`

Keep `plamp_web/server.py` responsible only for the HTTP route, translating helper errors into `HTTPException` responses.

## Error Handling

Expected failures:

- no camera script configured: return 500 with an actionable message
- configured script path does not exist: return 500 with the missing path
- camera command exits non-zero: return 502 with the command failure and stderr summary
- command exits but image is missing or empty: return 502 with the expected image path
- sidecar write fails: return 500

Do not append grow events for neutral camera-roll captures.

## Follow-Up Slices

After this API works:

1. Add a polished "Take picture" button to the main Plamp page that calls `POST /api/camera/captures` and shows the returned image.
2. Add `GET /api/camera/captures` for recent camera-roll images.
3. Add grow album support, likely by attaching an existing camera-roll capture to a grow through an endpoint such as `POST /api/grows/{grow_id}/captures/{capture_id}`.
4. Add a grow gallery page over attached grow captures.

## Testing

Unit tests should cover the helper without requiring real camera hardware by using a fake capture script that writes a small image to the requested path.

Recommended tests:

- successful capture writes image and sidecar under `data/camera/captures/YYYY-MM-DD/`
- metadata includes capture ID, timestamp, image URL, image path, sidecar path, script path, command, parsed camera summary, stderr, and brightness
- missing script raises a clear helper error
- script that exits successfully but does not write an image raises a clear helper error
- FastAPI route returns successful JSON for a fake helper path or temporary fake config, depending on the final implementation shape
- image route returns JPEG bytes for a known capture ID and 404 for an unknown capture ID
- camera API test page includes the POST curl command, response display elements, and image preview element

Manual validation on hardware:

```bash
curl -X POST http://localhost:8000/api/camera/captures
```

Success means the response points to a new JPG and JSON sidecar under `data/camera/captures/YYYY-MM-DD/`, includes an `image_url`, and that URL returns a real camera shot.
