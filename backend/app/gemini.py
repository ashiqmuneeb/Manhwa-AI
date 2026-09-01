import google.generativeai as genai
from app.config import settings
import json
import logging
import re

logger = logging.getLogger(__name__)

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)
    logger.info("Gemini API configured.")
else:
    logger.warning("GEMINI_API_KEY is missing. Gemini parser will operate in fallback mode.")

def analyze_paragraph(text: str, context_setting: str = "", cast_profiles: str = "") -> dict:
    """
    Sends paragraph text to Gemini to parse scene setting, character actions, cinematic shot type, panel type, and dialogue.
    Returns a dictionary of:
    - prompt_setting: Describe the background and scene environment.
    - prompt_actions: Describe the main character actions, expressions, and poses.
    - dialogue: Any dialogue/speech in the paragraph.
    - shot_type: The cinematic camera angle (e.g. extreme close-up, wide establishing, two-shot, over-the-shoulder, dutch angle).
    - panel_type: 'speed_rush' | 'impact_burst' | 'smirk_dialogue' | 'intense_dialogue' | 'establishing'
    - bubble_type: 'burst' (jagged spiky) | 'smooth' (rounded) | 'thought' | 'narration'
    - sfx_text: Action sound effect (e.g. 'SWOOSH!', 'BAM!', 'CRACK!', 'SLASH!', 'THUD!') or empty.
    - image_prompt: A consolidated prompt suitable for FLUX/SD panel generation.
    """
    if not settings.GEMINI_API_KEY:
        return _fallback_parsing(text)

    prompt = f"""
    You are an award-winning Korean Action Webtoon (Manhwa) Director & Storyboard Artist (creator of Lookism, Solo Leveling, Questism, Wind Breaker).
    Analyze the following paragraph from a story/novel and design a single high-impact Manhwa comic panel.

    Story Text: "{text}"
    {f"Existing Scene Setting: {context_setting}" if context_setting else ""}
    {f"Known Character Appearances: {cast_profiles}" if cast_profiles else ""}

    Format your response strictly as a JSON object with the following fields:
    - prompt_setting: Detailed visual description of the background environment, lighting palette, and atmosphere.
    - prompt_actions: Specific description of the characters present, their exact hair color/style, eye color, facial expression, body pose, and clothing.
    - shot_type: The most dynamic cinematic camera shot for this moment (e.g. 'extreme close-up on intense eyes with speed streaks', 'dramatic tilted low-angle portrait with smirk', 'two-shot over-the-shoulder conversation', 'wide establishing shot', 'dynamic impact burst shot').
    - panel_type: Choose one: 'speed_rush' (motion/speed blur), 'impact_burst' (explosive blow/collision), 'smirk_dialogue' (tilted/smirking), 'intense_dialogue' (close drama), 'establishing' (scenic).
    - bubble_type: Choose one: 'burst' (for shouting, fear, shock, anger with jagged spiky edges), 'smooth' (for normal dialogue), 'thought' (internal thought), 'narration' (for diary/narrator).
    - sfx_text: An expressive comic sound effect if action/tension is present (e.g. 'SWOOSH!', 'BAM!', 'CRACK!', 'SLASH!', 'THUD!', 'GASP!'), or empty string if none.
    - dialogue: The exact text of any speech/dialogue in the scene. If no dialogue, return empty string.
    - image_prompt: A consolidated, highly visual prompt for an image generator (FLUX / Stable Diffusion).
      Format: "korean webtoon manhwa action style, [shot_type], [characters with exact hair/eyes/clothing and pose], [prompt_setting], heavy black inking lines, vibrant digital cel shading, crisp clean line art, dramatic lighting, high contrast shadows, comic book color grading, masterpiece 8k comic panel, no text, no speech bubbles, clean art panel"

    IMPORTANT: The image_prompt must NOT contain any words, speech bubbles, letters, or subtitles.

    JSON Output:
    """

    for model_name in ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro", "gemini-flash"]:
        try:
            model = genai.GenerativeModel(model_name)

            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            
            result = json.loads(response.text.strip())
            
            # Verify result contains keys, otherwise construct image prompt if missing
            if "image_prompt" not in result or not result["image_prompt"]:
                setting = result.get("prompt_setting", "dimly lit atmospheric indoor setting")
                actions = result.get("prompt_actions", "manhwa characters in dramatic conversation")
                shot = result.get("shot_type", "cinematic action medium shot")
                result["image_prompt"] = f"korean webtoon manhwa action style, {shot}, {actions}, {setting}, heavy black inking lines, vibrant digital cel shading, dynamic lighting, masterpiece 8k comic panel, no text, no speech bubbles, clean art panel"
                
            return result
        except Exception as e:
            logger.warning(f"Gemini model {model_name} failed: {e}. Trying next model...")
            continue
            
    logger.error("All Gemini models failed. Using local heuristic fallback.")
    return _fallback_parsing(text)


