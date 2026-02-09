#!/bin/bash
# Quick mount/unmount script for Google Drive

MOUNT_POINT="/mnt/gdrive"
GDRIVE_FOLDER="Social_Maker"

case "$1" in
    mount)
        echo "Mounting Google Drive to $MOUNT_POINT..."
        rclone mount gdrive:$GDRIVE_FOLDER $MOUNT_POINT \
            --daemon \
            --vfs-cache-mode full \
            --vfs-cache-max-size 5G \
            --vfs-read-chunk-size 32M \
            --vfs-read-chunk-size-limit 256M \
            --buffer-size 32M \
            --dir-cache-time 72h \
            --log-file=/tmp/rclone.log
        sleep 2
        if mountpoint -q $MOUNT_POINT; then
            echo "Mounted successfully!"
            echo "Assets: $MOUNT_POINT/assets"
            echo "Output: $MOUNT_POINT/output"
        else
            echo "Mount failed. Check /tmp/rclone.log"
        fi
        ;;
    unmount|umount)
        echo "Unmounting Google Drive..."
        fusermount -u $MOUNT_POINT 2>/dev/null || sudo umount $MOUNT_POINT
        echo "Unmounted."
        ;;
    status)
        if mountpoint -q $MOUNT_POINT; then
            echo "Google Drive is mounted at $MOUNT_POINT"
            echo ""
            echo "Contents:"
            ls -la $MOUNT_POINT
        else
            echo "Google Drive is NOT mounted"
        fi
        ;;
    *)
        echo "Usage: $0 {mount|unmount|status}"
        exit 1
        ;;
esac
