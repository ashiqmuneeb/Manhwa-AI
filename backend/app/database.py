from supabase import create_client, Client
from app.config import settings
import logging
import sqlite3
import uuid
import os
from datetime import datetime

logger = logging.getLogger(__name__)

# Setup local database file path relative to this file to prevent directory issues
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "local.db")

supabase_client: Client = None
use_sqlite = False

if settings.SUPABASE_URL and settings.SUPABASE_KEY:
    try:
        supabase_client = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        logger.info("Supabase client initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing Supabase client: {e}. Falling back to SQLite.")
        use_sqlite = True
else:
    logger.warning("Supabase credentials missing. Running in local SQLite mode.")
    use_sqlite = True


def get_sqlite_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_sqlite_db():
    try:
        conn = get_sqlite_conn()
        cursor = conn.cursor()
        
        # 1. Novels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS novels (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Chapters table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id TEXT PRIMARY KEY,
                novel_id TEXT NOT NULL,
                title TEXT NOT NULL,
                raw_text TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (novel_id) REFERENCES novels (id) ON DELETE CASCADE
            )
        """)
        
        # 3. Scenes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scenes (
                id TEXT PRIMARY KEY,
                chapter_id TEXT NOT NULL,
                sequence_number INTEGER NOT NULL,
                paragraph_text TEXT,
                prompt_setting TEXT,
                prompt_actions TEXT,
                dialogue TEXT,
                image_prompt TEXT,
                image_url TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (chapter_id) REFERENCES chapters (id) ON DELETE CASCADE
            )
        """)
        conn.commit()
        conn.close()
        logger.info("SQLite database tables verified/created successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite tables: {e}", exc_info=True)


if use_sqlite:
    init_sqlite_db()


def get_supabase() -> Client:
    return supabase_client


def create_novel(title: str):
    if use_sqlite:
        try:
            novel_id = str(uuid.uuid4())
            conn = get_sqlite_conn()
            conn.execute("INSERT INTO novels (id, title) VALUES (?, ?)", (novel_id, title))
            conn.commit()
            conn.close()
            return {"id": novel_id, "title": title}
        except Exception as e:
            logger.error(f"SQLite create_novel error: {e}")
            return None

    response = supabase_client.table("novels").insert({"title": title}).execute()
    return response.data[0] if response.data else None


def create_chapter(novel_id: str, title: str, raw_text: str):
    if use_sqlite:
        try:
            chapter_id = str(uuid.uuid4())
            conn = get_sqlite_conn()
            conn.execute(
                "INSERT INTO chapters (id, novel_id, title, raw_text, status) VALUES (?, ?, ?, ?, 'pending')",
                (chapter_id, novel_id, title, raw_text)
            )
            conn.commit()
            conn.close()
            return {
                "id": chapter_id,
                "novel_id": novel_id,
                "title": title,
                "raw_text": raw_text,
                "status": "pending"
            }
        except Exception as e:
            logger.error(f"SQLite create_chapter error: {e}")
            return None

    response = supabase_client.table("chapters").insert({
        "novel_id": novel_id,
        "title": title,
        "raw_text": raw_text,
        "status": "pending"
    }).execute()
    return response.data[0] if response.data else None


def update_chapter_status(chapter_id: str, status: str):
    if use_sqlite:
        try:
            conn = get_sqlite_conn()
            conn.execute("UPDATE chapters SET status = ? WHERE id = ?", (status, chapter_id))
            conn.commit()
            conn.close()
            return
        except Exception as e:
            logger.error(f"SQLite update_chapter_status error: {e}")
            return

    supabase_client.table("chapters").update({"status": status}).eq("id", chapter_id).execute()


