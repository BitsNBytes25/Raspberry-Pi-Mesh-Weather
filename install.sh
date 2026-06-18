#!/bin/bash

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

PROJECT_NAME="raspberry_pi_mesh_weather"
INSTALL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
UV_PATH="$HOME/.local/bin/uv"

echo "📍 Detected Working Directory: $INSTALL_DIR"

echo "Ensuring Python virtual environment"
uv sync

echo "🛠️ Creating systemd service files..."

# --- 1. MESH WATCHER SERVICE ---
cat <<EOF > mesh-weather.service
[Unit]
Description=Mesh Weather
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$UV_PATH run daemon
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# --- ESCALATION & INSTALLATION ---
echo "🚀 Escalating to root to move files to /etc/systemd/system/..."

sudo mv mesh-weather.service /etc/systemd/system/

echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "✅ Enabling services on boot..."
sudo systemctl enable mesh-weather.service

echo "▶️ Starting services..."
sudo systemctl restart mesh-weather.service

echo "🎉 Installation complete!"
echo "Check status with: systemctl status mesh-weather"