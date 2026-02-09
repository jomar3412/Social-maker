# Quick Start: Video Auto-Tagging Implementation

This guide gets you from zero to working video auto-tagging in under 30 minutes.

---

## Prerequisites

- Google Cloud account (free trial gives $300 credit)
- Project directory: `/home/markhuerta/Project/socal_maker`
- Virtual environment activated: `source venv/bin/activate`

---

## Step 1: Set Up Google Cloud (10 minutes)

### 1.1 Create GCP Project

```bash
# Login to GCP
gcloud auth login

# Create project
gcloud projects create socal-maker-videos --name="SoCal Maker Videos"

# Set as active project
gcloud config set project socal-maker-videos

# Enable required APIs
gcloud services enable videointelligence.googleapis.com
gcloud services enable storage.googleapis.com
```

### 1.2 Create Cloud Storage Bucket

```bash
# Create bucket in US region
gsutil mb -l us-central1 gs://socal-maker-videos

# Verify creation
gsutil ls
```

### 1.3 Create Service Account

```bash
# Create service account
gcloud iam service-accounts create video-tagger \
  --display-name="Video Auto-Tagger" \
  --description="Service account for automated video tagging"

# Grant permissions
gcloud projects add-iam-policy-binding socal-maker-videos \
  --member="serviceAccount:video-tagger@socal-maker-videos.iam.gserviceaccount.com" \
  --role="roles/videointelligence.user"

gcloud projects add-iam-policy-binding socal-maker-videos \
  --member="serviceAccount:video-tagger@socal-maker-videos.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Create and download JSON key
mkdir -p /home/markhuerta/Project/socal_maker/credentials
gcloud iam service-accounts keys create \
  /home/markhuerta/Project/socal_maker/credentials/gcp_service_account.json \
  --iam-account=video-tagger@socal-maker-videos.iam.gserviceaccount.com

# Verify key was created
ls -lh /home/markhuerta/Project/socal_maker/credentials/gcp_service_account.json
```

---

## Step 2: Install Dependencies (2 minutes)

```bash
cd /home/markhuerta/Project/socal_maker
source venv/bin/activate

# Install Google Cloud libraries
pip install google-cloud-videointelligence google-cloud-storage google-auth

# Verify installation
python -c "from google.cloud import videointelligence_v1; print('Success!')"
```

---

## Step 3: Update .env File (1 minute)

Add to `/home/markhuerta/Project/socal_maker/.env`:

```bash
# Google Cloud Platform
GOOGLE_APPLICATION_CREDENTIALS="/home/markhuerta/Project/socal_maker/credentials/gcp_service_account.json"
GCP_PROJECT_ID="socal-maker-videos"
GCP_STORAGE_BUCKET="socal-maker-videos"

# Auto-tagging settings
AUTO_TAG_MIN_CONFIDENCE=0.80
AUTO_TAG_MAX_TAGS=15
AUTO_TAG_ENABLED=true
```

---

## Step 4: Create Auto-Tagger Module (5 minutes)

Create `/home/markhuerta/Project/socal_maker/generators/auto_tagger.py`:

