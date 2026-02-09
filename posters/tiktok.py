"""
TikTok video uploader using Content Posting API.

Setup:
1. Register at https://developers.tiktok.com
2. Create an app and apply for Content Posting API access
3. Set up OAuth 2.0 and get access token
4. Add credentials to .env

Docs: https://developers.tiktok.com/doc/content-posting-api-get-started

Note: Unaudited apps can only post as PRIVATE (self-only viewing).
To post publicly, your app must pass TikTok's audit process.
"""
import time
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import TIKTOK_ACCESS_TOKEN

TIKTOK_API_URL = "https://open.tiktokapis.com/v2"


def _init_video_upload(access_token, video_path):
    """Initialize a video upload and get the upload URL."""
    file_size = Path(video_path).stat().st_size

    url = f"{TIKTOK_API_URL}/post/publish/inbox/video/init/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    data = {
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": file_size,
            "chunk_size": file_size,  # single chunk upload
            "total_chunk_count": 1,
        },
    }

    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    result = response.json()

    if result.get("error", {}).get("code") != "ok":
        raise RuntimeError(f"TikTok init error: {result}")

    return result["data"]["publish_id"], result["data"]["upload_url"]


def _upload_video_chunk(upload_url, video_path):
    """Upload the video file to TikTok's servers."""
    file_size = Path(video_path).stat().st_size

    headers = {
        "Content-Type": "video/mp4",
        "Content-Length": str(file_size),
        "Content-Range": f"bytes 0-{file_size - 1}/{file_size}",
    }

    with open(video_path, "rb") as f:
        response = requests.put(upload_url, headers=headers, data=f)

    response.raise_for_status()
    return response


def _publish_video(access_token, publish_id, description):
    """Publish the uploaded video."""
    url = f"{TIKTOK_API_URL}/post/publish/status/fetch/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    data = {"publish_id": publish_id}

    # Check publish status
    for attempt in range(30):
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        status = result.get("data", {}).get("status")
        if status == "PUBLISH_COMPLETE":
            return result
        elif status in ("FAILED", "PUBLISH_FAILED"):
            raise RuntimeError(f"TikTok publish failed: {result}")

        time.sleep(5)

    raise TimeoutError("TikTok took too long to publish.")


def upload_to_tiktok(video_path, description):
    """
    Upload a video to TikTok.

    Args:
        video_path: Path to the MP4 file
        description: Video description/caption

    Returns:
        Publish result from TikTok API

    Note:
        - Unaudited apps post as PRIVATE only
        - Max 15 posts per day per creator account
        - Video must be MP4, < 287MB
    """
    if not TIKTOK_ACCESS_TOKEN:
        raise ValueError(
            "Missing TikTok credentials. Set TIKTOK_ACCESS_TOKEN in .env.\n"
            "See: https://developers.tiktok.com/doc/content-posting-api-get-started"
        )

    print("Initializing TikTok upload...")
    publish_id, upload_url = _init_video_upload(TIKTOK_ACCESS_TOKEN, video_path)

    print("Uploading video to TikTok...")
    _upload_video_chunk(upload_url, video_path)

    print("Publishing on TikTok...")
    result = _publish_video(TIKTOK_ACCESS_TOKEN, publish_id, description)
    print("  Published on TikTok!")
    return result


if __name__ == "__main__":
    print("TikTok poster ready.")
    print(f"Token configured: {'Yes' if TIKTOK_ACCESS_TOKEN else 'No'}")
