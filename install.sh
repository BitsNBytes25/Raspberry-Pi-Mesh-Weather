#!/bin/bash

if ! command -v uv &> /dev/null; then
	# Install UV
	curl -LsSf https://astral.sh/uv/install.sh | sh
fi

PROJECT_NAME="raspberry_pi_mesh_weather"
INSTALL_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
UV_PATH="$HOME/.local/bin/uv"
CONFIG="$INSTALL_DIR/config.yaml"

echo "📍 Detected Working Directory: $INSTALL_DIR"

if [ ! -e "$CONFIG" ]; then
	echo "ERROR - please copy config.yaml.example to config.yaml and configure it before installing!"
	exit 1
fi

if ! command -v yq &> /dev/null; then
	echo "Installing yq as dependency for installation"
	sudo apt install -y yq
fi

if ! command -v yq &> /dev/null; then
	echo "ERROR - could not install yq!"
	exit 1
fi

# Install base requirements
UVCMD=($UV_PATH sync)

# Install optional requirements
if [ "$(yq -r '.radio.type' "$CONFIG")" == "meshtastic" ]; then
	echo "Enabling dependencies for Meshtastic"
	UVCMD+=(--group radio-meshtastic)
fi
if [ "$(yq -r '.radio.type' "$CONFIG")" == "meshcore" ]; then
	echo "Enabling dependencies for MeshCore"
	UVCMD+=(--group radio-meshcore)
fi
if [ "$(yq -r '.display.enabled' "$CONFIG")" == "true" ]; then
	if [ "$(yq -r '.display.type' "$CONFIG")" == "sh1106" ]; then
		echo "Enabling dependencies for SH1106 display"
		UVCMD+=(--group display-sh1106)
	fi
fi
for SENSOR in $(yq -r '(.sensors // [])[].type' "$CONFIG"); do
	echo "Enabling dependencies for $SENSOR sensor"
	UVCMD+=(--group sensor-$SENSOR)
done

echo "Installing all Python dependencies"
"${UVCMD[@]}"

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