```python
"""
Auto-tag videos using Google Cloud Video Intelligence API.
"""

import os
import json
from typing import List, Dict, Optional
from pathlib import Path

from google.cloud import videointelligence_v1 as videointelligence
from google.cloud import storage
from google.oauth2 import service_account
from dotenv import load_dotenv

load_dotenv()


class VideoAutoTagger:
    """
    Automatically tag videos using Google Cloud Video Intelligence API.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        credentials_path: Optional[str] = None,
        min_confidence: float = 0.8
    ):
        """
        Initialize auto-tagger.

        Args:
            bucket_name: Cloud Storage bucket name (defaults to .env)
            credentials_path: Path to service account JSON (defaults to .env)
            min_confidence: Minimum confidence score for tags (0.0-1.0)
        """
        self.bucket_name = bucket_name or os.getenv('GCP_STORAGE_BUCKET')
        self.credentials_path = credentials_path or os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
        self.min_confidence = float(os.getenv('AUTO_TAG_MIN_CONFIDENCE', min_confidence))
        self.max_tags = int(os.getenv('AUTO_TAG_MAX_TAGS', 15))

        # Initialize clients
        credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path
        )
        self.storage_client = storage.Client(credentials=credentials)
        self.video_client = videointelligence.VideoIntelligenceServiceClient(
            credentials=credentials
        )

    def upload_video(self, local_path: str, blob_name: Optional[str] = None) -> str:
        """
        Upload video to Cloud Storage.

        Args:
            local_path: Path to local video file
            blob_name: Optional custom blob name (defaults to basename)

        Returns:
            GCS URI (gs://bucket/path)
        """
        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Video file not found: {local_path}")

        bucket = self.storage_client.bucket(self.bucket_name)

        if blob_name is None:
            blob_name = f"videos/{Path(local_path).name}"

        blob = bucket.blob(blob_name)

        print(f"Uploading {local_path} to gs://{self.bucket_name}/{blob_name}")
        blob.upload_from_filename(local_path)

        return f"gs://{self.bucket_name}/{blob_name}"

    def detect_labels(
        self,
        video_uri: str,
        use_shot_mode: bool = True
    ) -> List[Dict[str, any]]:
        """
        Detect labels in video using Video Intelligence API.

        Args:
            video_uri: GCS URI (gs://bucket/path) or local path
            use_shot_mode: Use SHOT_AND_FRAME_MODE for better temporal understanding

        Returns:
            List of dicts with label, confidence, and category
        """
        # Configure label detection
        config = videointelligence.LabelDetectionConfig(
            label_detection_mode=(
                videointelligence.LabelDetectionMode.SHOT_AND_FRAME_MODE
                if use_shot_mode
                else videointelligence.LabelDetectionMode.SHOT_MODE
            )
        )

        # Make API request
        print(f"Processing video: {video_uri}")
        operation = self.video_client.annotate_video(
            request={
                "input_uri": video_uri,
                "features": [videointelligence.Feature.LABEL_DETECTION],
                "video_context": {"label_detection_config": config}
            }
        )

        # Wait for completion (async operation)
        print("Waiting for operation to complete...")
        result = operation.result(timeout=300)

        # Parse results
        segment_labels = result.annotation_results[0].segment_label_annotations
        labels = []

        for label_annotation in segment_labels:
            for segment in label_annotation.segments:
                confidence = segment.confidence

                if confidence >= self.min_confidence:
                    labels.append({
                        'label': label_annotation.entity.description.lower(),
                        'confidence': round(confidence, 3),
                        'category': (
                            label_annotation.category_entities[0].description.lower()
                            if label_annotation.category_entities
                            else None
                        )
                    })

        # Sort by confidence, remove duplicates, limit to max_tags
        labels = sorted(labels, key=lambda x: x['confidence'], reverse=True)
        seen_labels = set()
        unique_labels = []

        for label_data in labels:
            if label_data['label'] not in seen_labels:
                unique_labels.append(label_data)
                seen_labels.add(label_data['label'])

            if len(unique_labels) >= self.max_tags:
                break

        return unique_labels

    def tag_video(
        self,
        local_video_path: str,
        upload: bool = True
    ) -> Dict[str, any]:
        """
        Full workflow: Upload video + detect labels.

        Args:
            local_video_path: Path to local video file
            upload: Upload to Cloud Storage first (required if >10MB)

        Returns:
            Dict with video_uri, auto_tags, and detailed_tags
        """
        # Upload to Cloud Storage
        if upload:
            video_uri = self.upload_video(local_video_path)
        else:
            video_uri = local_video_path

        # Detect labels
        detailed_tags = self.detect_labels(video_uri)

        # Extract just the tag names
        auto_tags = [tag['label'] for tag in detailed_tags]

        return {
            'video_uri': video_uri,
            'auto_tags': auto_tags,
            'detailed_tags': detailed_tags,
            'tag_count': len(auto_tags)
        }

    def delete_video(self, video_uri: str) -> bool:
        """
        Delete video from Cloud Storage (cleanup).

        Args:
            video_uri: GCS URI (gs://bucket/path)

        Returns:
            True if deleted, False if not found
        """
        if not video_uri.startswith('gs://'):
            print(f"Not a GCS URI, skipping deletion: {video_uri}")
            return False

        # Parse bucket and blob from URI
        parts = video_uri.replace('gs://', '').split('/', 1)
        bucket_name = parts[0]
        blob_name = parts[1]

        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_name)

        if blob.exists():
            blob.delete()
            print(f"Deleted {video_uri}")
            return True
        else:
            print(f"Video not found: {video_uri}")
            return False


# CLI usage
if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(description="Auto-tag videos with Google Cloud Video Intelligence")
    parser.add_argument('video_path', help="Path to video file")
    parser.add_argument('--min-confidence', type=float, default=0.8, help="Minimum confidence (0.0-1.0)")
    parser.add_argument('--max-tags', type=int, default=15, help="Maximum number of tags")
    parser.add_argument('--no-upload', action='store_true', help="Skip upload (use local file)")
    parser.add_argument('--delete-after', action='store_true', help="Delete from Cloud Storage after tagging")

    args = parser.parse_args()

    # Initialize tagger
    tagger = VideoAutoTagger(min_confidence=args.min_confidence)
    tagger.max_tags = args.max_tags

    # Tag video
    try:
        result = tagger.tag_video(args.video_path, upload=not args.no_upload)

        print("\n" + "="*60)
        print("VIDEO AUTO-TAGGING RESULTS")
        print("="*60)
        print(f"Video: {args.video_path}")
        print(f"Cloud URI: {result['video_uri']}")
        print(f"\nDetected {result['tag_count']} tags:")
        print("-"*60)

        for tag_data in result['detailed_tags']:
            category = f" ({tag_data['category']})" if tag_data['category'] else ""
            print(f"  • {tag_data['label']:<20} {tag_data['confidence']*100:>5.1f}%{category}")

        print("-"*60)
        print(f"\nTag list (comma-separated):")
        print(", ".join(result['auto_tags']))

        # Cleanup if requested
        if args.delete_after:
            print("\nCleaning up...")
            tagger.delete_video(result['video_uri'])

    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)
```

