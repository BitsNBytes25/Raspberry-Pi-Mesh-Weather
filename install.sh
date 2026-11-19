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

# If the service exists, ensure it is stopped before updating the system.
if [ -e /etc/systemd/system/mesh-weather.service ]; then
	if sudo systemctl is-active mesh-weather >/dev/null; then
		echo "Stopping mesh-weather prior to update"
		sudo systemctl stop mesh-weather
	fi
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

AI_GROUP_ADDED=false

if [ "$(yq -r '.ai.enabled // false' "$CONFIG")" == "true" ]; then
	TOTAL_MEM_MB=$(awk '/^MemTotal:/ {printf "%.0f", $2/1024}' /proc/meminfo)
	if [ "${TOTAL_MEM_MB:-0}" -lt 1980 ]; then
		# Check if the total amount of system memory is too low to enable AI features.
		# Technically the user can run it using swap, but this is REALLY not recommended
		echo "⚠️  WARNING: Only ${TOTAL_MEM_MB} MB of RAM detected. AI support requires ~2 GB."
		echo "     Skipping AI dependencies (torch + sentence-transformers)."
		echo "     The daemon will run, but AI features will be unavailable until installed on a device with more memory."
	else
		# torch by default will install cuda libraries; these are not available on a raspberry pi.
		# Install the CPU version manually to ensure it doesn't try to use cuda.
		echo "Installing CPU version of torch for AI support"
		$UV_PATH pip install torch --index-url https://download.pytorch.org/whl/cpu

		echo "Enabling dependencies for AI command resolver (sentence-transformers)"
		UVCMD+=(--group ai)
		AI_GROUP_ADDED=true
	fi
fi

echo "Installing all Python dependencies"
"${UVCMD[@]}"

# --- Optional: AI command resolver (sentence-transformers) ---------------
#
# The AI dependency group is added to UVCMD above when ai.enabled is true.
# The model (default: sentence-transformers/all-MiniLM-L6-v2) is downloaded
# to the local Hugging Face cache on first daemon load when online.  For an
# offline Pi, point ai.model_path at a local directory containing the model
# files, e.g.:
#
#   huggingface-cli download sentence-transformers/all-MiniLM-L6-v2 --local-dir /path/to/model
if [ "$AI_GROUP_ADDED" = "true" ]; then
	echo "AI command resolver enabled; the model will be downloaded on first run (if online)"
fi

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

echo "Testing daemon..."
if ! $UV_PATH run daemon --test; then
	echo "!! TEST RUN FAILED !!"
	exit 1
fi

echo "▶️ Starting services..."
sudo systemctl start mesh-weather.service

echo "🎉 Installation complete!"
echo "Check status with: systemctl status mesh-weather"
