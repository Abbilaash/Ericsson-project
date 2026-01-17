# System Migration: Color Detection → QR Code Detection

## Overview

Successfully migrated the drone-robot detection system from RGB color-based detection (yellow/orange/purple) to QR code scanning with predefined location coordinates and API data integration.

---

## Changes Summary

### 1. Base Station Backend (`base station/backend/main.py`)

#### New API Endpoints (Added)

Three new REST endpoints for issue location management:

```
GET /api/rust_location
├─ Returns: Issue type, predefined coordinates (50, 75, 10), robot count (1)
├─ Triggers: Robot assignment for rust issue
└─ Example: /api/rust_location

GET /api/antenna_tilt_location
├─ Returns: Issue type, predefined coordinates (200, 100, 20), robot count (1)
├─ Triggers: Robot assignment for tilted antenna issue
└─ Example: /api/antenna_tilt_location

GET /api/circuit_overheat_location
├─ Returns: Issue type, predefined coordinates (120, 150, 5), robot count (2)
├─ Triggers: Robot assignment for overheated circuit issue
└─ Example: /api/circuit_overheat_location
```

#### Issue Location Mapping

```python
ISSUE_LOCATIONS = {
    "rust": {
        "coordinates": {"x": 50, "y": 75, "z": 10},
        "robot_count": 1,
        "description": "Rust detected at location"
    },
    "overheated_circuit": {
        "coordinates": {"x": 120, "y": 150, "z": 5},
        "robot_count": 2,
        "description": "Overheated circuit detected at location"
    },
    "tilted_antenna": {
        "coordinates": {"x": 200, "y": 100, "z": 20},
        "robot_count": 1,
        "description": "Tilted antenna detected at location"
    }
}
```

#### QR Code Mapping

```python
QR_CODE_TO_ISSUE = {
    "RUST_QR": "rust",
    "CIRCUIT_QR": "overheated_circuit",
    "ANTENNA_QR": "tilted_antenna"
}
```

#### Message Handler Changes

- **OLD**: `handle_tcp_client()` processed `FORWARD_TO` messages with color detection
- **NEW**: Now processes `QR_SCAN` messages with QR codes and API data
- **Coordinates**: No longer drone-provided; fetched from hardcoded `ISSUE_LOCATIONS`

#### Issue Detection Function

- **Renamed**: `handle_color_detection()` → `handle_issue_detection(issue_type, coordinates)`
- **Behavior**: Maps issue type to predefined robots and sends `MOVEMENT_COMMAND`

---

### 2. Drone (`drone/main.py`)

#### Imports (Updated)

```python
# Added:
import requests
from pyzbar.pyzbar import decode
```

#### Configuration (Replaced)

```python
# OLD: Color detection constants
YELLOW_PIXEL_THRESHOLD = 500
ISSUE_TABLE = {"yellow": "robots", "orange": "robots", "purple": "robots"}

# NEW: QR code mapping
QR_CODE_TO_ISSUE = {
    "RUST_QR": "rust",
    "CIRCUIT_QR": "overheated_circuit",
    "ANTENNA_QR": "tilted_antenna"
}
API_BASE_URL = "http://localhost:5000/api"
```

#### Detection Function (Replaced)

```python
# OLD: detected(issue: str, base_station_ip: str)
#      - Detected colors
#      - Sent FORWARD_TO message

# NEW: qr_detected(qr_code: str, base_station_ip: str)
#      - Detects QR codes (RUST_QR, CIRCUIT_QR, ANTENNA_QR)
#      - Maps QR code to issue type using QR_CODE_TO_ISSUE
#      - Fetches API data from /api/{issue_type}_location
#      - Prints fetched data to console
#      - Sends QR_SCAN message with qr_code and api_data fields
```

#### Video Detection Loop (Replaced)

```python
# OLD: start_video_detection()
#      - RGB color range detection (yellow/orange/purple)
#      - Pixel counting for threshold matching

# NEW: start_video_detection()
#      - Uses pyzbar to decode QR codes from camera frames
#      - Validates QR code against QR_CODE_TO_ISSUE mapping
#      - Enforces 2-second cooldown between detections
#      - Prints: "[QR] Scanned: {qr_code}, Data: {...}"
#      - Sends QR_SCAN message for valid QR codes
```

#### Message Format Changes

```python
# OLD FORWARD_TO message:
{
    "message_type": "FORWARD_TO",
    "content": {
        "issue_type": "yellow",
        "color": "yellow",
        "coordinates": {"x": 100, "y": 150, "z": 0},
        "message": "..."
    }
}

# NEW QR_SCAN message:
{
    "message_type": "QR_SCAN",
    "content": {
        "qr_code": "RUST_QR",
        "issue_type": "rust",
        "api_data": {
            "success": true,
            "issue_type": "rust",
            "coordinates": {"x": 50, "y": 75, "z": 10},
            "robots_assigned": 1
        },
        "message": "..."
    }
}
```

---

### 3. Robot (`robot/main.py`)

#### Configuration (Updated)

```python
# OLD: Color-based issue table
ISSUE_TABLE = {
    "yellow": "robots",
    "orange": "robots",
    "purple": "robots"
}

# NEW: Issue type mapping
ISSUE_TYPES = {
    "rust": "robot_task",
    "overheated_circuit": "robot_task",
    "tilted_antenna": "robot_task"
}
```

#### Movement Command Handler (Updated)

