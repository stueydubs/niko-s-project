# Conch Shell Phone — Design Document

## Overview

A physical art installation: a conch shell that acts as a phone. It rings, you pick it up, you hear a message. 30 tracks play in strict sequence over multiple days. Silence is part of the artwork.

**Hardware:** Raspberry Pi 3B+, momentary push-button (GPIO 17), audio output (3.5mm or USB DAC). Generator-powered, expects unclean shutdowns.

## Architecture

Single Python script (`conch.py`) running a polling loop (~10 iterations/sec). No threading, no async, no frameworks.

### State Machine

Three states, represented by a string variable:

```
BOOT → load track index from disk → SILENT (timer uses current track's config)

SILENT:  wait for randomized silence duration → RINGING
RINGING: loop ring.mp3, wait for button press → stop ring → PLAYING
PLAYING: play current track to completion → advance index, save → SILENT
```

- Button presses honored only in RINGING state
- Silence duration randomized between `silence_min` and `silence_max` (minutes) from current track's config
- After track 30, index wraps to track 01; silence uses track 01's config

### Main Loop

`while True` loop with `time.sleep(0.1)`:
- SILENT: check elapsed time against chosen silence duration
- RINGING: check `button_pressed` flag
- PLAYING: check `subprocess.poll()` for cvlc completion

## GPIO & Button

- GPIO 17 (BCM), internal pull-up resistor (`GPIO.PUD_UP`)
- Momentary NO switch: GPIO 17 (pin 11) to GND (pin 9)
- Edge detection: `GPIO.add_event_detect(17, GPIO.FALLING, bouncetime=300)`
- Callback sets `button_pressed = True`; main loop checks and clears it
- Flag cleared/ignored in SILENT and PLAYING states

## Audio Playback

- Ring: `cvlc --loop audio/ring.mp3` via `subprocess.Popen`, killed on button press
- Track: `cvlc --play-and-exit audio/XX.mp3` via `subprocess.Popen`, `.poll()` to detect completion
- All subprocess stdout/stderr suppressed (`DEVNULL`)
- Paths relative to script directory via `os.path.dirname(os.path.abspath(__file__))`

## Track Configuration

```python
TRACK_CONFIG = [
    {"file": "01.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "02.mp3", "silence_min": 20, "silence_max": 25},
    # ... 30 entries total, placeholder values (15-25 min range)
]
```

## Persistence

- `track_state.txt`: single integer (0-29, zero-indexed)
- Atomic write: write to temp file, then `os.replace()` to final path
- Read on boot with fallback to 0 if missing/corrupt
- Updated after each track finishes

## Logging

- Python `logging` with `RotatingFileHandler`
- Max 1MB, 2 backups
- Format: `2026-02-19 14:30:05 [INFO] message`
- Logs: state transitions, track numbers, silence durations, button presses, errors

## Systemd Service

- `After=sound.target multi-user.target`
- `Restart=always`, `RestartSec=5`
- `User=pi`, `WorkingDirectory=/home/pi/conch`
- Crash recovery: main loop wrapped in `try/except` that logs and exits (systemd restarts)

## Deliverables

| File | Purpose | ~Lines |
|------|---------|--------|
| `conch.py` | Main script | ~200 |
| `conch.service` | Systemd unit file | ~15 |
| `install.sh` | Setup script | ~15 |

## Decisions Made

- Boot silence uses current track's silence config (not a fixed delay)
- Track 30 → track 01 wrap uses track 01's silence config
- State file stores only the track index (no timestamps)
- Polling loop approach (vs blocking subprocess or signal-based)
