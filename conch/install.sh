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
