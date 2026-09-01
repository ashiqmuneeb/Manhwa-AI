import redis
import requests
from app.config import settings
import logging

logger = logging.getLogger(__name__)

# Standard Redis client (TCP protocol)
redis_client = None

if settings.REDIS_URL:
    try:
        redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info("Connected to Upstash Redis via TCP protocol.")
    except Exception as e:
        logger.error(f"Failed to connect to Redis TCP: {e}")

# In-memory queue fallback if no Redis is available
_mock_queue = []

QUEUE_NAME = "manhwa_scene_queue"

def push_scene_task(scene_id: str) -> bool:
    """
    Pushes a scene ID to the end (left) of the queue.
    """
    # 1. TCP Redis Client
    if redis_client:
        try:
            redis_client.lpush(QUEUE_NAME, scene_id)
            return True
        except Exception as e:
            logger.error(f"Redis TCP LPUSH error: {e}")
            
    # 2. HTTP REST Upstash Client
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{settings.UPSTASH_REDIS_REST_URL.rstrip('/')}/lpush/{QUEUE_NAME}/{scene_id}"
            headers = {"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"}
            response = requests.post(url, headers=headers, timeout=5)
            if response.status_code == 200:
                return True
            logger.error(f"Upstash REST LPUSH error: {response.text}")
        except Exception as e:
            logger.error(f"Upstash REST LPUSH exception: {e}")
            
    # 3. Fallback to Memory Queue
    logger.warning("No Redis client configured. Appending task to local memory queue.")
    _mock_queue.insert(0, scene_id)
    return True

def pop_scene_task() -> str:
    """
    Pops a scene ID from the front (right) of the queue. Returns None if empty.
    """
    # 1. TCP Redis Client
    if redis_client:
        try:
            val = redis_client.rpop(QUEUE_NAME)
            if val:
                return val
        except Exception as e:
            logger.error(f"Redis TCP RPOP error: {e}")
            
    # 2. HTTP REST Upstash Client
    if settings.UPSTASH_REDIS_REST_URL and settings.UPSTASH_REDIS_REST_TOKEN:
        try:
            url = f"{settings.UPSTASH_REDIS_REST_URL.rstrip('/')}/rpop/{QUEUE_NAME}"
            headers = {"Authorization": f"Bearer {settings.UPSTASH_REDIS_REST_TOKEN}"}
            response = requests.post(url, headers=headers, timeout=5)
            if response.status_code == 200:
                res_data = response.json()
                # Upstash REST rpop returns a dict with "result" key
                if res_data and "result" in res_data:
                    return res_data["result"]
        except Exception as e:
            logger.error(f"Upstash REST RPOP exception: {e}")
            
    # 3. Fallback to Memory Queue
    if _mock_queue:
        return _mock_queue.pop()
    return None