---

## Step 5: Test with Sample Video (5 minutes)

### 5.1 Generate or Download Test Video

```bash
# Option 1: Use existing video
TEST_VIDEO="/mnt/gdrive/socal_maker/output/test_video.mp4"

# Option 2: Create 5-second test video with FFmpeg
ffmpeg -f lavfi -i color=c=blue:s=1080x1920:d=5 \
       -f lavfi -i anullsrc=r=44100:cl=stereo \
       -vf "drawtext=text='Test Video':fontsize=80:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2" \
       -pix_fmt yuv420p -c:v libx264 -c:a aac -shortest \
       /tmp/test_video.mp4

TEST_VIDEO="/tmp/test_video.mp4"
```

### 5.2 Run Auto-Tagger

```bash
cd /home/markhuerta/Project/socal_maker

# Basic usage
python generators/auto_tagger.py /mnt/gdrive/socal_maker/output/motivation_001.mp4

# With custom settings
python generators/auto_tagger.py "$TEST_VIDEO" \
  --min-confidence 0.7 \
  --max-tags 20 \
  --delete-after
```

### Expected Output

```
Uploading /tmp/test_video.mp4 to gs://socal-maker-videos/videos/test_video.mp4
Processing video: gs://socal-maker-videos/videos/test_video.mp4
Waiting for operation to complete...

============================================================
VIDEO AUTO-TAGGING RESULTS
============================================================
Video: /tmp/test_video.mp4
Cloud URI: gs://socal-maker-videos/videos/test_video.mp4

Detected 8 tags:
------------------------------------------------------------
  • text                  98.5% (media)
  • font                  95.2% (typography)
  • blue                  92.8% (color)
  • graphic design        89.4% (design)
  • rectangle             87.1% (shape)
  • sky                   85.6% (nature)
  • electric blue         83.2% (color)
  • azure                 81.7% (color)
------------------------------------------------------------

Tag list (comma-separated):
text, font, blue, graphic design, rectangle, sky, electric blue, azure
```

---

## Step 6: Integrate into Pipeline (7 minutes)

### 6.1 Update content_history.json Schema

Add `auto_tags` field to your content history:

```json
{
  "video_id": "vid_001",
  "created_at": "2026-02-07T10:00:00Z",
  "niche": "motivation",
  "script": "The obstacle is the way...",
  "manual_tags": ["stoicism", "marcus_aurelius", "motivation"],
  "auto_tags": ["sunset", "mountain", "nature", "text", "sky"],
  "combined_tags": ["stoicism", "marcus_aurelius", "motivation", "sunset", "mountain", "nature", "text", "sky"],
  "video_path": "/mnt/gdrive/socal_maker/output/motivation_001.mp4",
  "video_uri": "gs://socal-maker-videos/videos/motivation_001.mp4"
}
```

