"""
YouTube Shorts uploader using YouTube Data API v3.

Setup:
1. Create a Google Cloud project at https://console.cloud.google.com
2. Enable "YouTube Data API v3"
3. Create OAuth 2.0 credentials (Desktop app)
4. Download client_secret.json to config/ directory
5. Run this script once to authorize and generate token
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import PROJECT_ROOT

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
CLIENT_SECRETS_FILE = PROJECT_ROOT / "config" / "client_secret.json"
TOKEN_FILE = PROJECT_ROOT / "config" / "youtube_token.json"


def _get_authenticated_service():
    """Build and return an authenticated YouTube API service."""
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = None

    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not CLIENT_SECRETS_FILE.exists():
                raise FileNotFoundError(
                    f"Missing {CLIENT_SECRETS_FILE}. Download it from Google Cloud Console.\n"
                    "See: https://developers.google.com/youtube/v3/guides/uploading_a_video"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_FILE), SCOPES
            )
            creds = flow.run_local_server(port=8080)

        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("youtube", "v3", credentials=creds)


def upload_to_youtube(video_path, title, description, tags=None, category_id="22"):
    """
    Upload a video to YouTube as a Short.

    Args:
        video_path: Path to the MP4 file
        title: Video title (max 100 chars)
        description: Video description
        tags: List of tags
        category_id: YouTube category ID (22 = People & Blogs)

    Returns:
        URL of the uploaded video
    """
    from googleapiclient.http import MediaFileUpload

    youtube = _get_authenticated_service()

    body = {
        "snippet": {
            "title": title[:100],
            "description": description,
            "tags": tags or [],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        resumable=True,
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    print("Uploading to YouTube...")
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"  Upload progress: {int(status.progress() * 100)}%")

    video_id = response["id"]
    video_url = f"https://youtube.com/shorts/{video_id}"
    print(f"  Uploaded: {video_url}")
    return video_url


if __name__ == "__main__":
    # Test authentication
    try:
        service = _get_authenticated_service()
        print("YouTube authentication successful!")
    except Exception as e:
        print(f"YouTube auth error: {e}")
