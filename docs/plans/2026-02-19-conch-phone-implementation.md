# Conch Shell Phone Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a production-ready Python script that drives a conch shell phone art installation on a Raspberry Pi 3B+.

**Architecture:** Single-file polling loop state machine (`conch.py`) with three states (silent, ringing, playing). GPIO callback sets a flag for button presses. `cvlc` subprocess handles audio. Track index persists to disk for power-loss recovery.

**Tech Stack:** Python 3, RPi.GPIO, cvlc (VLC CLI), systemd

**Design doc:** `docs/plans/2026-02-19-conch-phone-design.md`

---

### Task 1: Create project structure and conch.py skeleton

**Files:**
- Create: `conch/conch.py`
- Create: `conch/audio/` (empty directory with `.gitkeep`)

**Step 1: Create the directory structure**

```bash
mkdir -p conch/audio
touch conch/audio/.gitkeep
```

**Step 2: Write the conch.py skeleton with imports, constants, and TRACK_CONFIG**

Create `conch/conch.py` with:

```python
#!/usr/bin/env python3
"""Conch Shell Phone — a time-based audio art installation."""

import os
import sys
import time
import random
import signal
import logging
import subprocess
import atexit
from logging.handlers import RotatingFileHandler

# Resolve paths relative to this script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
STATE_FILE = os.path.join(BASE_DIR, "track_state.txt")
LOG_FILE = os.path.join(BASE_DIR, "conch.log")

# GPIO pin (BCM numbering)
BUTTON_PIN = 17

# Polling interval (seconds)
POLL_INTERVAL = 0.1

TRACK_CONFIG = [
    {"file": "01.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "02.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "03.mp3", "silence_min": 18, "silence_max": 22},
    {"file": "04.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "05.mp3", "silence_min": 19, "silence_max": 24},
    {"file": "06.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "07.mp3", "silence_min": 22, "silence_max": 25},
    {"file": "08.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "09.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "10.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "11.mp3", "silence_min": 18, "silence_max": 23},
    {"file": "12.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "13.mp3", "silence_min": 21, "silence_max": 25},
    {"file": "14.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "15.mp3", "silence_min": 19, "silence_max": 24},
    {"file": "16.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "17.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "18.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "19.mp3", "silence_min": 18, "silence_max": 23},
    {"file": "20.mp3", "silence_min": 22, "silence_max": 25},
    {"file": "21.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "22.mp3", "silence_min": 19, "silence_max": 24},
    {"file": "23.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "24.mp3", "silence_min": 16, "silence_max": 21},
    {"file": "25.mp3", "silence_min": 20, "silence_max": 25},
    {"file": "26.mp3", "silence_min": 18, "silence_max": 23},
    {"file": "27.mp3", "silence_min": 21, "silence_max": 25},
    {"file": "28.mp3", "silence_min": 17, "silence_max": 22},
    {"file": "29.mp3", "silence_min": 15, "silence_max": 20},
    {"file": "30.mp3", "silence_min": 19, "silence_max": 24},
]
```

**Step 3: Commit**

```bash
git add conch/
git commit -m "feat: create project structure and conch.py skeleton with track config"
```

---

### Task 2: Add logging setup and persistence functions

**Files:**
- Modify: `conch/conch.py`

**Step 1: Add logging setup function**

Append to `conch/conch.py` after `TRACK_CONFIG`:

```python
def setup_logging():
    logger = logging.getLogger("conch")
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2)
    handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s",
                                           datefmt="%Y-%m-%d %H:%M:%S"))
    logger.addHandler(handler)
    return logger
```

**Step 2: Add persistence functions**

Append after `setup_logging`:

```python
def load_track_index():
    try:
        with open(STATE_FILE, "r") as f:
            index = int(f.read().strip())
            if 0 <= index < len(TRACK_CONFIG):
                return index
    except (FileNotFoundError, ValueError):
        pass
    return 0


def save_track_index(index):
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(str(index))
    os.replace(tmp, STATE_FILE)
```

**Step 3: Verify the functions work (manual quick test)**

Add a temporary block at the bottom to test:

