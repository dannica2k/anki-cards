"""
Card generation engine using Gemini API, Course Profiles, Multimodal Vision, and Hierarchical Spaced-Repetition.
Guarantees exam-grade coverage, format-aware density calibration, and direct testing of all key concepts.
"""

import os
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel, Field
import pymupdf
from PIL import Image
from google import genai
from google.genai import types


class FlashcardNote(BaseModel):
    text: str = Field(description="Card front text with {{c1::...}}, {{c2::...}}, {{c3::...}} cloze deletions. Use HTML (<br>, <b>) and Unicode symbols (ΔG′°, α, β, γ, ⇌, →, ⁺, ²⁺, ₂) instead of LaTeX backslashes.")
    extra: str = Field(default="", description="Concise high-yield explanation, physiological rationale, or embedded figure tag <img src=\"...\">. Use Unicode symbols instead of LaTeX.")


class FlashcardDeckPayload(BaseModel):
    deck_name: str
    course_display: str
    course_compact: str
    session: str
    tag: str
    notes: List[FlashcardNote]
    media_files: List[str] = []


class BatchCardPayload(BaseModel):
    notes: List[FlashcardNote]


def get_course_rules(course_code: str, base_dir: Path) -> str:
    """Reads course-specific profile from references/ or falls back to template."""
    clean_compact = course_code.replace(" ", "").lower()
    clean_hyphen = re.sub(r'([a-zA-Z]+)\s*(\d+)', r'\1-\2', course_code).lower()
    refs_dir = base_dir / ".agents" / "skills" / "anki-card-generator" / "references"

    for candidate in [refs_dir / f"{clean_hyphen}.md", refs_dir / f"{clean_compact}.md"]:
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")

    refs = list(refs_dir.glob(f"*{clean_compact}*.md")) + list(refs_dir.glob(f"*{clean_hyphen}*.md"))
    if refs:
        return refs[0].read_text(encoding="utf-8")

    fallback = base_dir / "MBB_ANKI_PROMPT.md"
    if fallback.exists():
        return fallback.read_text(encoding="utf-8")
    return ""