def _fallback_parsing(text: str) -> dict:
    """
    Intelligent character & action heuristic parser if Gemini API is unreachable.
    Identifies characters, actions, dialogue, panel types, and SFX for authentic Action Manhwa panels.
    """
    # Extract dialogues
    dialogues = re.findall(r'"([^"]*)"|“([^”]*)”', text)
    flat_dialogues = [d[0] or d[1] for d in dialogues if (d[0] or d[1])]
    dialogue_str = " | ".join(flat_dialogues) if flat_dialogues else ""
    
    lower_text = text.lower()
    
    # 1. Detect Action Category & SFX
    panel_type = "intense_dialogue"
    bubble_type = "smooth"
    sfx_text = ""
    shot_type = "dramatic close-up portrait"

    if any(k in lower_text for k in ["speed", "fast", "flash", "dodge", "rush", "blur", "wind", "read", "stare"]):
        panel_type = "speed_rush"
        bubble_type = "burst"
        sfx_text = "SWOOSH!"
        shot_type = "extreme close-up on eyes with motion blur speed streaks across face"
    elif any(k in lower_text for k in ["hit", "punch", "strike", "blow", "crash", "smash", "kick", "slam", "pain", "jerk"]):
        panel_type = "impact_burst"
        bubble_type = "burst"
        sfx_text = "BAM!"
        shot_type = "dynamic Dutch-angle explosive impact shot with energy sparks"
    elif any(k in lower_text for k in ["smirk", "smile", "grin", "laugh", "great", "felt", "cool", "bro"]):
        panel_type = "smirk_dialogue"
        bubble_type = "smooth"
        sfx_text = "HEH..."
        shot_type = "tilted low-angle close-up portrait with confident smirk, dramatic rim lighting"
    elif any(k in lower_text for k in ["diary", "morning", "scared", "fear", "danger", "frightened"]):
        panel_type = "intense_dialogue"
        bubble_type = "thought" if not dialogue_str else "burst"
        sfx_text = "THUMP..."
        shot_type = "intimate close-up showing trembling eyes and nervous expression"
    elif any(k in lower_text for k in ["gym", "ballroom", "forest", "woods", "hall", "town", "street"]):
        panel_type = "establishing"
        bubble_type = "smooth"
        shot_type = "wide atmospheric establishing shot"

    # 2. Detect Setting
    setting = "indoor room setting, dramatic moody lighting"
    if any(k in lower_text for k in ["dance", "band", "music", "gym", "hall", "ballroom", "party"]):
        setting = "dimly lit elegant school dance ballroom, ambient party lights, dramatic atmosphere"
    elif any(k in lower_text for k in ["bedroom", "room", "diary", "bed", "window", "desk"]):
        setting = "cozy bedroom with warm lamp light, desk with open journal diary near window"
    elif any(k in lower_text for k in ["forest", "tree", "wood", "cemetery", "graveyard", "fog", "mist", "oak"]):
        setting = "ancient misty forest at dusk, moonlight filtering through tall dark trees"
    elif any(k in lower_text for k in ["street", "city", "road", "car", "drive"]):
        setting = "quiet suburban town street at twilight, streetlights casting long dramatic shadows"

    # 3. Detect Characters and Details
    has_elena = "elena" in lower_text
    has_stefan = "stefan" in lower_text or "damon" in lower_text
    has_male = has_stefan or any(k in lower_text for k in [" he ", "him ", "his ", "man ", "boy ", "guy "])
    has_female = has_elena or any(k in lower_text for k in [" she ", "her ", "hers ", "woman ", "girl "])

    characters_desc = []
    if has_female and has_male:
        characters_desc.append("beautiful young woman with long golden blonde hair and sapphire blue eyes in an elegant dress, standing close to a handsome brooding young man with wavy dark hair and intense piercing green eyes")
    elif has_female:
        if "diary" in lower_text or "write" in lower_text:
            characters_desc.append("beautiful young woman with long wavy blonde hair writing intently in her diary, contemplative gentle expression")
        elif "window" in lower_text:
            characters_desc.append("beautiful young woman with long blonde hair looking thoughtfully out a window, soft rim lighting")
        else:
            characters_desc.append("beautiful young woman with long blonde hair, expressive blue eyes, emotional close-up facial expression")
    elif has_male:
        characters_desc.append("handsome mysterious young man with dark wavy hair, sharp angular jawline, intense focused green eyes, wearing a dark jacket")
    else:
        characters_desc.append("young manhwa protagonist with sharp intense gaze and dynamic expression")

    char_str = ", ".join(characters_desc)
    
    # 4. Narrative Action Summary
    action = re.sub(r'"[^"]*"|“[^”]*”', '', text).strip()
    if len(action) > 120:
        action = action[:120] + "..."
    if not action:
        action = "character in dramatic confrontation"

    # 5. Construct Action Manhwa Image Prompt
    image_prompt = (
        f"korean webtoon manhwa action style, {shot_type}, {char_str}, {setting}, "
        f"heavy black inking lines, vibrant digital cel shading, crisp clean line art, "
        f"high contrast shadows, comic book color grading, dynamic action lines, "
        f"masterpiece 8k comic panel, no text, no speech bubbles, clean art panel"
    )

    return {
        "prompt_setting": setting,
        "prompt_actions": f"{char_str}. {action}",
        "dialogue": dialogue_str,
        "shot_type": shot_type,
        "panel_type": panel_type,
        "bubble_type": bubble_type,
        "sfx_text": sfx_text,
        "image_prompt": image_prompt
    }


