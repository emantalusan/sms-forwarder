#!/bin/bash

# Check if install directory is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <install_directory>"
    echo "Example: $0 /opt/sms-forwarder"
    exit 1
fi

INSTALL_DIR="$1"
SERVICE_NAME="sms-forwarder"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$INSTALL_DIR/venv"
REQUIREMENTS_FILE="$SCRIPT_DIR/requirements.txt"

# Ensure requirements.txt exists
if [ ! -f "$REQUIREMENTS_FILE" ]; then
    echo "Error: requirements.txt not found in $SCRIPT_DIR"
    exit 1
fi

# Update package list and install dependencies
echo "Updating package list and installing dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip

# Create install directory if it doesn't exist
echo "Creating install directory at $INSTALL_DIR..."
sudo mkdir -p "$INSTALL_DIR"
sudo chown $USER:$USER "$INSTALL_DIR"

# Copy files to install directory
echo "Copying application files to $INSTALL_DIR..."
cp -r "$SCRIPT_DIR"/* "$INSTALL_DIR/"
cd "$INSTALL_DIR"

# Create and activate virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"

# Install Python dependencies
echo "Installing Python dependencies from requirements.txt..."
pip install --upgrade pip
pip install -r "$REQUIREMENTS_FILE"

# Deactivate virtual environment
deactivate

# Create systemd service file
echo "Creating systemd service file..."
cat << EOF | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null
[Unit]
Description=SMS Forwarder Service
After=network.target

[Service]
ExecStart=$VENV_DIR/bin/python $INSTALL_DIR/main.py
WorkingDirectory=$INSTALL_DIR
Restart=always
User=$USER
Group=$USER
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd, enable, and start the service
echo "Configuring and starting the $SERVICE_NAME service..."
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

# Check service status
echo "Checking service status..."
sleep 2
sudo systemctl status "$SERVICE_NAME" --no-pager

echo "Installation complete! SMS Forwarder is installed at $INSTALL_DIR and running as a service."
echo "To check logs: sudo journalctl -u $SERVICE_NAME -f"
echo "To stop the service: sudo systemctl stop $SERVICE_NAME"
echo "To restart the service: sudo systemctl restart $SERVICE_NAME"