### 6.2 Update pipeline.py

Add auto-tagging step after video generation:

```python
# /home/markhuerta/Project/socal_maker/pipeline.py

import os
from generators.auto_tagger import VideoAutoTagger

def generate_video_with_tags(niche: str, video_type: str) -> dict:
    """
    Full pipeline: script → image → voice → video → tags.
    """
    # 1. Generate script (existing code)
    script_data = generate_script(niche, video_type)

    # 2. Generate images (existing code)
    images = generate_images(script_data)

    # 3. Generate voice (existing code)
    audio_path = generate_voice(script_data['text'])

    # 4. Generate video (existing code)
    video_path = create_video(images, audio_path)

    # 5. AUTO-TAG VIDEO (NEW!)
    if os.getenv('AUTO_TAG_ENABLED', 'true').lower() == 'true':
        print("\n=== Auto-tagging video ===")
        tagger = VideoAutoTagger()

        try:
            tag_result = tagger.tag_video(video_path, upload=True)

            # Combine manual tags (from script generator) + auto tags (from Video Intelligence)
            combined_tags = list(set(
                script_data.get('tags', []) +  # Manual tags
                tag_result['auto_tags']         # Auto tags
            ))

            # Update content history
            content_data = {
                'video_id': script_data['video_id'],
                'created_at': script_data['created_at'],
                'niche': niche,
                'script': script_data['text'],
                'manual_tags': script_data.get('tags', []),
                'auto_tags': tag_result['auto_tags'],
                'combined_tags': combined_tags[:30],  # YouTube limit
                'video_path': video_path,
                'video_uri': tag_result['video_uri']
            }

            print(f"✓ Detected {len(tag_result['auto_tags'])} auto-tags")
            print(f"✓ Total tags: {len(combined_tags)}")

        except Exception as e:
            print(f"⚠ Auto-tagging failed: {e}")
            print("Continuing with manual tags only...")
            content_data = {
                'video_id': script_data['video_id'],
                'manual_tags': script_data.get('tags', []),
                'auto_tags': [],
                'combined_tags': script_data.get('tags', [])
            }
    else:
        print("Auto-tagging disabled in .env")
        content_data = {
            'video_id': script_data['video_id'],
            'manual_tags': script_data.get('tags', []),
            'auto_tags': [],
            'combined_tags': script_data.get('tags', [])
        }

    return content_data
```

### 6.3 Update YouTube Poster

Use combined tags when posting:

```python
# /home/markhuerta/Project/socal_maker/posters/youtube_poster.py

def post_video(video_path: str, content_data: dict):
    """Post video to YouTube with combined tags."""

    # Use combined_tags for maximum reach
    tags = content_data.get('combined_tags', [])

    # Add platform-specific tags
    tags.extend(['shorts', 'youtubeshorts', 'viral'])

    body = {
        'snippet': {
            'title': content_data['title'],
            'description': content_data['description'],
            'tags': tags[:30],  # YouTube max 30 tags
            'categoryId': '22'  # People & Blogs
        },
        'status': {
            'privacyStatus': 'public'
        }
    }

    # ... rest of upload code
```

---

## Step 7: Run Full Pipeline Test

```bash
cd /home/markhuerta/Project/socal_maker

# Test full pipeline with auto-tagging
python pipeline.py --niche motivation --type quote

# Check results
cat content_history.json | jq '.[-1]'
```

Expected output in `content_history.json`:

```json
{
  "video_id": "vid_047",
  "created_at": "2026-02-07T11:30:00Z",
  "niche": "motivation",
  "script": "The impediment to action advances action. What stands in the way becomes the way.",
  "manual_tags": ["stoicism", "marcus_aurelius", "motivation", "obstacle", "philosophy"],
  "auto_tags": ["sunset", "mountain", "sky", "nature", "text", "font", "landscape"],
  "combined_tags": [
    "stoicism", "marcus_aurelius", "motivation", "obstacle", "philosophy",
    "sunset", "mountain", "sky", "nature", "text", "font", "landscape"
  ],
  "video_path": "/mnt/gdrive/socal_maker/output/motivation_vid_047.mp4",
  "video_uri": "gs://socal-maker-videos/videos/motivation_vid_047.mp4"
}
```