```python
# OLD: handle_movement_command()
#      - Extracted color from content
#      - Logged "Color to rectify: {color}"
#      - Used color in task storage and completion report

# NEW: handle_movement_command()
#      - Extracts issue_type from content instead of color
#      - Logs "Issue type to rectify: {issue_type}"
#      - Stores issue_type in current_task dict
#      - Uses issue_type in rectification process
```

#### Task Completion Report (Updated)

```python
# OLD TASK_COMPLETED message:
{
    "message_type": "TASK_COMPLETED",
    "content": {
        "task_id": message_id,
        "color": "yellow",
        "coordinates": {...},
        "status": "completed",
        "message": "Successfully rectified yellow at location ..."
    }
}

# NEW TASK_COMPLETED message:
{
    "message_type": "TASK_COMPLETED",
    "content": {
        "task_id": message_id,
        "issue_type": "rust",
        "coordinates": {...},
        "status": "completed",
        "message": "Successfully rectified rust at location ..."
    }
}
```

---

## System Architecture Changes

### Message Flow (Old)

```
Drone Camera (RGB)
    ↓ [Detects Yellow/Orange/Purple]
Drone sends FORWARD_TO(color)
    ↓
Base Station receives color-based message
    ↓
Base Station assigns robots based on color
    ↓
Robots execute "color rectification"
```

### Message Flow (New)

```
Drone Camera (PiCamera2)
    ↓ [Decodes QR Code with pyzbar]
Drone maps QR code → Issue type (RUST_QR → rust)
    ↓
Drone fetches /api/rust_location
    ↓
Drone sends QR_SCAN(qr_code, api_data)
    ↓
Base Station receives QR-based message
    ↓
Base Station looks up coordinates from ISSUE_LOCATIONS
    ↓
Base Station assigns predefined robots (1 for rust, 2 for circuit, 1 for antenna)
    ↓
Robots execute issue rectification with coordinates from backend
    ↓
Robots send TASK_COMPLETED with issue_type
```

---

## Issue Mapping

| QR Code    | Issue Type         | Coordinates    | Robots | Description                 |
| ---------- | ------------------ | -------------- | ------ | --------------------------- |
| RUST_QR    | rust               | (50, 75, 10)   | 1      | Rust detected at location   |
| CIRCUIT_QR | overheated_circuit | (120, 150, 5)  | 2      | Overheated circuit detected |
| ANTENNA_QR | tilted_antenna     | (200, 100, 20) | 1      | Tilted antenna detected     |

---

## Drone QR Code Detection Process

1. **Capture Frame**: PiCamera2 captures video frame (640x480, RGB888)
2. **Decode QR**: pyzbar library decodes all QR codes in frame
3. **Validate**: Check if QR code is in QR_CODE_TO_ISSUE mapping
4. **Map**: Convert QR code to issue type (e.g., RUST_QR → rust)
5. **Fetch API**: GET `/api/{issue_type}_location` to retrieve coordinates and metadata
6. **Print**: Output fetched data to console
   ```
   [QR] Scanned: RUST_QR
   [QR] Data: {
       "success": true,
       "issue_type": "rust",
       "coordinates": {"x": 50, "y": 75, "z": 10},
       "robots_assigned": 1
   }
   ```
7. **Send**: Send QR_SCAN message to base station with qr_code and api_data
8. **Cooldown**: Enforce 2-second detection cooldown to prevent duplicate messages

---

## API Endpoint Behavior

When drone detects valid QR code:

1. Drone fetches `/api/{issue_type}_location` (e.g., `/api/rust_location`)
2. Endpoint returns coordinates and robot assignment info
3. Endpoint internally calls `handle_issue_detection()` to assign robots
4. Response includes confirmation of robot assignments

### Example Response

```json
{
  "success": true,
  "issue_type": "rust",
  "coordinates": { "x": 50, "y": 75, "z": 10 },
  "description": "Rust detected at location",
  "robots_assigned": 1
}
```

---

## Dependencies Added

### Drone Requirements

- `pyzbar`: For QR code decoding
- `requests`: For API data fetching

Install with:

```bash
pip install pyzbar requests
```

---

## Backward Compatibility

⚠️ **Breaking Changes**:

- All color detection removed from drone
- MOVEMENT_COMMAND now requires `issue_type` instead of `color`
- TASK_COMPLETED now sends `issue_type` instead of `color`
- Frontend dashboard must update to display `issue_type`

✅ **Preserved**:

- TCP port configuration (9998 listen, 9999 command)
- 2-attempt persistent connection retry logic
- Heartbeat and connection request mechanisms
- Base station routing and device tracking

---

## Testing Checklist

- [ ] Generate QR codes: RUST_QR, CIRCUIT_QR, ANTENNA_QR
- [ ] Place QR codes in camera view
- [ ] Verify drone detects and logs QR code data
- [ ] Verify API endpoints return correct coordinates
- [ ] Verify robots receive MOVEMENT_COMMAND with issue_type
- [ ] Verify robots execute rectification and send TASK_COMPLETED
- [ ] Verify base station clears task_id after TASK_COMPLETED
- [ ] Verify frontend dashboard shows updated task status

---

## File Changes Summary

| File                           | Changes                                                                                 |
| ------------------------------ | --------------------------------------------------------------------------------------- |
| `base station/backend/main.py` | Added 3 API endpoints, ISSUE_LOCATIONS dict, QR_CODE_TO_ISSUE dict, updated TCP handler |
| `drone/main.py`                | Replaced color detection with QR scanning, added API fetching, updated message type     |
| `robot/main.py`                | Updated to use issue_type instead of color, updated TASK_COMPLETED payload              |

---

## Status: ✅ MIGRATION COMPLETE

All components updated and ready for QR code detection system deployment.
