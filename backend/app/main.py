from fastapi import FastAPI, HTTPException, BackgroundTasks, Form, File, UploadFile, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import logging
import io
import os
from contextlib import asynccontextmanager
import pypdf
from pypdf import PdfReader
import json
import uuid

# Create static files directory in backend root directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
os.makedirs(STATIC_DIR, exist_ok=True)

from app.config import settings
from app.database import (
    create_novel,
    create_chapter,
    create_scenes,
    get_chapter_scenes,
    update_scene,
    get_supabase
)
from app.queue import push_scene_task
from app.worker import start_background_worker

# Setup logs
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Schema validation models
class RetrySceneRequest(BaseModel):
    scene_id: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: trigger background worker thread
    logger.info("Initializing application services...")
    start_background_worker()
    yield
    # Shutdown: clean up if needed
    logger.info("Shutting down application...")

app = FastAPI(
    title="Novel-to-Manhwa API",
    description="Python API for converting novel text into vertical-scrolling comic panels.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for local Vite development and staging deployments
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/static/{filename}")
def serve_static_file(filename: str):
    """
    Dependency-free static file server to host locally generated manhwa panels.
    Does not require aiofiles.
    """
    file_path = os.path.join(STATIC_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Static file not found")
    
    try:
        with open(file_path, "rb") as f:
            content = f.read()
        return Response(content=content, media_type="image/png")
    except Exception as e:
        logger.error(f"Error serving static file {filename}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error reading static file")

@app.get("/")
def read_root():
    return {
        "status": "online",
        "mock_mode": settings.MOCK_IMAGE_GEN,
        "image_gen_endpoint": settings.IMAGE_GEN_URL or "not_configured"
    }

import re

def split_text_into_chapters(text: str) -> list:
    """
    Splits raw novel text into chapters based on standard headings.
    Returns a list of dicts: [{'title': 'Chapter X', 'content': '...'}]
    """
    lines = text.split("\n")
    # Matches common headings like Chapter 1, CH 2, Prologue, Epilogue, etc.
    chapter_pattern = re.compile(
        r'^\s*(?:chapter|ch\.|episode|ep\.)\s*[a-zA-Z0-9_.-]+|^\s*(?:prologue|epilogue)\b', 
        re.IGNORECASE
    )
    
    chapters = []
    current_title = "Prologue"
    current_lines = []
    
    for line in lines:
        stripped_line = line.strip()
        if chapter_pattern.match(stripped_line) and len(stripped_line) < 100:
            if current_lines:
                chapters.append({
                    "title": current_title,
                    "content": "\n".join(current_lines).strip()
                })
                current_lines = []
            current_title = stripped_line
        else:
            current_lines.append(line)
            
    if current_lines:
        chapters.append({
            "title": current_title,
            "content": "\n".join(current_lines).strip()
        })
        
    # If no headings matched, group everything as Chapter 1
    if not chapters or (len(chapters) == 1 and not chapters[0]["content"]):
        chapters = [{"title": "Chapter 1", "content": text.strip()}]
        
    return chapters

def chunk_into_story_scenes(text: str) -> list:
    """
    Intelligently merges broken lines and groups narrative fragments into cohesive story scenes.
    Combines character dialogue with its immediate narrative reaction.
    """
    raw_lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not raw_lines:
        return []

    # Step 1: Reconstruct broken lines (lines that were split mid-sentence)
    merged_lines = []
    current_buf = ""
    for line in raw_lines:
        if not current_buf:
            current_buf = line
        else:
            # If current buffer doesn't end with sentence terminator and isn't closed dialogue, merge
            if not current_buf.endswith(('.', '!', '?', '"', '”', '…', '—')):
                current_buf += " " + line
            else:
                merged_lines.append(current_buf)
                current_buf = line
    if current_buf:
        merged_lines.append(current_buf)

    # Step 2: Group into cohesive Manhwa panels (100 to 400 chars per panel)
    scenes = []
    scene_buf = []
    char_count = 0

    for line in merged_lines:
        scene_buf.append(line)
        char_count += len(line)
        
        # If we have at least 150 chars or 2-3 dialogue turns, form a scene
        if char_count >= 160 or len(scene_buf) >= 3:
            scenes.append(" ".join(scene_buf).strip())
            scene_buf = []
            char_count = 0

    if scene_buf:
        if scenes and char_count < 80:
            scenes[-1] += " " + " ".join(scene_buf).strip()
        else:
            scenes.append(" ".join(scene_buf).strip())

    return scenes


def is_comic_pdf(reader: PdfReader) -> bool:
    """
    Checks if a PDF has very little text and contains images, indicating it is a comic chapter.
    """
    try:
        sample_pages = min(5, len(reader.pages))
        total_text_len = 0
        has_images = False
        
        for i in range(sample_pages):
            page = reader.pages[i]
            text = page.extract_text() or ""
            total_text_len += len(text.strip())
            if page.images and len(page.images) > 0:
                has_images = True
                
        avg_text_len = total_text_len / sample_pages if sample_pages > 0 else 0
        return avg_text_len < 100 and has_images
    except Exception as e:
        logger.error(f"Error checking if PDF is comic: {e}")
        return False


@app.post("/api/extract-text")
async def extract_text(
    file: UploadFile = File(...),
    max_chapters: Optional[int] = Form(5)
):
    """
    Utility endpoint to extract plain text from TXT or PDF files for frontend pre-generation editing.
    Supports direct page image extraction for comic/manhwa PDFs.
    """
    try:
        filename = file.filename.lower()
        file_bytes = await file.read()
        
        extracted_text = ""
        pages_list = []
        
        if filename.endswith(".pdf"):
            try:
                pdf_file = io.BytesIO(file_bytes)
                reader = PdfReader(pdf_file)
                
                # Check if this is a comic book PDF
                if is_comic_pdf(reader):
                    pages_to_read = len(reader.pages)
                    if max_chapters is not None and max_chapters > 0:
                        pages_to_read = min(pages_to_read, max_chapters)
                        
                    for page_idx in range(pages_to_read):
                        page = reader.pages[page_idx]
                        if page.images and len(page.images) > 0:
                            img = page.images[0]
                            img_bytes = img.data
                            
                            img_filename = f"comic_page_{page_idx+1}_{uuid.uuid4().hex[:8]}.png"
                            img_filepath = os.path.join(STATIC_DIR, img_filename)
                            
                            from PIL import Image
                            pil_img = Image.open(io.BytesIO(img_bytes))
                            if pil_img.mode in ("RGBA", "P"):
                                pil_img = pil_img.convert("RGB")
                            pil_img.save(img_filepath, format="PNG")
                            
                            pages_list.append({
                                "pageNum": page_idx + 1,
                                "text": f"[Comic Page {page_idx+1}]",
                                "image_url": f"http://localhost:8000/static/{img_filename}",
                                "is_comic": True
                            })
                        else:
                            pages_list.append({
                                "pageNum": page_idx + 1,
                                "text": f"[Blank Page {page_idx+1}]",
                                "image_url": None,
                                "is_comic": True
                            })
                    return {
                        "text": "[Comic PDF Uploaded]",
                        "pages": pages_list,
                        "is_comic": True
                    }
                else:
                    pages_to_read = len(reader.pages)
                    if max_chapters is not None and max_chapters > 0:
                        pages_to_read = min(pages_to_read, max_chapters)
                        
                    for page_idx in range(pages_to_read):
                        page_text = reader.pages[page_idx].extract_text()
                        if page_text:
                            page_text_clean = page_text.strip()
                            if page_text_clean:
                                pages_list.append({
                                    "pageNum": page_idx + 1,
                                    "text": page_text_clean,
                                    "image_url": None,
                                    "is_comic": False
                                })
                    extracted_text = "\n\n".join(p["text"] for p in pages_list)
            except Exception as pe:
                raise HTTPException(status_code=400, detail=f"Failed to read PDF: {str(pe)}")
        elif filename.endswith(".txt") or filename.endswith(".md"):
            try:
                extracted_text = file_bytes.decode("utf-8", errors="ignore")
                paragraphs = [p.strip() for p in extracted_text.split("\n") if p.strip()]
                
                # Limit paragraphs based on max_chapters safety limit
                if max_chapters is not None and max_chapters > 0:
                    limit = max_chapters * 12
                    paragraphs = paragraphs[:limit]
                
                # Group every 5 paragraphs into a single page
                for i in range(0, len(paragraphs), 5):
                    page_chunk = "\n\n".join(paragraphs[i:i+5])
                    pages_list.append({
                        "pageNum": (i // 5) + 1,
                        "text": page_chunk,
                        "image_url": None,
                        "is_comic": False
                    })
                extracted_text = "\n\n".join(paragraphs)
            except Exception as te:
                raise HTTPException(status_code=400, detail="Failed to decode text file.")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format.")
            
        return {
            "text": extracted_text.strip(),
            "pages": pages_list,
            "is_comic": False
        }
    except Exception as e:
        logger.error(f"Error in extract-text utility: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/story/analyze-full")
async def analyze_full_story_endpoint(


    raw_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None)
):
    """
    Performs complete full-story semantic analysis, character discovery, and creates director questionnaire.
    """
    try:
        extracted_text = ""
        if file and file.filename:
            file_bytes = await file.read()
            filename = file.filename.lower()
            if filename.endswith(".pdf"):
                pdf_file = io.BytesIO(file_bytes)
                reader = pypdf.PdfReader(pdf_file)
                extracted_text = "\n\n".join(
                    page.extract_text() or "" for page in reader.pages[:15]
                )
            elif filename.endswith(".txt") or filename.endswith(".md"):
                extracted_text = file_bytes.decode("utf-8", errors="ignore")
        elif raw_text:
            extracted_text = raw_text

        extracted_text = extracted_text.strip()
        if not extracted_text:
            raise HTTPException(status_code=400, detail="No story text provided for analysis.")

        from app.gemini import analyze_full_story
        story_plan = analyze_full_story(extracted_text)
        story_plan["raw_text"] = extracted_text

        return {
            "success": True,
            "data": story_plan
        }
    except Exception as e:
        logger.error(f"Failed to analyze full story: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_novel(

    title: str = Form(...),
    raw_text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    max_chapters: Optional[int] = Form(1),
    pages_json: Optional[str] = Form(None),
    cast_profiles: Optional[str] = Form(None)
):

    """
    Receives raw novel text OR uploaded file (.txt/.pdf), parses it into chapters,
    and pushes tasks into the queue up to the specified max_chapters limit.
    If pages_json is provided and represents a comic PDF, compiles pages immediately.
    """
    try:
        if not title.strip():
            raise HTTPException(status_code=400, detail="Novel title cannot be empty.")

        # Check if pages_json is provided and is comic
        is_comic = False
        parsed_pages = []
        if pages_json:
            try:
                parsed_pages = json.loads(pages_json)
                if parsed_pages and any(p.get("is_comic") for p in parsed_pages):
                    is_comic = True
            except Exception as je:
                logger.error(f"Failed to parse pages_json: {je}")

        if is_comic:
            # Create Novel row
            novel = create_novel(title)
            if not novel:
                raise HTTPException(status_code=500, detail="Failed to create novel entry.")
            novel_id = novel["id"]

            # Create a single Chapter for the comic pages
            chapter = create_chapter(novel_id, "Chapter 1", "[Comic Chapter]")
            if not chapter:
                raise HTTPException(status_code=500, detail="Failed to create chapter entry.")
            chapter_id = chapter["id"]

            # Create scenes data directly as completed comic pages
            scenes_data = []
            for index, page in enumerate(parsed_pages):
                scenes_data.append({
                    "chapter_id": chapter_id,
                    "sequence_number": index + 1,
                    "paragraph_text": page.get("text", f"Comic Page {index+1}"),
                    "image_url": page.get("image_url", ""),
                    "status": "completed"
                })

            saved_scenes = create_scenes(scenes_data)
            if not saved_scenes:
                raise HTTPException(status_code=500, detail="Failed to create comic page scenes.")

            return {
                "success": True,
                "novel_id": novel_id,
                "chapter_id": chapter_id,
                "total_paragraphs": len(parsed_pages),
                "queued_paragraphs": 0
            }

        extracted_text = ""

        # Process file upload if present
        if file is not None:
            filename = file.filename.lower()
            file_bytes = await file.read()
            
            if filename.endswith(".pdf"):
                logger.info(f"Extracting text from uploaded PDF file: {file.filename}")
                try:
                    pdf_file = io.BytesIO(file_bytes)
                    reader = PdfReader(pdf_file)
                    text_list = []
                    
                    pages_to_read = len(reader.pages)
                    if max_chapters is not None and max_chapters > 0:
                        pages_to_read = min(pages_to_read, max_chapters)
                        logger.info(f"Limiting PDF extraction to the first {pages_to_read} pages.")
                        
                    for page_idx in range(pages_to_read):
                        page_text = reader.pages[page_idx].extract_text()
                        if page_text:
                            text_list.append(page_text)
                    extracted_text = "\n".join(text_list)
                except Exception as pe:
                    logger.error(f"PDF extraction error: {pe}")
                    raise HTTPException(status_code=400, detail=f"Failed to extract text from PDF: {str(pe)}")
            elif filename.endswith(".txt") or filename.endswith(".md"):
                logger.info(f"Extracting text from uploaded text file: {file.filename}")
                try:
                    extracted_text = file_bytes.decode("utf-8", errors="ignore")
                except Exception as te:
                    logger.error(f"Text decoding error: {te}")
                    raise HTTPException(status_code=400, detail="Failed to decode text file. Ensure it is UTF-8 encoded.")
            else:
                raise HTTPException(status_code=400, detail="Unsupported file format. Please upload a .txt or .pdf file.")
        else:
            # Fall back to raw text input
            extracted_text = raw_text or ""

        extracted_text = extracted_text.strip()
        if not extracted_text:
            raise HTTPException(status_code=400, detail="No novel text content was provided or extracted.")

        # 1. Parse text into chapters
        parsed_chapters = split_text_into_chapters(extracted_text)
        logger.info(f"Parsed novel into {len(parsed_chapters)} chapters.")

        # 2. Create Novel row
        novel = create_novel(title)
        if not novel:
            raise HTTPException(status_code=500, detail="Failed to create novel entry.")
        novel_id = novel["id"]

        first_chapter_id = None
        total_scenes_queued = 0
        total_paragraphs_processed = 0

        # Limit chapters to process based on max_chapters input
        chapters_to_process = parsed_chapters
        if max_chapters is not None and max_chapters > 0:
            chapters_to_process = parsed_chapters[:max_chapters]
            logger.info(f"Limiting generation queue to the first {max_chapters} chapters.")

        for ch_idx, ch in enumerate(chapters_to_process):
            ch_title = ch["title"]
            ch_content = ch["content"]
            
            # Skip empty chapters
            if not ch_content.strip():
                continue

            # Create Chapter row in database
            chapter = create_chapter(novel_id, ch_title, ch_content)
            if not chapter:
                logger.error(f"Failed to create chapter entry for {ch_title}")
                continue

            chapter_id = chapter["id"]
            if first_chapter_id is None:
                first_chapter_id = chapter_id

            # Chunk the chapter content into coherent Manhwa story scenes
            paragraphs = chunk_into_story_scenes(ch_content)
            if not paragraphs:
                paragraphs = [p.strip() for p in ch_content.split("\n") if p.strip()]
            
            # Safety limit: if there is only 1 chapter and it is extremely large,
            # limit the panels based on max_chapters (e.g. 5 chapters * 12 = 60 panels)
            if len(chapters_to_process) == 1 and max_chapters is not None and max_chapters > 0:
                limit = max_chapters * 12
                if len(paragraphs) > limit:
                    logger.info(f"No multiple chapters matched. Truncating paragraph queue to first {limit} scenes.")
                    paragraphs = paragraphs[:limit]
                    
            total_paragraphs_processed += len(paragraphs)

            # Create scenes data
            scenes_data = []
            for index, paragraph in enumerate(paragraphs):
                scenes_data.append({
                    "chapter_id": chapter_id,
                    "sequence_number": index + 1,
                    "paragraph_text": paragraph,
                    "status": "pending"
                })

            saved_scenes = create_scenes(scenes_data)
            if not saved_scenes:
                logger.error(f"Failed to create scene entries for chapter {ch_title}")
                continue

            # Queue tasks
            for scene in saved_scenes:
                success = push_scene_task(scene["id"])
                if success:
                    total_scenes_queued += 1
                else:
                    logger.error(f"Failed to queue scene task: {scene['id']}")

        if not first_chapter_id:
            raise HTTPException(status_code=400, detail="Failed to process or parse any chapters from the manuscript.")

        return {
            "success": True,
            "novel_id": novel_id,
            "chapter_id": first_chapter_id,
            "total_paragraphs": total_paragraphs_processed,
            "queued_paragraphs": total_scenes_queued
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error in upload novel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Unexpected server error: {str(e)}")

@app.get("/api/chapters/{chapter_id}/scenes")
def get_scenes(chapter_id: str):
    """
    Returns list of scenes for the chapter.
    """
    try:
        scenes = get_chapter_scenes(chapter_id)
        # Mock responses if Supabase is offline/unconfigured
        if not scenes and not settings.SUPABASE_URL:
            # Generate local sample scenes for frontend evaluation
            return [
                {
                    "id": f"mock-scene-{i}",
                    "chapter_id": chapter_id,
                    "sequence_number": i,
                    "paragraph_text": f"This is mock paragraph number {i} describing some epic manhwa action scene.",
                    "prompt_setting": "A scenic background landscape",
                    "prompt_actions": "Character standing tall",
                    "dialogue": "Let's do this!",
                    "image_prompt": "Epic warrior stance",
                    "image_url": f"https://picsum.photos/seed/{i}/600/800",
                    "status": "completed",
                    "error_message": None
                }
                for i in range(1, 5)
            ]
        return scenes
    except Exception as e:
        logger.error(f"Error fetching scenes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/status")
def get_chapter_progress(chapter_id: str):
    """
    Retrieves percentage/count stats of generating images.
    """
    try:
        scenes = get_chapter_scenes(chapter_id)
        if not scenes:
            return {"total": 0, "completed": 0, "pending": 0, "generating": 0, "failed": 0}

        total = len(scenes)
        completed = sum(1 for s in scenes if s["status"] == "completed")
        pending = sum(1 for s in scenes if s["status"] == "pending")
        generating = sum(1 for s in scenes if s["status"] == "generating")
        failed = sum(1 for s in scenes if s["status"] == "failed")

        return {
            "total": total,
            "completed": completed,
            "pending": pending,
            "generating": generating,
            "failed": failed,
            "percentage": int((completed / total) * 100) if total > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error fetching status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/scenes/{scene_id}/retry")
def retry_scene(scene_id: str):
    """
    Resets the failed scene to pending and triggers reprocessing.
    """
    try:
        update_scene(scene_id, {
            "status": "pending",
            "error_message": None
        })
        success = push_scene_task(scene_id)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to queue task for retry.")
        return {"success": True, "scene_id": scene_id, "status": "pending"}
    except Exception as e:
        logger.error(f"Error retrying scene: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chapters/{chapter_id}/retry-failed")
def retry_failed_chapter_scenes(chapter_id: str):
    """
    Re-queues all failed or pending scenes for a given chapter.
    """
    try:
        scenes = get_chapter_scenes(chapter_id)
        requeued_count = 0
        for s in scenes:
            if s.get("status") in ("failed", "pending"):
                update_scene(s["id"], {"status": "pending", "error_message": None})
                push_scene_task(s["id"])
                requeued_count += 1
        return {"success": True, "requeued": requeued_count}
    except Exception as e:
        logger.error(f"Error retrying failed chapter scenes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/novels")
def get_novels():
    """
    Retrieves all compiled novels along with their chapter ID for visual bookshelf rendering.
    """
    try:
        supabase = get_supabase()
        if not supabase:
            # Try to get novels from SQLite fallback database
            from app.database import get_all_novels
            novels = get_all_novels()
            if novels is not None:
                return novels
            return []
        
        # Query novels with their joined chapters
        res = supabase.table("novels").select("id, title, created_at, chapters(id)").order("created_at", desc=True).execute()
        
        flat_novels = []
        for item in res.data:
            chapter_id = None
            if item.get("chapters") and len(item["chapters"]) > 0:
                chapter_id = item["chapters"][0]["id"]
            flat_novels.append({
                "id": item["id"],
                "title": item["title"],
                "created_at": item["created_at"],
                "chapter_id": chapter_id
            })
        return flat_novels
    except Exception as e:
        logger.error(f"Error listing novels: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/novels/{novel_id}")
def delete_novel(novel_id: str):
    """
    Deletes the novel. Associated chapters and scenes are deleted via CASCADE triggers in DB.
    """
    try:
        supabase = get_supabase()
        if not supabase:
            from app.database import delete_novel as delete_novel_db
            success = delete_novel_db(novel_id)
            return {"success": success}
            
        supabase.table("novels").delete().eq("id", novel_id).execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"Error deleting novel {novel_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

