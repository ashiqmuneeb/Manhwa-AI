import time
import requests
import json
import base64
import logging
import threading
import os
from app.config import settings
from app.database import update_scene, get_supabase, get_scene
from app.queue import pop_scene_task

logger = logging.getLogger(__name__)

# Setup local static files directory relative to the backend root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

# Optional R2 / S3 client setup
s3_client = None
if settings.R2_ENDPOINT_URL and settings.R2_BUCKET_NAME:
    try:
        import boto3
        s3_client = boto3.client(
            's3',
            endpoint_url=settings.R2_ENDPOINT_URL,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY
        )
        logger.info("Cloudflare R2 client initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize R2 boto3 client: {e}")

def upload_image_to_r2(image_bytes: bytes, filename: str) -> str:
    """
    Uploads generated image bytes to Cloudflare R2.
    Returns the public URL if successful, otherwise empty string.
    """
    if not s3_client or not settings.R2_BUCKET_NAME:
        return ""
    try:
        s3_client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=filename,
            Body=image_bytes,
            ContentType='image/png'
        )
        # Construct public URL (endpoint URL + bucket + filename or custom domain)
        endpoint = settings.R2_ENDPOINT_URL.rstrip('/')
        return f"{endpoint}/{settings.R2_BUCKET_NAME}/{filename}"
    except Exception as e:
        logger.error(f"R2 upload failed: {e}")
        return ""

def generate_mock_image(prompt: str, sequence_num: int, scene_id: str) -> str:
    """
    Generates a beautiful placeholder image from Picsum or Placehold.co and saves it locally.
    Simulates a 5-second processing delay.
    """
    logger.info(f"Generating mock panel for scene #{sequence_num}...")
    time.sleep(5.0)  # 5-second simulation delay

    # Use picsum with seed for deterministic beautiful cartoon/comic search
    seed = (sequence_num * 17) % 1000
    mock_url = f"https://picsum.photos/seed/{seed}/600/800"
    
    filename = f"scene_{scene_id}.png"
    filepath = os.path.join(STATIC_DIR, filename)
    
    try:
        logger.info(f"Downloading mock image locally from Picsum: {mock_url}")
        res = requests.get(mock_url, timeout=10)
        if res.status_code == 200:
            with open(filepath, "wb") as f:
                f.write(res.content)
            logger.info(f"Saved mock image locally: {filepath}")
            return f"http://localhost:8000/static/{filename}"
    except Exception as e:
        logger.error(f"Failed to download mock image: {e}. Writing local fallback placeholder.")
        try:
            # Write a 1x1 pixel gray PNG fallback file so the server can host a local image
            fallback_png = (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\rIDATx\x9cc\xb0\xaf\xaf\xae\x00\x03\x00\x01\xbd\x00\xfd\x16k\xae\xab\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            with open(filepath, "wb") as f:
                f.write(fallback_png)
            logger.info(f"Saved local 1x1 PNG fallback to: {filepath}")
            return f"http://localhost:8000/static/{filename}"
        except Exception as we:
            logger.error(f"Failed to write offline fallback image: {we}")
        
    return mock_url


def generate_real_image(prompt: str, scene_id: str) -> str:
    """
    Sends prompt to Kaggle/Stable Diffusion ngrok endpoint.
    Retrieves and saves the output image locally.
    """
    if not settings.IMAGE_GEN_URL:
        raise ValueError("IMAGE_GEN_URL (Kaggle ngrok link) is not configured.")

    payload = {"prompt": prompt}
    headers = {"Content-Type": "application/json"}
    
    logger.info(f"Requesting image from Kaggle endpoint: {settings.IMAGE_GEN_URL}")
    response = requests.post(settings.IMAGE_GEN_URL, json=payload, headers=headers, timeout=120)
    
    if response.status_code != 200:
        raise Exception(f"Kaggle image generator returned status code {response.status_code}: {response.text}")
    
    res_json = response.json()
    filename = f"scene_{scene_id}.png"
    filepath = os.path.join(STATIC_DIR, filename)
    
    # Kaggle endpoint could return {"image": "<base64_data>"} or {"image_url": "..."}
    if "image" in res_json:
        # Image is base64 encoded
        img_data = base64.b64decode(res_json["image"])
        with open(filepath, "wb") as f:
            f.write(img_data)
        logger.info(f"Saved generated image locally: {filepath}")
        return f"http://localhost:8000/static/{filename}"
        
    elif "image_url" in res_json:
        img_url = res_json["image_url"]
        try:
            res = requests.get(img_url, timeout=30)
            if res.status_code == 200:
                with open(filepath, "wb") as f:
                    f.write(res.content)
                logger.info(f"Saved generated image from URL locally: {filepath}")
                return f"http://localhost:8000/static/{filename}"
        except Exception as e:
            logger.error(f"Failed to download generated image from remote URL: {e}")
        return img_url
        
    raise Exception("Unknown response structure from Kaggle endpoint.")

def process_scene(scene_id: str):
    """
    Main job worker logic for a single scene task.
    """
    try:
        # 1. Fetch current scene details
        scene = get_scene(scene_id)
        if not scene:
            logger.error(f"Scene {scene_id} not found in database.")
            return
        
        update_scene(scene_id, {"status": "generating", "error_message": None})
        
        # Perform Gemini analysis if prompt is not yet generated
        prompt = scene.get("image_prompt")
        paragraph_text = scene.get("paragraph_text", "")
        
        if not prompt and paragraph_text:
            logger.info(f"Running Gemini analysis for scene {scene_id}...")
            from app.gemini import analyze_paragraph
            analysis_results = analyze_paragraph(paragraph_text)
            
            # Save parsed fields
            update_scene(scene_id, {
                "prompt_setting": analysis_results.get("prompt_setting"),
                "prompt_actions": analysis_results.get("prompt_actions"),
                "dialogue": analysis_results.get("dialogue"),
                "image_prompt": analysis_results.get("image_prompt")
            })
            prompt = analysis_results.get("image_prompt")
            
        if not prompt:
            prompt = "A manhwa scene, korean webtoon style"
            
        seq_num = scene.get("sequence_number", 1)
        
        # 2. Trigger generation
        if settings.MOCK_IMAGE_GEN:
            img_url = generate_mock_image(prompt, seq_num, scene_id)
        else:
            img_url = generate_real_image(prompt, scene_id)
            
        # 3. Update scene completion
        update_scene(scene_id, {
            "status": "completed",
            "image_url": img_url,
            "updated_at": "now()"
        })
        logger.info(f"Successfully generated and updated panel for scene {scene_id}.")
        
    except Exception as e:
        logger.error(f"Failed to process scene {scene_id}: {e}")
        update_scene(scene_id, {
            "status": "failed",
            "error_message": str(e)
        })

def worker_loop():
    """
    Infinite loop running in background thread to poll queue tasks.
    """
    logger.info("Background Manhwa Queue worker started.")
    while True:
        try:
            scene_id = pop_scene_task()
            if scene_id:
                logger.info(f"Worker picked up scene task: {scene_id}")
                process_scene(scene_id)
            else:
                # Sleep briefly if queue is empty
                time.sleep(2.0)
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            time.sleep(5.0)

def start_background_worker():
    """
    Spawns the worker thread.
    """
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    return t
