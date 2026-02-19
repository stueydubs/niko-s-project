#!/bin/bash
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CURRENT_USER="${SUDO_USER:-$(whoami)}"

echo "Installing Conch Shell Phone..."

# Install VLC (headless) if not present
if ! command -v cvlc &> /dev/null; then
    echo "Installing VLC..."
    sudo apt-get update
    sudo apt-get install -y vlc-nox
fi

# Install RPi.GPIO if not present
if ! python3 -c "import RPi.GPIO" 2>/dev/null; then
    echo "Installing RPi.GPIO..."
    sudo apt-get install -y python3-rpi.gpio
fi

# Check for audio files
if [ ! -f "$SCRIPT_DIR/audio/ring.mp3" ]; then
    echo "WARNING: audio/ring.mp3 not found. Place audio files in $SCRIPT_DIR/audio/ before the service starts."
fi

# Template and install service file, then enable
sed -e "s|User=pi|User=$CURRENT_USER|" \
    -e "s|/home/pi/conch|$SCRIPT_DIR|g" \
    "$SCRIPT_DIR/conch.service" | sudo tee /etc/systemd/system/conch.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable conch.service
if ! sudo systemctl start conch.service; then
    echo "ERROR: Service failed to start. Check: sudo journalctl -u conch.service"
    exit 1
fi

echo "Conch Shell Phone installed and running."
echo "Check status: sudo systemctl status conch.service"
echo "View logs: tail -f $SCRIPT_DIR/conch.log"
