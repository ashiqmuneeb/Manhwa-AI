import time
import requests
import json
import base64
import logging
import threading
import os
import urllib.parse
import re
from concurrent.futures import ThreadPoolExecutor
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
        endpoint = settings.R2_ENDPOINT_URL.rstrip('/')
        return f"{endpoint}/{settings.R2_BUCKET_NAME}/{filename}"
    except Exception as e:
        logger.error(f"R2 upload failed: {e}")
        return ""

def generate_flux_webtoon_image(prompt: str, scene_id: str, seq_num: int = 1) -> str:
    """
    Generates authentic, high-quality Korean Manhwa comic panels with character consistency using FLUX.
    Includes multi-model fallback (FLUX, Turbo) and automatic retry.
    """
    clean_prompt = re.sub(r'\[.*?\]', '', prompt).strip()
    if "korean webtoon" not in clean_prompt.lower() and "manhwa" not in clean_prompt.lower():
        clean_prompt = f"korean webtoon manhwa style, dynamic lighting, digital cel shading, crisp line art, {clean_prompt}"

    seed = (seq_num * 101) % 99999
    encoded_prompt = urllib.parse.quote(clean_prompt)
    filename = f"scene_{scene_id}.png"
    filepath = os.path.join(STATIC_DIR, filename)

    models = ["flux", "turbo"]
    for model in models:
        flux_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=600&height=800&model={model}&seed={seed}&nologo=true&enhance=true"
        for attempt in range(3):
            try:
                logger.info(f"Requesting character-based Manhwa image (model={model}, attempt={attempt+1}, seed={seed}) for scene {scene_id}...")
                res = requests.get(flux_url, timeout=40)
                if res.status_code == 200 and len(res.content) > 1000:
                    with open(filepath, "wb") as f:
                        f.write(res.content)
                    logger.info(f"Successfully saved Manhwa panel ({len(res.content)} bytes): {filepath}")
                    return f"http://localhost:8000/static/{filename}"
                else:
                    logger.warning(f"Generation attempt {attempt+1} returned code {res.status_code}, length {len(res.content)}")
            except Exception as e:
                logger.warning(f"Generation attempt {attempt+1} failed ({model}): {e}")
                time.sleep(1.5)

    raise Exception("All FLUX and Turbo image generation attempts timed out or failed.")

def generate_mock_image(prompt: str, sequence_num: int, scene_id: str) -> str:
    """
    Generates a fast real FLUX manhwa panel for mock mode so story/characters always match.
    """
    return generate_flux_webtoon_image(prompt, scene_id, sequence_num)



def generate_real_image(prompt: str, scene_id: str, seq_num: int = 1) -> str:
    """
    Tries user's custom Kaggle/GPU ngrok endpoint first.
    If the custom endpoint is offline or fails, falls back to the online FLUX engine automatically.
    """
    if settings.IMAGE_GEN_URL and settings.IMAGE_GEN_URL.strip():
        payload = {"prompt": prompt}
        headers = {"Content-Type": "application/json"}
        
        try:
            logger.info(f"Attempting custom GPU endpoint: {settings.IMAGE_GEN_URL}")
            response = requests.post(settings.IMAGE_GEN_URL, json=payload, headers=headers, timeout=20)
            
            if response.status_code == 200:
                res_json = response.json()
                filename = f"scene_{scene_id}.png"
                filepath = os.path.join(STATIC_DIR, filename)
                
                if "image" in res_json:
                    img_data = base64.b64decode(res_json["image"])
                    with open(filepath, "wb") as f:
                        f.write(img_data)
                    logger.info(f"Saved custom GPU generated image: {filepath}")
                    return f"http://localhost:8000/static/{filename}"
                    
                elif "image_url" in res_json:
                    img_url = res_json["image_url"]
                    res = requests.get(img_url, timeout=20)
                    if res.status_code == 200:
                        with open(filepath, "wb") as f:
                            f.write(res.content)
                        return f"http://localhost:8000/static/{filename}"
                    return img_url
            else:
                logger.warning(f"Custom GPU endpoint returned status {response.status_code}. Falling back to FLUX...")
        except Exception as e:
            logger.warning(f"Custom GPU endpoint failed or timed out: {e}. Falling back to FLUX...")

    # Fallback to high-speed FLUX engine
    return generate_flux_webtoon_image(prompt, scene_id, seq_num)

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
                "panel_type": analysis_results.get("panel_type", "action_scene"),
                "bubble_type": analysis_results.get("bubble_type", "smooth"),
                "sfx_text": analysis_results.get("sfx_text", ""),
                "image_prompt": analysis_results.get("image_prompt")
            })
            prompt = analysis_results.get("image_prompt")
            
        if not prompt:
            prompt = "korean webtoon manhwa action style, dynamic action pose, detailed background, clean art panel"

            
        seq_num = scene.get("sequence_number", 1)
        
        # 2. Trigger generation
        img_url = generate_real_image(prompt, scene_id, seq_num)
            
        # 3. Update scene completion
        update_scene(scene_id, {
            "status": "completed",
            "image_url": img_url,
            "error_message": None
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
    Concurrent multi-threaded worker loop running in background.
    """
    logger.info("Background Manhwa Multi-Threaded Queue worker started (3 workers).")
    executor = ThreadPoolExecutor(max_workers=3)
    
    while True:
        try:
            scene_id = pop_scene_task()
            if scene_id:
                logger.info(f"Worker dispatching scene task: {scene_id}")
                executor.submit(process_scene, scene_id)
                time.sleep(0.5)
            else:
                time.sleep(1.0)
        except Exception as e:
            logger.error(f"Error in worker loop: {e}")
            time.sleep(3.0)


def start_background_worker():
    """
    Spawns the worker thread.
    """
    t = threading.Thread(target=worker_loop, daemon=True)
    t.start()
    return t