```python
if __name__ == "__main__":
    log = setup_logging()
    log.info("Test log entry")
    save_track_index(5)
    assert load_track_index() == 5
    save_track_index(0)
    assert load_track_index() == 0
    os.remove(STATE_FILE)
    assert load_track_index() == 0  # fallback
    print("All checks passed")
```

Run: `python3 conch/conch.py`
Expected: "All checks passed", `conch/conch.log` contains "Test log entry"

**Step 4: Remove the test block**

Remove the `if __name__` test block added in Step 3 (it was just for verification).

**Step 5: Commit**

```bash
git add conch/conch.py
git commit -m "feat: add logging setup and track state persistence"
```

---

### Task 3: Add GPIO setup and button callback

**Files:**
- Modify: `conch/conch.py`

**Step 1: Add GPIO setup and button callback**

Append after the persistence functions:

```python
button_pressed = False


def on_button_press(channel):
    global button_pressed
    button_pressed = True


def setup_gpio():
    import RPi.GPIO as GPIO
    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    GPIO.add_event_detect(BUTTON_PIN, GPIO.FALLING,
                          callback=on_button_press, bouncetime=300)


def cleanup_gpio():
    try:
        import RPi.GPIO as GPIO
        GPIO.cleanup()
    except Exception:
        pass
```

**Note:** `RPi.GPIO` is imported inside the functions so the script can still be loaded/tested on non-Pi machines (the import only fails when `setup_gpio()` is actually called).

**Step 2: Commit**

```bash
git add conch/conch.py
git commit -m "feat: add GPIO setup and button callback"
```

---

### Task 4: Add audio playback functions

**Files:**
- Modify: `conch/conch.py`

**Step 1: Add playback helper functions**

Append after GPIO functions:

```python
def start_ring(log):
    ring_file = os.path.join(AUDIO_DIR, "ring.mp3")
    log.info("Starting ring loop")
    return subprocess.Popen(
        ["cvlc", "--loop", ring_file],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )


def stop_ring(proc, log):
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.info("Ring stopped")


def start_track(track_index, log):
    track_file = os.path.join(AUDIO_DIR, TRACK_CONFIG[track_index]["file"])
    log.info("Playing track %s", TRACK_CONFIG[track_index]["file"])
    return subprocess.Popen(
        ["cvlc", "--play-and-exit", track_file],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
```

**Step 2: Commit**

```bash
git add conch/conch.py
git commit -m "feat: add audio playback functions (ring and track)"
```

---

### Task 5: Implement the main loop state machine

**Files:**
- Modify: `conch/conch.py`

**Step 1: Write the main function with the state machine**

Append after playback functions:

```python
def main():
    global button_pressed

    log = setup_logging()
    log.info("Conch starting up")

    setup_gpio()
    atexit.register(cleanup_gpio)

    track_index = load_track_index()
    log.info("Loaded track index: %d (%s)", track_index, TRACK_CONFIG[track_index]["file"])

    state = "silent"
    silence_end = 0
    ring_proc = None
    track_proc = None

    # Enter initial silence
    config = TRACK_CONFIG[track_index]
    silence_sec = random.uniform(config["silence_min"], config["silence_max"]) * 60
    silence_end = time.time() + silence_sec
    log.info("Entering SILENT state (%.1f minutes)", silence_sec / 60)

    while True:
        if state == "silent":
            button_pressed = False  # ignore presses during silence
            if time.time() >= silence_end:
                state = "ringing"
                ring_proc = start_ring(log)
                log.info("Entering RINGING state, next track: %s",
                         TRACK_CONFIG[track_index]["file"])

        elif state == "ringing":
            if button_pressed:
                button_pressed = False
                log.info("Button pressed during RINGING")
                stop_ring(ring_proc, log)
                ring_proc = None
                state = "playing"
                track_proc = start_track(track_index, log)
                log.info("Entering PLAYING state")

        elif state == "playing":
            button_pressed = False  # ignore presses during playback
            if track_proc and track_proc.poll() is not None:
                log.info("Track %s finished", TRACK_CONFIG[track_index]["file"])
                track_proc = None
                track_index = (track_index + 1) % len(TRACK_CONFIG)
                save_track_index(track_index)
                log.info("Advanced to track index %d (%s)",
                         track_index, TRACK_CONFIG[track_index]["file"])
                config = TRACK_CONFIG[track_index]
                silence_sec = random.uniform(config["silence_min"],
                                             config["silence_max"]) * 60
                silence_end = time.time() + silence_sec
                state = "silent"
                log.info("Entering SILENT state (%.1f minutes)", silence_sec / 60)

        time.sleep(POLL_INTERVAL)
```