def create_scenes(scenes_data: list):
    if use_sqlite:
        try:
            inserted_scenes = []
            conn = get_sqlite_conn()
            for s in scenes_data:
                scene_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO scenes (id, chapter_id, sequence_number, paragraph_text, status, image_url, dialogue, image_prompt)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        scene_id,
                        s["chapter_id"],
                        s["sequence_number"],
                        s["paragraph_text"],
                        s["status"],
                        s.get("image_url"),
                        s.get("dialogue"),
                        s.get("image_prompt")
                    )
                )
                inserted_scenes.append({
                    "id": scene_id,
                    **s
                })
            conn.commit()
            conn.close()
            return inserted_scenes
        except Exception as e:
            logger.error(f"SQLite create_scenes error: {e}")
            return None

    response = supabase_client.table("scenes").insert(scenes_data).execute()
    return response.data


def get_chapter_scenes(chapter_id: str):
    if use_sqlite:
        try:
            conn = get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM scenes WHERE chapter_id = ? ORDER BY sequence_number ASC",
                (chapter_id,)
            )
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"SQLite get_chapter_scenes error: {e}")
            return []

    response = supabase_client.table("scenes")\
        .select("*")\
        .eq("chapter_id", chapter_id)\
        .order("sequence_number", desc=False)\
        .execute()
    return response.data


def update_scene(scene_id: str, updates: dict):
    if use_sqlite:
        try:
            if not updates:
                return
            # SQLite compatibility: Replace PostgreSQL now() function with UTC ISO format
            if "updated_at" in updates and updates["updated_at"] == "now()":
                updates = updates.copy()
                updates["updated_at"] = datetime.utcnow().isoformat()

            set_clause = ", ".join([f"{k} = ?" for k in updates.keys()])
            values = list(updates.values())
            values.append(scene_id)
            
            conn = get_sqlite_conn()
            conn.execute(f"UPDATE scenes SET {set_clause} WHERE id = ?", values)
            conn.commit()
            conn.close()
            return
        except Exception as e:
            logger.error(f"SQLite update_scene error: {e}")
            return

    supabase_client.table("scenes").update(updates).eq("id", scene_id).execute()


def get_scene(scene_id: str):
    """
    Retrieve a single scene's data by its ID.
    Compatible with both SQLite and Supabase backends.
    """
    if use_sqlite:
        try:
            conn = get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,))
            row = cursor.fetchone()
            conn.close()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"SQLite get_scene error: {e}")
            return None

    try:
        response = supabase_client.table("scenes").select("*").eq("id", scene_id).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"Supabase get_scene error: {e}")
        return None


def delete_scene(scene_id: str) -> bool:
    """
    Deletes a single scene by its ID.
    Compatible with both SQLite and Supabase backends.
    """
    if use_sqlite:
        try:
            conn = get_sqlite_conn()
            conn.execute("DELETE FROM scenes WHERE id = ?", (scene_id,))
            conn.commit()
            conn.close()
            logger.info(f"SQLite deleted scene {scene_id}")
            return True
        except Exception as e:
            logger.error(f"SQLite delete_scene error: {e}")
            return False

    try:
        supabase_client.table("scenes").delete().eq("id", scene_id).execute()
        logger.info(f"Supabase deleted scene {scene_id}")
        return True
    except Exception as e:
        logger.error(f"Supabase delete_scene error: {e}")
        return False


def get_all_novels():
    """
    Query all novels and fetch their first chapter ID.
    Supports SQLite mode.
    """
    if use_sqlite:
        try:
            conn = get_sqlite_conn()
            cursor = conn.cursor()
            cursor.execute("""
                SELECT n.id, n.title, n.created_at, c.id as chapter_id
                FROM novels n
                LEFT JOIN chapters c ON n.id = c.novel_id
                GROUP BY n.id
                ORDER BY n.created_at DESC
            """)
            rows = cursor.fetchall()
            conn.close()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"SQLite get_all_novels error: {e}")
            return []
    return None


def delete_novel(novel_id: str) -> bool:
    """
    Deletes the novel from local SQLite database.
    Foreign key CASCADE deletes chapters and scenes automatically.
    """
    if use_sqlite:
        try:
            conn = get_sqlite_conn()
            conn.execute("DELETE FROM novels WHERE id = ?", (novel_id,))
            conn.commit()
            conn.close()
            logger.info(f"SQLite deleted novel {novel_id}")
            return True
        except Exception as e:
            logger.error(f"SQLite delete_novel error: {e}")
            return False
    return False


