#!/bin/bash

# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh

PROJECT_NAME="raspberry_pi_mesh_weather"
INSTALL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
UV_PATH="$HOME/.local/bin/uv"

echo "📍 Detected Working Directory: $INSTALL_DIR"

echo "Ensuring Python virtual environment"
if [ -e "$INSTALL_DIR/.venv" ]; then
	uv sync
fi

echo "🛠️ Creating systemd service files..."

# --- 1. MESH WATCHER SERVICE ---
cat <<EOF > mesh-watcher.service
[Unit]
Description=Meshcore Radio Watcher
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$UV_PATH run meshcore
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# --- 2. SENSOR WATCHER SERVICE ---
cat <<EOF > sensor-watcher.service
[Unit]
Description=BME280 Sensor Watcher
After=mnt-meshdata.mount

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$UV_PATH run sensors
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# --- 3. DISPLAY WATCHER SERVICE ---
cat <<EOF > display-watcher.service
[Unit]
Description=OLED Dashboard Display
After=sensor-watcher.service mesh-watcher.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$UV_PATH run display
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# --- ESCALATION & INSTALLATION ---
echo "🚀 Escalating to root to move files to /etc/systemd/system/..."

sudo mv mesh-watcher.service /etc/systemd/system/
sudo mv sensor-watcher.service /etc/systemd/system/
sudo mv display-watcher.service /etc/systemd/system/

echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "✅ Enabling services on boot..."
sudo systemctl enable mesh-watcher.service
sudo systemctl enable sensor-watcher.service
sudo systemctl enable display-watcher.service

echo "▶️ Starting services..."
sudo systemctl restart mesh-watcher.service
sudo systemctl restart sensor-watcher.service
sudo systemctl restart display-watcher.service

echo "🎉 Installation complete!"
echo "Check status with: systemctl status display-watcher"