**Step 2: Add the entry point with crash recovery**

Append after `main()`:

```python
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logging.getLogger("conch").info("Shutdown requested (KeyboardInterrupt)")
    except Exception as e:
        logging.getLogger("conch").exception("Fatal error: %s", e)
        sys.exit(1)
```

**Step 3: Commit**

```bash
git add conch/conch.py
git commit -m "feat: implement main loop state machine with crash recovery"
```

---

### Task 6: Create systemd service file

**Files:**
- Create: `conch/conch.service`

**Step 1: Write the service file**

```ini
[Unit]
Description=Conch Shell Phone
After=sound.target multi-user.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/conch
ExecStart=/usr/bin/python3 /home/pi/conch/conch.py
Restart=always
RestartSec=5
StandardOutput=null
StandardError=null

[Install]
WantedBy=multi-user.target
```

**Step 2: Commit**

```bash
git add conch/conch.service
git commit -m "feat: add systemd service file"
```

---

### Task 7: Create install script

**Files:**
- Create: `conch/install.sh`

**Step 1: Write the install script**

```bash
#!/bin/bash
set -e

echo "Installing Conch Shell Phone..."

# Install VLC if not present
if ! command -v cvlc &> /dev/null; then
    echo "Installing VLC..."
    sudo apt-get update
    sudo apt-get install -y vlc
fi

# Copy service file and enable
sudo cp conch.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable conch.service
sudo systemctl start conch.service

echo "Conch Shell Phone installed and running."
echo "Check status: sudo systemctl status conch.service"
echo "View logs: tail -f conch.log"
```

**Step 2: Make it executable**

```bash
chmod +x conch/install.sh
```

**Step 3: Commit**

```bash
git add conch/install.sh
git commit -m "feat: add install script"
```

---

### Task 8: Final review and wiring note

**Files:**
- Modify: `conch/conch.py` (if any issues found during review)

**Step 1: Read through the complete conch.py**

Verify:
- All 30 track entries present in TRACK_CONFIG
- State machine has exactly 3 states
- Button ignored during silent and playing
- Track index wraps correctly (modulo 30)
- Atomic file write uses os.replace
- Logging configured with rotation
- No stdout/stderr output in production
- Script is under 250 lines

**Step 2: Verify file structure matches spec**

```
conch/
├── conch.py
├── conch.service
├── install.sh
└── audio/
    └── .gitkeep
```

**Step 3: Add wiring note as a comment at the top of conch.py**

Add after the docstring:

```python
# Wiring: Momentary NO switch between GPIO 17 (physical pin 11) and GND (physical pin 9).
# No external resistor needed — internal pull-up is enabled in software.
```

**Step 4: Final commit**

```bash
git add conch/conch.py
git commit -m "docs: add wiring note to conch.py"
```

---

## Summary

| Task | Description | Key Files |
|------|------------|-----------|
| 1 | Project structure + skeleton + track config | `conch/conch.py`, `conch/audio/` |
| 2 | Logging + persistence functions | `conch/conch.py` |
| 3 | GPIO setup + button callback | `conch/conch.py` |
| 4 | Audio playback functions | `conch/conch.py` |
| 5 | Main loop state machine + entry point | `conch/conch.py` |
| 6 | Systemd service file | `conch/conch.service` |
| 7 | Install script | `conch/install.sh` |
| 8 | Final review + wiring note | `conch/conch.py` |

**Total estimated script size:** ~200 lines
**Total commits:** 8
