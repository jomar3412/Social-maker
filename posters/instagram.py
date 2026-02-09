"""
Instagram Reels uploader using Meta Graph API.

Setup:
1. Create a Facebook App at https://developers.facebook.com
2. Set app type to "Business"
3. Add Instagram Graph API product
4. Connect your Instagram Business/Creator account
5. Generate a long-lived access token
6. Add token and account ID to .env

Docs: https://developers.facebook.com/docs/instagram-api/guides/content-publishing
"""
import time
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import INSTAGRAM_ACCESS_TOKEN, INSTAGRAM_BUSINESS_ACCOUNT_ID

GRAPH_API_URL = "https://graph.facebook.com/v21.0"


def _create_media_container(video_url, caption):
    """
    Step 1: Create a media container for the Reel.

    Note: Instagram requires the video to be hosted at a public URL.
    You'll need to upload the video to a public server first (e.g., S3, your own server).
    """
    url = f"{GRAPH_API_URL}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media"
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }

    response = requests.post(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["id"]


def _check_container_status(container_id):
    """Check if the media container is ready for publishing."""
    url = f"{GRAPH_API_URL}/{container_id}"
    params = {
        "fields": "status_code",
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }

    response = requests.get(url, params=params)
    response.raise_for_status()
    return response.json().get("status_code")


def _publish_media(container_id):
    """Step 2: Publish the media container."""
    url = f"{GRAPH_API_URL}/{INSTAGRAM_BUSINESS_ACCOUNT_ID}/media_publish"
    params = {
        "creation_id": container_id,
        "access_token": INSTAGRAM_ACCESS_TOKEN,
    }

    response = requests.post(url, params=params)
    response.raise_for_status()
    return response.json()


def upload_to_instagram(video_path, caption, video_url=None):
    """
    Upload a Reel to Instagram.

    Args:
        video_path: Local path to video (for reference/logging)
        caption: Post caption with hashtags
        video_url: Public URL where the video is hosted.
                   Instagram requires a publicly accessible URL.

    Returns:
        Media ID of the published post

    Note:
        You need to host the video at a public URL first.
        Options:
        - Upload to a simple HTTP server
        - Use ngrok to expose a local server
        - Upload to S3/CloudFront
        - Use a service like Cloudinary
    """
    if not INSTAGRAM_ACCESS_TOKEN or not INSTAGRAM_BUSINESS_ACCOUNT_ID:
        raise ValueError(
            "Missing Instagram credentials. Set INSTAGRAM_ACCESS_TOKEN and "
            "INSTAGRAM_BUSINESS_ACCOUNT_ID in your .env file."
        )

    if not video_url:
        raise ValueError(
            "Instagram requires a public video URL. Upload the video to a "
            "public server first, then pass the URL here.\n"
            "Tip: Use `python -m http.server 8000` + ngrok for testing."
        )

    print("Creating Instagram media container...")
    container_id = _create_media_container(video_url, caption)

    # Wait for container to finish processing
    print("Waiting for Instagram to process video...")
    for attempt in range(30):
        status = _check_container_status(container_id)
        if status == "FINISHED":
            break
        elif status == "ERROR":
            raise RuntimeError("Instagram rejected the video.")
        time.sleep(5)
    else:
        raise TimeoutError("Instagram took too long to process the video.")

    # Publish
    print("Publishing to Instagram...")
    result = _publish_media(container_id)
    media_id = result.get("id", "unknown")
    print(f"  Published! Media ID: {media_id}")
    return media_id


if __name__ == "__main__":
    print("Instagram poster ready.")
    print(f"Account configured: {'Yes' if INSTAGRAM_BUSINESS_ACCOUNT_ID else 'No'}")
    print(f"Token configured: {'Yes' if INSTAGRAM_ACCESS_TOKEN else 'No'}")
