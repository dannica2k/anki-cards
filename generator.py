import time
"""
Card generation engine using Gemini API and Course Profiles.
Uses Pydantic response_schema and Unicode notation (no LaTeX backslashes) to guarantee valid JSON.
"""

import os
import json
import re
from pathlib import Path
from pydantic import BaseModel, Field
from google import genai
from google.genai import types


class FlashcardNote(BaseModel):
    text: str = Field(description="Card front text with {{c1::...}}, {{c2::...}}, {{c3::...}} cloze deletions. Use HTML (<br>, <b>) and Unicode symbols (ΔG′°, α, β, γ, ⇌, →, ⁺, ²⁺, ₂) instead of LaTeX backslashes.")
    extra: str = Field(description="Concise high-yield explanation, physiological purpose, or thermodynamic context. Use Unicode symbols instead of LaTeX.")


class FlashcardDeckPayload(BaseModel):
    deck_name: str
    course_display: str
    course_compact: str
    session: str
    tag: str
    notes: list[FlashcardNote]


def get_course_rules(course_code: str, base_dir: Path) -> str:
    """Reads course-specific profile from references/ or falls back to template."""
    clean_code = course_code.replace(" ", "").lower()
    profile_path = base_dir / ".agents" / "skills" / "anki-card-generator" / "references" / f"{clean_code}.md"
    if not profile_path.exists():
        refs = list((base_dir / ".agents" / "skills" / "anki-card-generator" / "references").glob(f"*{clean_code}*.md"))
        if refs:
            profile_path = refs[0]
        else:
            profile_path = base_dir / "MBB_ANKI_PROMPT.md"

    if profile_path.exists():
        return profile_path.read_text(encoding="utf-8")
    return ""


def _safe_parse_json(raw_text: str) -> dict:
    """Parses JSON string, automatically escaping any stray LaTeX backslashes if present."""
    cleaned = re.sub(r'^```json\s*|\s*```$', '', raw_text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Escape any backslash not followed by valid JSON escape chars (" \ / b f n r t u)
        fixed = re.sub(r'\\(?![/\"\\bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', cleaned)
        return json.loads(fixed)


def generate_cards_from_text(slide_text: str, course_code: str, session_num: str, base_dir: Path, api_key: str = None) -> dict:
    """
    Sends slide text + course profile instructions to Gemini,
    returning structured JSON notes following the 3-cloze equation rule.
    """
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    course_rules = get_course_rules(course_code, base_dir)
    course_compact = course_code.replace(" ", "")

    system_prompt = f"""You are an elite biochemistry and university flashcard architect specializing in spaced-repetition (Anki Cloze).
Your mission is to generate high-yield, exam-ready Cloze flashcards from the provided lecture slides for:
Course: {course_code}
Session: {session_num}

### COURSE PEDAGOGICAL RULES & FORMATTING GUIDELINES:
{course_rules}

### CARD GENERATION MANDATES:
1. BIOCHEMICAL REACTIONS: Always follow the standard 3-cloze equation format:
   {{c1::Substrate}} + {{c3::ATP/Cofactor}} ——[{{c2::Enzyme}}]——> {{c1::Product}} + {{c3::ADP/NADH}}
2. ATOMICITY: Never put long multi-sentence explanations into a single cloze.
3. NO BINARY CLOZES: Never cloze high/low, yes/no, increase/decrease. Cloze the molecule or mechanism.
4. THERMODYNAMICS & MECHANISM: Always include cards for ΔG′°, active-site residues (Cys, His, Lys, Glu), Mg²⁺ coordination, tautomerization, and irreversible regulatory steps.
5. EXTRA FIELD: Every single note MUST have an 'extra' field providing concise, high-yield context.
6. UNICODE & HTML ONLY (NO LATEX BACKSLASHES): Format chemical formulas and symbols using clean Unicode and HTML (e.g. ΔG′°, Mg²⁺, NAD⁺, H₂O, α, β, γ, ⇌, →, <b>, <br>). Do NOT use LaTeX backslash commands like \\Delta or \\text.

Set metadata fields as:
- deck_name: "{course_code} - Flashcards"
- course_display: "{course_code}"
- course_compact: "{course_compact}"
- session: "{session_num}"
- tag: "#{course_compact}::Session::{session_num}"
"""

    prompt = f"Here is the extracted text and handwritten annotations from Session {session_num} slides:\n\n{slide_text}"

    models_to_try = ["gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
    response = None
    last_err = None

    for m in models_to_try:
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=m,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        response_mime_type="application/json",
                        response_schema=FlashcardDeckPayload,
                        temperature=0.2
                    )
                )
                if response and response.text:
                    break
            except Exception as e:
                last_err = e
                err_str = str(e)
                if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                else:
                    break
        if response and response.text:
            break

    if not response or not response.text:
        raise last_err

    return _safe_parse_json(response.text)