---

## Troubleshooting

### Error: "No module named 'google.cloud'"

```bash
pip install google-cloud-videointelligence google-cloud-storage
```

### Error: "Could not load credentials from file"

```bash
# Verify file exists
ls -lh /home/markhuerta/Project/socal_maker/credentials/gcp_service_account.json

# Check .env file
grep GOOGLE_APPLICATION_CREDENTIALS .env
```

### Error: "Permission denied" or "403 Forbidden"

```bash
# Re-grant permissions
gcloud projects add-iam-policy-binding socal-maker-videos \
  --member="serviceAccount:video-tagger@socal-maker-videos.iam.gserviceaccount.com" \
  --role="roles/videointelligence.user"
```

### Error: "Video file is too large (>10MB)"

Solution: Always use `upload=True` to upload to Cloud Storage first (handles files up to 2GB).

### Tags are too generic

Increase `min_confidence` in `.env`:

```bash
AUTO_TAG_MIN_CONFIDENCE=0.90
```

---

## Usage Monitoring

### Check API Usage

```bash
# View current month usage
gcloud logging read "resource.type=ml_job AND protoPayload.methodName=google.cloud.videointelligence.v1.VideoIntelligenceService.AnnotateVideo" \
  --limit 100 \
  --format="table(timestamp, protoPayload.authenticationInfo.principalEmail)"

# Count requests this month
gcloud logging read "resource.type=ml_job AND protoPayload.methodName=google.cloud.videointelligence.v1.VideoIntelligenceService.AnnotateVideo AND timestamp>=\"$(date -d 'last month' +%Y-%m-01)\"" \
  --format="value(timestamp)" | wc -l
```

### Check Storage Usage

```bash
# List all videos in bucket
gsutil ls -lh gs://socal-maker-videos/videos/

# Check total storage size
gsutil du -sh gs://socal-maker-videos
```

### Clean Up Old Videos

```bash
# Delete videos older than 30 days
gsutil -m rm $(gsutil ls gs://socal-maker-videos/videos/** | \
  awk -v date="$(date -d '30 days ago' +%s)" '$2 < date {print $3}')
```

---

## Next Steps

1. **Test with 10 videos** to verify accuracy and costs
2. **Integrate into scheduler.py** for automated daily tagging
3. **Set up billing alerts** at $10 threshold (you won't hit it, but good practice)
4. **Monitor tag quality** and adjust `min_confidence` as needed
5. **Consider custom model** (Vertex AI) if you need brand-specific tags

---

## Cost Tracking

Create a simple cost tracker:

```python
# /home/markhuerta/Project/socal_maker/utils/cost_tracker.py

import json
from datetime import datetime
from pathlib import Path

COST_FILE = Path(__file__).parent.parent / "api_costs.json"

def log_video_processing(video_duration_seconds: int):
    """Log video processing for cost tracking."""
    if not COST_FILE.exists():
        COST_FILE.write_text(json.dumps({"total_minutes": 0, "videos": []}))

    data = json.loads(COST_FILE.read_text())
    minutes = video_duration_seconds / 60

    data["total_minutes"] += minutes
    data["videos"].append({
        "timestamp": datetime.now().isoformat(),
        "minutes": round(minutes, 2)
    })

    COST_FILE.write_text(json.dumps(data, indent=2))

    # Calculate cost
    free_tier = 1000
    rate = 0.10  # $0.10/min

    if data["total_minutes"] <= free_tier:
        cost = 0
    else:
        cost = (data["total_minutes"] - free_tier) * rate

    print(f"API Usage: {data['total_minutes']:.1f}/{free_tier} free minutes")
    print(f"Estimated cost this month: ${cost:.2f}")
```

Add to `auto_tagger.py`:

```python
from utils.cost_tracker import log_video_processing

# After successful processing
log_video_processing(video_duration_seconds=30)
```

---

## Summary

You now have:
- ✅ GCP project set up
- ✅ Video Intelligence API enabled
- ✅ Auto-tagger module created
- ✅ Pipeline integration ready
- ✅ Cost tracking implemented

**Monthly cost for 100 videos**: **$0.00** (within free tier)

**Time to implement**: ~30 minutes

**Ready to scale**: Up to 2,000 videos/month for free!