def analyze_full_story(story_text: str) -> dict:
    """
    Performs full-story comprehension across the whole novel manuscript.
    Extracts synopsis, genre/tone, character cast, and director customization questions.
    """
    if not settings.GEMINI_API_KEY:
        return _fallback_full_story_analysis(story_text)

    prompt = f"""
    You are an award-winning Webtoon / Manhwa Studio Creative Director & Storyboard Lead.
    Read the following novel / story text in its entirety to understand the plot, characters, and aesthetic vision.

    Story Text Excerpt:
    \"\"\"{story_text[:6000]}\"\"\"

    Analyze the story and generate a structured creative direction plan as JSON:
    {{
        "synopsis": "A 2-3 sentence engaging synopsis of the story premise and central conflict.",
        "genre_and_tone": "The primary genre and emotional tone (e.g. 'Urban Martial Arts Action', 'Dark Supernatural Romance', 'Psychological Thriller').",
        "recommended_art_style": "Action Inking with Motion Streaks",
        "characters": [
            {{
                "name": "Character Name",
                "role": "Protagonist / Antagonist / Lead / Supporting",
                "hair": "Hair style & color (e.g. 'Tousled golden blonde hair with subtle fringe')",
                "eyes": "Eye color and expression (e.g. 'Sharp sapphire blue eyes, piercing gaze')",
                "clothing": "Signature outfit style (e.g. 'Black leather biker jacket with silver accents')",
                "signature_trait": "Distinct visual accessory or feature (e.g. 'Silver hoop earring on left ear, small scar on jaw')"
            }}
        ],
        "director_questions": [
            {{
                "id": "action_intensity",
                "question": "How intense should the action visual effects (speed lines, impact sparks) be?",
                "options": ["High-Octane Action (Maximum Speed Lines & Explosive SFX)", "Cinematic Drama (Subtle Inking & Moody Lighting)", "Stylized Webtoon (Clean Cel Shading)"],
                "default": "High-Octane Action (Maximum Speed Lines & Explosive SFX)"
            }},
            {{
                "id": "lighting_palette",
                "question": "What primary lighting mood fits this manhwa best?",
                "options": ["High-Contrast Night Lighting with Rim Lights", "Warm Cinematic Golden Hour", "Moody Atmospheric Dark Noir"],
                "default": "High-Contrast Night Lighting with Rim Lights"
            }}
        ]
    }}

    Respond with pure JSON only.
    """

    for model_name in ["gemini-3.6-flash", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(
                prompt,
                generation_config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text.strip())
            return result
        except Exception as e:
            logger.warning(f"Full story analysis on {model_name} failed: {e}. Trying next...")
            continue

    logger.error("All Gemini models failed for full-story analysis. Using local heuristic fallback.")
    return _fallback_full_story_analysis(story_text)


def _fallback_full_story_analysis(story_text: str) -> dict:
    """
    Local heuristic fallback to extract synopsis, characters, and director questions without API key.
    """
    lower_text = story_text.lower()
    
    # 1. Determine characters
    characters = []
    
    if "elena" in lower_text:
        characters.append({
            "name": "Elena",
            "role": "Protagonist",
            "hair": "Long waist-length golden blonde hair",
            "eyes": "Deep sapphire blue eyes, expressive gentle gaze",
            "clothing": "Midnight blue elegant evening gown",
            "signature_trait": "Silver ribbon hair clip and antique journal"
        })
    if "stefan" in lower_text:
        characters.append({
            "name": "Stefan",
            "role": "Male Lead",
            "hair": "Tousled dark wavy hair",
            "eyes": "Intense piercing emerald green eyes",
            "clothing": "Dark tailored jacket over crisp collar",
            "signature_trait": "Lapis lazuli ring and sharp brooding jawline"
        })
    if "damon" in lower_text:
        characters.append({
            "name": "Damon",
            "role": "Rival / Antagonist",
            "hair": "Short jet-black messy hair",
            "eyes": "Icy pale blue eyes with a confident smirk",
            "clothing": "Fitted black leather jacket",
            "signature_trait": "Crow feather emblem and signature smirk"
        })
    if "thomas" in lower_text:
        characters.append({
            "name": "Thomas",
            "role": "Fighter / Combatant",
            "hair": "Short cropped blonde hair with styled front",
            "eyes": "Dark intense eyes, focused gaze",
            "clothing": "Athletic streetwear and dark compression shirt",
            "signature_trait": "Silver hoop earrings on both ears"
        })
    if "thaddaeus" in lower_text:
        characters.append({
            "name": "Thaddaeus",
            "role": "Speed Fighter",
            "hair": "Sleek parted ash silver-grey hair",
            "eyes": "Calm ruthless dark grey eyes",
            "clothing": "Dark high-collar martial arts jacket",
            "signature_trait": "Insane speed blur afterimage"
        })
        
    if not characters:
        characters.append({
            "name": "Hero",
            "role": "Main Protagonist",
            "hair": "Stylized dark webtoon hair",
            "eyes": "Intense glowing eyes with sharp focus",
            "clothing": "Modern stylish jacket and dark trousers",
            "signature_trait": "Confident smirk and dynamic combat stance"
        })

    # 2. Determine Genre & Synopsis
    if any(k in lower_text for k in ["speed", "punch", "hit", "strike", "fight", "martial"]):
        genre = "Urban Martial Arts & High-Speed Action"
        synopsis = "A high-stakes martial conflict where fighters clash with inhuman speed and devastating power. Tension mounts as secret techniques and rivalries push combatants to their ultimate limits."
        art_style = "Action Inking with Motion Streaks"
    elif any(k in lower_text for k in ["vampire", "blood", "shadow", "diary", "stefan", "elena"]):
        genre = "Dark Supernatural & Romantic Suspense"
        synopsis = "In a quiet historic town, secrets unravel through a personal diary as ancient supernatural forces and dangerous romantic tensions collide under the cover of night."
        art_style = "High-Contrast Gothic Cel Shading"
    else:
        genre = "Modern Dramatic Webtoon"
        synopsis = "A compelling character-driven narrative exploring emotional encounters, hidden motives, and transformative confrontations."
        art_style = "Vibrant Webtoon Cel Shading"

    return {
        "synopsis": synopsis,
        "genre_and_tone": genre,
        "recommended_art_style": art_style,
        "characters": characters,
        "director_questions": [
            {
                "id": "action_intensity",
                "question": "How intense should the action visual effects (speed lines, impact sparks) be?",
                "options": ["High-Octane Action (Maximum Speed Lines & Explosive SFX)", "Cinematic Drama (Subtle Inking & Moody Lighting)", "Stylized Webtoon (Clean Cel Shading)"],
                "default": "High-Octane Action (Maximum Speed Lines & Explosive SFX)"
            },
            {
                "id": "lighting_palette",
                "question": "What primary lighting mood fits this manhwa best?",
                "options": ["High-Contrast Night Lighting with Rim Lights", "Warm Cinematic Golden Hour", "Moody Atmospheric Dark Noir"],
                "default": "High-Contrast Night Lighting with Rim Lights"
            }
        ]
    }



