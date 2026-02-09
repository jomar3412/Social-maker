#!/bin/bash
# =============================================================================
# Google Drive Setup Script for Social Media Content Pipeline
# =============================================================================
# This script helps you mount Google Drive on your Hostinger server
# so you can store assets and outputs in the cloud.
#
# Usage:
#   chmod +x scripts/setup_gdrive.sh
#   ./scripts/setup_gdrive.sh
# =============================================================================

set -e

MOUNT_POINT="/mnt/gdrive"
GDRIVE_FOLDER="Social_Maker"

echo "=========================================="
echo "  Google Drive Setup for Content Pipeline"
echo "=========================================="
echo ""

# Check if rclone is installed
if ! command -v rclone &> /dev/null; then
    echo "[1/4] Installing rclone..."
    curl https://rclone.org/install.sh | sudo bash
else
    echo "[1/4] rclone already installed: $(rclone version | head -n1)"
fi

# Check if Google Drive is already configured
if rclone listremotes | grep -q "gdrive:"; then
    echo "[2/4] Google Drive already configured in rclone"
else
    echo "[2/4] Configuring Google Drive..."
    echo ""
    echo "Follow the prompts:"
    echo "  - Name: gdrive"
    echo "  - Storage: Google Drive (type 'drive' or number)"
    echo "  - Client ID: leave blank (press Enter)"
    echo "  - Client Secret: leave blank (press Enter)"
    echo "  - Scope: 1 (Full access)"
    echo "  - Root folder ID: leave blank"
    echo "  - Service account: leave blank"
    echo "  - Edit advanced config: n"
    echo "  - Auto config: n (for headless server)"
    echo "  - Then follow the link to authorize"
    echo ""
    rclone config
fi

# Create mount point
echo "[3/4] Creating mount point at $MOUNT_POINT..."
sudo mkdir -p $MOUNT_POINT
sudo chown $USER:$USER $MOUNT_POINT

# Create folder structure in Google Drive
echo "[4/4] Creating folder structure in Google Drive..."
rclone mkdir "gdrive:$GDRIVE_FOLDER/assets/backgrounds/motivation"
rclone mkdir "gdrive:$GDRIVE_FOLDER/assets/backgrounds/facts"
rclone mkdir "gdrive:$GDRIVE_FOLDER/assets/music/motivation"
rclone mkdir "gdrive:$GDRIVE_FOLDER/assets/music/facts"
rclone mkdir "gdrive:$GDRIVE_FOLDER/assets/fonts"
rclone mkdir "gdrive:$GDRIVE_FOLDER/output"

echo ""
echo "=========================================="
echo "  Setup Complete!"
echo "=========================================="
echo ""
echo "To mount Google Drive, run:"
echo ""
echo "  rclone mount gdrive:$GDRIVE_FOLDER $MOUNT_POINT --daemon --vfs-cache-mode full"
echo ""
echo "To mount automatically on boot, add to crontab:"
echo ""
echo "  crontab -e"
echo "  @reboot rclone mount gdrive:$GDRIVE_FOLDER $MOUNT_POINT --daemon --vfs-cache-mode full"
echo ""
echo "Then update your .env file:"
echo ""
echo "  ASSETS_DIR=$MOUNT_POINT/assets"
echo "  OUTPUT_DIR=$MOUNT_POINT/output"
echo ""
echo "Upload your assets to Google Drive:"
echo "  - Backgrounds: My Drive/$GDRIVE_FOLDER/assets/backgrounds/motivation/"
echo "  - Backgrounds: My Drive/$GDRIVE_FOLDER/assets/backgrounds/facts/"
echo "  - Music:       My Drive/$GDRIVE_FOLDER/assets/music/"
echo "  - Fonts:       My Drive/$GDRIVE_FOLDER/assets/fonts/"
echo ""