def _safe_parse_json(raw_text: str) -> dict:
    """Parses JSON string, automatically escaping any stray LaTeX backslashes if present."""
    cleaned = re.sub(r'^```json\s*|\s*```$', '', raw_text.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        fixed = re.sub(r'\\(?![/\"\\bfnrt]|u[0-9a-fA-F]{4})', r'\\\\', cleaned)
        return json.loads(fixed)


def detect_pdf_layout(doc: pymupdf.Document) -> Dict[str, Any]:
    """
    Detects whether the document is presentation slides (landscape, light text)
    or dense course notes / handouts (letter/portrait, high word count, multiple sections).
    """
    total_pages = len(doc)
    if total_pages == 0:
        return {
            "is_dense_notes": False,
            "format_name": "Unknown",
            "avg_words_per_page": 0,
            "orientation": "unknown"
        }

    total_words = 0
    landscape_count = 0

    for page in doc:
        rect = page.rect
        if rect.width > rect.height * 1.15:
            landscape_count += 1
        text = page.get_text()
        words = len(text.split())
        total_words += words

    avg_words = total_words / max(total_pages, 1)
    is_landscape = landscape_count > (total_pages / 2)

    # If portrait/letter or average words per page > 220, classify as dense course notes
    is_dense = (not is_landscape) or (avg_words > 220)

    format_name = "Dense Course Notes / Handout (Letter/Portrait)" if is_dense else "Presentation Slides (Widescreen Landscape)"

    return {
        "is_dense_notes": is_dense,
        "format_name": format_name,
        "avg_words_per_page": round(avg_words, 1),
        "total_words": total_words,
        "orientation": "Landscape" if is_landscape else "Portrait/Letter"
    }


def extract_pdf_assets(pdf_path: str, output_dir: Path) -> Dict[str, Any]:
    """
    Renders slide snapshots (DPI 150), extracts embedded figures,
    and captures structured text blocks with section headings.
    """
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    layout = detect_pdf_layout(doc)

    slides_data = []
    section_patterns = re.compile(r'(?:Section\s+|SECTION\s+)?\b(\d+[a-zA-Z]?(?:\.\d+)+)\s+([^\n]{3,50})', re.IGNORECASE)
    all_sections_detected = []

    for pno in range(total_pages):
        page = doc[pno]
        text_blocks = []
        b_list = page.get_text("blocks")
        page_text = ""

        for b in b_list:
            t = b[4].strip().replace('\n', ' ')
            if t:
                text_blocks.append(t)
                page_text += " " + t

        # Find section headings
        found_sections = section_patterns.findall(page_text)
        page_sections = []
        for sec_num, sec_title in found_sections:
            clean_sec = f"{sec_num.strip()} {sec_title.strip()[:40]}"
            page_sections.append(clean_sec)
            if clean_sec not in all_sections_detected:
                all_sections_detected.append(clean_sec)

        # Save rendered slide snapshot
        slide_img_name = f"slide_{pno+1:02d}.png"
        slide_img_path = images_dir / slide_img_name
        pix = page.get_pixmap(dpi=150)
        pix.save(str(slide_img_path))

        # Extract embedded figures
        embedded_figures = []
        for img_idx, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            try:
                base_img = doc.extract_image(xref)
                ext = base_img["ext"]
                fig_name = f"slide_{pno+1:02d}_fig_{img_idx+1}.{ext}"
                fig_path = images_dir / fig_name
                with open(fig_path, "wb") as f_out:
                    f_out.write(base_img["image"])
                # Only keep figures of reasonable size (ignore 1x1 tracking pixels/icons)
                if len(base_img["image"]) > 3000:
                    embedded_figures.append(str(fig_path))
            except Exception:
                pass

        slides_data.append({
            "page_num": pno + 1,
            "text": "\n".join(text_blocks),
            "sections": page_sections,
            "snapshot_path": str(slide_img_path),
            "figure_paths": embedded_figures
        })

    return {
        "layout": layout,
        "total_pages": total_pages,
        "sections": all_sections_detected,
        "slides_data": slides_data,
        "images_dir": str(images_dir)
    }


def analyze_lecture_pdf(
    pdf_path: str,
    base_dir: Path,
    course_code: str = "BPK 207",
    session_num: str = "3a",
    api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Performs a fast pre-generation audit of the lecture material:
    - Analyzes document layout and word density
    - Projects card counts across High Level, Regular Recap, and Deep Dive
    - Identifies prof hints, exclusions ("Don't need to know"), and critical diagrams
    - Returns actionable observations and specific quality warnings
    """
    extract_dir = base_dir / "extracted" / f"{course_code.replace(' ', '')}_Session_{session_num}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    cache_file = extract_dir / "audit.json"

    # Return cached audit if PDF hasn't been modified
    if cache_file.exists():
        try:
            if os.path.getmtime(str(cache_file)) >= os.path.getmtime(pdf_path):
                return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    assets = extract_pdf_assets(pdf_path, extract_dir)

    layout = assets["layout"]
    total_pages = assets["total_pages"]
    sections = assets["sections"]
    slides_data = assets["slides_data"]

    # Calculate format-aware card count projections
    is_dense = layout["is_dense_notes"]
    num_sections = max(len(sections), 1)

    if is_dense:
        high_level = max(15, round(num_sections * 0.85 + total_pages * 0.25))
        regular_recap = max(25, round(num_sections * 1.35 + total_pages * 0.45))
        deep_dive = max(40, round(num_sections * 2.2 + total_pages * 0.85))
    else:
        high_level = max(10, round(total_pages * 0.75))
        regular_recap = max(20, round(total_pages * 1.5))
        deep_dive = max(35, round(total_pages * 2.5))

    # Fast scan of text and handwritten annotations across slides
    full_text_sample = "\n".join([f"[Slide {s['page_num']}] {s['text']}" for s in slides_data])
    
    observations = []
    gap_warnings = []

    # Concrete checks
    if re.search(r"not specifically examine|not on the exam|recommend that you read|prerequisite", full_text_sample, re.IGNORECASE):
        observations.append("📌 **Prerequisite / Non-Exam Review Detected:** Sections containing review material (e.g. general cell physiology) will be condensed, focusing strictly on testable definitions.")

    if re.search(r"don'?t need to know|skip|not important", full_text_sample, re.IGNORECASE):
        observations.append("🚫 **Exclusions Detected:** Detected instructor annotations or notes marking specific classifications as *'Don't need to know'* (e.g. specific cutaneous receptor subclasses). These will be excluded from flashcards.")

    fig_count = sum(len(s["figure_paths"]) for s in slides_data)
    if fig_count > 0:
        observations.append(f"🖼️ **Diagram Integration:** Identified **{fig_count} illustrative figures/diagrams**. High-yield figures will be extracted and embedded into the `extra` field of relevant cards.")

    if is_dense:
        gap_warnings.append(f"📄 **Dense Letter Format Detected:** This lecture contains **{layout['avg_words_per_page']} words/page** across **{num_sections} numbered sections**. Generating in **Regular Recap** or **Deep Dive** is recommended to ensure every mechanism is actively tested.")

    result = {
        "layout": layout,
        "total_pages": total_pages,
        "sections": sections,
        "slides_data": slides_data,
        "images_dir": assets["images_dir"],
        "projected_counts": {
            "High Level": high_level,
            "Regular Recap": regular_recap,
            "Deep Dive": deep_dive
        },
        "observations": observations,
        "gap_warnings": gap_warnings
    }

    try:
        cache_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
    except Exception:
        pass

    return result


def generate_cards_chunked(
    slides_data: List[Dict[str, Any]],
    course_code: str,
    session_num: str,
    density_mode: str,
    target_count: int,
    custom_guidance: str,
    base_dir: Path,
    api_key: Optional[str] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Executes chunked multimodal card generation using Gemini Flash:
    - Processes slides in batches of 4-6 pages with multimodal snapshots + text
    - Enforces the Mandatory Testing Mandate (no hiding core facts in extra)
    - Enforces Hierarchical Spaced-Repetition (Parent list card + Child deep-dive cards)
    - Embeds extracted slide figures into the extra field
    - Returns a merged deck payload with packed media
    """
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")

    client = genai.Client(api_key=api_key)
    course_rules = get_course_rules(course_code, base_dir)
    course_compact = course_code.replace(" ", "")
    unit_type = "Chapter" if "::Chapter::" in course_rules else "Session"
    deck_tag = f"#{course_compact}::{unit_type}::{session_num}"

    total_slides = len(slides_data)
    batch_size = 4 if total_slides > 12 else 5
    batches = [slides_data[i:i + batch_size] for i in range(0, total_slides, batch_size)]
    num_batches = len(batches)

    # Allocate target cards per batch
    base_cards_per_batch = max(3, target_count // num_batches)
    extra_cards = target_count % num_batches

    all_notes = []
    used_media_files = set()

    system_instruction = f"""You are a master university flashcard architect specializing in high-yield Anki Cloze generation.
Course: {course_code} ({unit_type} {session_num})
Density Setting: {density_mode}

### COURSE PEDAGOGICAL RULES & FORMULATION STYLE:
{course_rules}

### CARD GENERATION MANDATES:
1. **THE "SUPPORT-ONLY" EXTRA FIELD RULE (ZERO UNTESTED CONCEPTS IN EXTRA)**:
   - The 'extra' field must **STRICTLY SUPPORT** the card's tested clozes; it must **NEVER INTRODUCE NEW OR DEEPER UNTESTED CONCEPTS**.
   - **The Testability Axiom**: If a piece of information is substantive enough to appear on an exam (a specific anatomical structure, mechanism, ion channel, receptor type, threshold, equation, or clinical effect), it **MUST BE TESTED AS AN ACTIVE-RECALL CLOZE NOTE**. It cannot live solely inside 'extra'.
   - **What BELONGS in 'extra'**:
     • **Diagram Grounding**: An embedded figure tag (`<img src="FILENAME">`) with a single concise sentence directing the student to observe the specific visual cue that confirms the clozed answer.
     • **Cross-Referencing Tested Concepts**: Explicit connections or contrasts to other cards in the deck (e.g., *"Contrast with Card on Utricle..."*).
     • **Direct Rationale ("The Why")**: A 1-sentence physiological, anatomical, or chemical explanation reinforcing *why* the clozed relationship is true.
   - **What is STRICTLY FORBIDDEN in 'extra'**:
     • Writing long textbook summaries that explain new physiological cascades, named pathways, or experimental nuances that lack their own flashcard.
2. **THE "EXTRA EXTRACTION" PRINCIPLE (CARD SPAWNING)**:
   - Before writing the 'extra' field of any note, perform this check:
     *"Does this explanation contain a key concept, term, step, or relationship that a professor could test on an exam?"*
     If **YES**, you MUST **EXTRACT IT OUT** and generate a dedicated active-recall Cloze card for it! Keep the original card's 'extra' brief and strictly supportive.
   - **Benchmark Comparison**:
     ❌ *BAD (Buried Mechanisms in Extra):*
       Text: "The {{c1::utricle}} senses acceleration in the horizontal plane."
       Extra: "<img src="fig.png"><br>The utricle contains calcium carbonate stones called otoconia resting atop a gelatinous otolithic membrane. Underneath, hair cells have stereocilia that bend towards a single tall kinocilium to open mechanically gated potassium channels (K+ influx), causing depolarization."
       *(Otoconia, kinocilium, K+ influx, and depolarization are high-yield exam concepts, but the student is never quizzed on them!)*
     ✅ *GOOD (Extracted into Dedicated Cards):*
       • Card 1 (Organ & Plane): "Within the otolith organs, the {{c1::saccule}} senses acceleration in {{c2::the vertical plane}}, whereas the {{c1::utricle}} senses acceleration in {{c2::the horizontal plane}} as well as {{c2::head tilt}} relative to gravity."
         Extra: "<img src="fig.png"><br><b>Spatial Orientation:</b> Utricle macula is oriented horizontally; saccule macula is oriented vertically."
       • Card 2 (Hair Cell Transduction): "In vestibular hair cells, bundle deflection {{c1::towards}} the kinocilium opens mechanically gated channels causing {{c2::K⁺ influx and depolarization}}, whereas deflection {{c1::away from}} the kinocilium causes {{c2::hyperpolarization}}."
         Extra: "<b>Ionic Basis:</b> High K⁺ in endolymph drives passive K⁺ entry into hair cells upon mechanical gating."
       • Card 3 (Otoconia & Inertia): "The otolithic membrane consists of a gelatinous matrix weighted by dense calcium carbonate crystals called {{c1::otoconia}}, which impart {{c2::inertial mass}} that deflects underlying hair cell bundles during linear acceleration."
         Extra: "<b>Function:</b> High density of otoconia causes inertial lag behind head movement, shearing the hair bundles."
3. **HIERARCHICAL SPACED REPETITION (PARENT / CHILD CARDS)**:
   - For multi-part topics or numbered lists (e.g. 3 techniques to study proprioception):
     a) Create an overarching **Parent / Roadmap Card** testing the overall category names and count.
     b) Create dedicated **Child / Deep-Dive Cards** drilling into the exact mechanisms, experimental observations, and physiological distinctions of EACH item.
4. **COORDINATED FUNCTIONAL CLOZE GROUPING (TIERED CATEGORY & DETAIL RULE)**:
   - When testing contrasting pairs, anatomical structures, or categorized lists, NEVER assign sequential arbitrary cloze numbers (e.g., {{c1::A}} ({{c2::X}}) and {{c3::B}} ({{c4::Y}})).
   - Instead, identify the **core concept tiers** and group parallel elements into matching cloze numbers (c1, c2):
     • **c1 (The Structural / Entity Tier):** Cloze all anatomical structures, organ names, classes, or category labels together.
     • **c2 (The Functional / Coordinate / Detail Tier):** Cloze all corresponding physiological roles, planes of motion, axes, or mechanisms together.
   - Benchmark Examples to ALWAYS emulate:
     • *Vestibular End Organs:* "The vestibular system detects head acceleration using two sets of end organs: the {{c1::otoliths}} (which sense {{c2::linear}} acceleration) and the {{c1::semicircular canals}} (which sense {{c2::angular}} acceleration)."
     • *Otolith Organs & Planes:* "Within the otolith organs, the {{c1::saccule}} senses acceleration in {{c2::the vertical plane}}, whereas the {{c1::utricle}} senses acceleration in {{c2::the horizontal plane}} as well as {{c2::head tilt}} relative to gravity."
     • *Rotational Dimensions & Axes:* "The semicircular canals sense angular head acceleration across three rotational dimensions: {{c1::roll}} (around {{c2::x}}-axis), {{c1::pitch}} (around {{c2::y}}-axis), and {{c1::yaw}} (around {{c2::z}}-axis)."
     • *Muscle Spindle Fibers & Afferents:* "Within the muscle spindle, {{c1::dynamic bag1}} fibres are innervated primarily by {{c2::Group Ia}} afferents, whereas {{c1::static bag2 and chain}} fibres are innervated primarily by {{c2::Group II}} afferents."
5. **BIDIRECTIONAL DEFINITION TESTING RULE (TERM ↔ MEANING)**:
   - When a card tests a definition or core scientific concept, NEVER test only in one direction (giving the whole definition and only clozing the term).
   - True exam mastery requires testing in BOTH directions on the note:
     • **`c1` (Term Recall):** Cloze the formal term/concept name (*[Definition] → [Term]*).
     • **`c2` (Definition / Functional Role Recall):** Cloze the complete functional description/definition (*[Term] → [What it actually means/does]*).
     • **`c3` (Underlying Driver / Mechanism Tier, if applicable):** Cloze the driving anatomical structure, effector, or mechanism.
   - **Benchmark Examples to ALWAYS emulate**:
     • *Accommodation:* "{{c2::The dynamic process of altering the shape and curvature of the crystalline lens to focus objects at varying distances onto the retina}} is called {{c1::accommodation}}, which is driven by the contraction and relaxation of the {{c3::ciliary muscles}}."
     • *Proprioception:* "{{c2::The ability to sense the position, orientation, and movement of the body and limbs in space without visual guidance}} is called {{c1::proprioception}}, mediated primarily by {{c3::muscle spindles and Golgi tendon organs}}."
     • *Alpha-Gamma Co-activation:* "{{c2::The simultaneous activation of alpha and gamma motoneurons to maintain intrafusal fiber tautness during muscle contraction}} is called {{c1::alpha-gamma co-activation}}, which prevents {{c3::the spindle from falling slack/silent}}."
6. **FORMULATION & DISCIPLINE ADAPTATION**:
   - For biochemistry/chemistry: use 3-cloze balanced reaction format, ΔG′°, cofactors, active-site residues.
   - For neurobiology/kinesiology: test afferent/efferent wiring, receptor types, stretch/force mechanics, reflex circuits, vibration paradigms, and somatotopic organization.
   - For social sciences: test definitions, theoretical frameworks, contrasting models.
7. **SLIDE DIAGRAM EMBEDDING**:
   - When a slide features an illustrative diagram (available in the extracted figures list), embed it in the 'extra' field using `<img src="FILENAME">` alongside a concise explanation.
8. **ATOMICITY & NO BINARY CLOZES**:
   - Cloze specific molecular players, anatomical structures, or mechanisms. Never cloze generic binary words like high/low, yes/no, increase/decrease.
9. **FORMATTING**:
   - Use clean HTML (<b>, <br>) and Unicode symbols (α, β, γ, Δ, ⇌, →, °, ², ⁺). NEVER use LaTeX backslashes.
"""

    models_to_try = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]

    for b_idx, batch in enumerate(batches):
        b_target = base_cards_per_batch + (1 if b_idx < extra_cards else 0)
        start_slide = batch[0]["page_num"]
        end_slide = batch[-1]["page_num"]

        msg = f"Batch {b_idx + 1}/{num_batches}: Generating {b_target} cards for Slides {start_slide}–{end_slide}..."
        if progress_callback:
            progress_callback(b_idx + 1, num_batches, msg)

        # Prepare multimodal content for batch
        batch_text_parts = [f"=== SLIDE BATCH: Slides {start_slide} to {end_slide} ==="]
        batch_images = []
        batch_available_figures = []

        for s in batch:
            batch_text_parts.append(f"\n--- Slide {s['page_num']} ---")
            if s.get("sections"):
                batch_text_parts.append(f"Sections on this slide: {', '.join(s['sections'])}")
            batch_text_parts.append(s["text"])

            # Attach slide snapshot image if exists
            snap = s.get("snapshot_path")
            if snap and os.path.exists(snap):
                try:
                    img = Image.open(snap)
                    batch_images.append(img)
                except Exception:
                    pass

            # Track extracted figures
            for fig_p in s.get("figure_paths", []):
                fig_name = Path(fig_p).name
                batch_available_figures.append(fig_name)
                used_media_files.add(fig_p)

        if batch_available_figures:
            batch_text_parts.append(f"\nAvailable diagram figures to embed in 'extra' (<img src=\"filename\">): {', '.join(batch_available_figures)}")

        if custom_guidance:
            batch_text_parts.append(f"\nUser Custom Focus Guidance:\n{custom_guidance}")

        batch_prompt = f"""Generate exactly {b_target} distinct, high-yield Anki Cloze flashcards for Slides {start_slide}–{end_slide}.
Ensure thorough coverage of every substantive concept in this batch. Adhere strictly to the "Support-Only" Extra Field Rule, the Extra Extraction Principle, and Hierarchical Parent/Child rules.
REMINDER: Never bury testable mechanisms or key terms in the 'extra' field; extract them into dedicated cards!

Slide Content:
{chr(10).join(batch_text_parts)}
"""

        # Call Gemini with images + prompt
        contents = batch_images + [batch_prompt]
        response = None
        last_err = None

        for m in models_to_try:
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=m,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            system_instruction=system_instruction,
                            response_mime_type="application/json",
                            response_schema=BatchCardPayload,
                            temperature=0.25
                        )
                    )
                    if response and response.text:
                        break
                except Exception as e:
                    last_err = e
                    err_str = str(e)
                    if "503" in err_str or "UNAVAILABLE" in err_str or "429" in err_str:
                        time.sleep(2.0 * (attempt + 1))
                        continue
                    else:
                        break
            if response and response.text:
                break

        if response and response.text:
            parsed = _safe_parse_json(response.text)
            batch_notes = parsed.get("notes", [])
            all_notes.extend(batch_notes)
        else:
            print(f"Warning: Batch {b_idx + 1} generation encountered error: {last_err}")

    if not all_notes and last_err:
        raise RuntimeError(f"Card generation failed: {last_err}")

    # Build final deck payload
    return {
        "deck_name": f"{course_code} - Flashcards",
        "course_display": course_code,
        "course_compact": course_compact,
        "session": str(session_num),
        "tag": deck_tag,
        "notes": all_notes,
        "media_files": list(used_media_files)
    }
