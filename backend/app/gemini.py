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

def analyze_paragraph(text: str) -> dict:
    """
    Sends paragraph text to Gemini to parse scene setting, character actions, and dialogue.
    Returns a dictionary of:
    - prompt_setting: Describe the background and scene environment.
    - prompt_actions: Describe the main character actions and positions.
    - dialogue: Any dialogue/speech in the paragraph.
    - image_prompt: A consolidated prompt suitable for FLUX/SD panel generation.
    """
    if not settings.GEMINI_API_KEY:
        return _fallback_parsing(text)

    prompt = f"""
    Analyze the following paragraph from a web novel and extract details for a Manhwa (webtoon) panel.
    Format your response as a JSON object with the following fields:
    - prompt_setting: Detailed visual description of the setting, environment, time of day, and atmosphere.
    - prompt_actions: Specific description of the characters present, their appearance, facial expressions, poses, and actions.
    - dialogue: The exact text of any speech/dialogue in the scene. If no dialogue, return empty string.
    - image_prompt: A concise, highly visual, consolidated prompt for an image generator (like FLUX/Stable Diffusion) to generate a comic panel representing this paragraph. Avoid abstract terms.

    IMPORTANT: The image_prompt must NOT contain any mention of speech bubbles, dialogue, text, captions, or words. It should focus purely on the visual scene. Specify 'no text, no speech bubbles, no words, clean art panel' in the prompt to ensure a clean panel for HTML text overlay.

    Text: "{text}"

    JSON Output:
    """

    try:
        model = genai.GenerativeModel("gemini-3.6-flash")
        response = model.generate_content(
            prompt,
            generation_config={"response_mime_type": "application/json"}
        )
        
        result = json.loads(response.text.strip())
        
        # Verify result contains keys, otherwise construct image prompt if missing
        if "image_prompt" not in result or not result["image_prompt"]:
            setting = result.get("prompt_setting", "")
            actions = result.get("prompt_actions", "")
            result["image_prompt"] = f"{setting}. {actions}. no text, no speech bubbles, clean art panel."
            
        return result
    except Exception as e:
        logger.error(f"Gemini API parse failed: {e}. Using fallback parser.")
        return _fallback_parsing(text)

def _fallback_parsing(text: str) -> dict:
    """
    Simple local heuristics-based fallback parser if Gemini fails or is not configured.
    """
    # Extract dialogues (anything inside double quotes)
    dialogues = re.findall(r'"([^"]*)"', text)
    dialogue_str = " | ".join(dialogues) if dialogues else ""
    
    # Try to find keywords for setting
    setting = "A web novel scene, indoor room setting"
    if any(k in text.lower() for k in ["forest", "tree", "wood", "grass", "mountain"]):
        setting = "An outdoor fantasy landscape, forest with sunlight filtering through leaves"
    elif any(k in text.lower() for k in ["street", "city", "shop", "town"]):
        setting = "A bustling city street setting"
    elif any(k in text.lower() for k in ["castle", "palace", "hall"]):
        setting = "A grand medieval castle hall"

    # Action is just a simplified version of the paragraph text without quotes
    action = re.sub(r'"[^"]*"', '', text).strip()
    if len(action) > 150:
        action = action[:150] + "..."

    # Construct simple image prompt
    style = "Korean webtoon style, manhwa comic art, highly detailed, vibrant colors, no text, no speech bubbles, clean art panel"
    image_prompt = f"{setting}, {action}. {style}"

    return {
        "prompt_setting": setting,
        "prompt_actions": action,
        "dialogue": dialogue_str,
        "image_prompt": image_prompt
    }
