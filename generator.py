"""
Card generation engine using Gemini API, Course Profiles, Multimodal Vision, and Hierarchical Spaced-Repetition.
Guarantees exam-grade coverage, format-aware density calibration, and direct testing of all key concepts.
"""

import os
import io
import re
import json
import time
import html
import base64
import hashlib
import mimetypes
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Tuple
from pydantic import BaseModel, Field
import pymupdf
from PIL import Image
from google import genai
from google.genai import types


class FlashcardNote(BaseModel):
    slide_number: int = Field(
        default=1,
        description="The 1-based slide/page number where this concept appears. You MUST generate notes in strict ascending slide_number order (Slide 1, then Slide 2, then Slide 3, etc.) without jumping back and forth between slides."
    )
    text: str = Field(
        description="Card front text with {{c1::...}}, {{c2::...}}, {{c3::...}} active-recall cloze deletions testing ALL exam-testable facts on this slide. Use HTML (<br>, <b>) and Unicode symbols (ΔG′°, α, β, γ, ⇌, →, ⁺, ²⁺, ₂) instead of LaTeX backslashes."
    )
    extra: str = Field(
        default="",
        description="STRICTLY limited to an embedded slide figure (<img src=\"...\">) and/or a brief 1-sentence non-testable clarification. NEVER place testable subject matter, definitions, reaction types, ΔG values, regulators, cofactors, or mechanisms in extra—all testable facts MUST be tested via {{c1::...}} clozes in `text` or spawned as their own FlashcardNote."
    )


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


class StudyGuideSection(BaseModel):
    heading: str = Field(description="Clear, numbered section heading covering a core lecture topic or mechanism.")
    content_markdown: str = Field(description="Thorough, intuitive explanation using GitHub-flavored Markdown (bold key terms, step-by-step causal chains, and comparison tables where helpful). Use Unicode symbols (ΔG′°, α, β, γ, ⇌, →, ⁺, ²⁺) instead of LaTeX backslashes.")
    figure_filename: str = Field(default="", description="Exact filename of the most relevant extracted slide figure (e.g. 'slide_04_fig_1.png') from the available figures list, or empty string if none applies.")
    figure_caption: str = Field(default="", description="Concise visual walkthrough explaining how to read the diagram and what exam-relevant features to observe.")
    exam_takeaways: List[str] = Field(default_factory=list, description="2 to 4 high-yield exam pearls, experimental paradigms, or common exam traps to watch out for.")


class StudyGuidePayload(BaseModel):
    title: str = Field(description="Comprehensive title for the lecture or topic study guide.")
    executive_summary: str = Field(description="Big-picture synthesis explaining the overarching theme of this lecture/topic and how the mechanisms connect.")
    sections: List[StudyGuideSection] = Field(description="Ordered, in-depth conceptual sections covering the lecture material.")



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


def _get_image_pixels(im: Image.Image) -> list:
    """Returns flat pixel list across Pillow versions without deprecation warnings."""
    if hasattr(im, "get_flattened_data"):
        return list(im.get_flattened_data())
    return list(im.getdata())


def _is_valid_educational_figure(
    img_bytes: bytes,
    pno: int = 1,
    total_pages: int = 15,
    page_occurrence_count: int = 1
) -> bool:
    """
    Filters out non-educational / decorative slide images before card generation:
    1. Rejects cover/title slide (Slide 1) decorative banners in multi-slide decks.
    2. Rejects template/watermark graphics repeated across multiple slides in the same deck.
    3. Rejects tiny icons, badges, or thin divider strips.
    4. Rejects camera photographs (e.g., campus/SFU building photos, classroom photos, portraits)
       which lack the white or transparent/uniform background of scientific diagrams.
    5. Rejects dark-background stock illustrations with high photographic color entropy.
    """
    if not img_bytes or len(img_bytes) <= 3000:
        return False
    if pno == 0 and total_pages > 2:
        return False
    if page_occurrence_count > 1:
        return False

    try:
        with Image.open(io.BytesIO(img_bytes)) as im:
            w, h = im.size
            if w < 100 or h < 45:
                return False
            aspect = w / max(h, 1)
            if aspect > 12.0 or aspect < 0.12:
                return False

            has_transparency = False
            if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
                rgba = im.convert("RGBA").resize((100, 100))
                alpha_vals = [px[3] for px in _get_image_pixels(rgba)]
                transparent_frac = sum(1 for a in alpha_vals if a < 30) / max(len(alpha_vals), 1)
                if transparent_frac >= 0.15:
                    has_transparency = True

            rgb = im.convert("RGB").resize((100, 100))
            pixels = _get_image_pixels(rgb)
            n_px = max(len(pixels), 1)
            near_white = sum(1 for r, g, b in pixels if r > 235 and g > 235 and b > 235) / n_px
            near_black = sum(1 for r, g, b in pixels if r < 20 and g < 20 and b < 20) / n_px
            buckets = len(set((r >> 4, g >> 4, b >> 4) for r, g, b in pixels))

            # Camera photographs (campus buildings, classroom scenes, scientist portraits)
            if not has_transparency and (near_white + near_black) < 0.12:
                return False

            # Dark-background stock art / decorative 3D splash graphics
            if not has_transparency and near_white < 0.15 and buckets > 450:
                return False

            return True
    except Exception:
        return False


def _sanitize_note_extra_images(notes: List[Dict[str, Any]], valid_filenames: set) -> List[Dict[str, Any]]:
    """
    Strips any `<img src="...">` tag in `extra` whose filename is not in the whitelisted
    educational figures extracted for the current lecture/batch.
    """
    img_tag_re = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
    for n in notes:
        extra = n.get("extra", "")
        if not extra or "<img" not in extra.lower():
            continue

        def _check_img(match: re.Match) -> str:
            src = match.group(1).strip()
            if src in valid_filenames:
                return match.group(0)
            return ""

        cleaned = img_tag_re.sub(_check_img, extra)
        cleaned = re.sub(r'^(?:\s*<br\s*/?>\s*)+', '', cleaned, flags=re.IGNORECASE).strip()
        n["extra"] = cleaned
    return notes


def extract_pdf_assets(pdf_path: str, output_dir: Path, file_prefix: str = "") -> Dict[str, Any]:
    """
    Renders slide snapshots (DPI 150), extracts embedded educational figures with
    globally unique session+hash-scoped filenames (filtering out decorative photos,
    campus pictures, portraits, and repeated slide-template graphics), and captures
    structured text blocks with section headings.
    """
    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    clean_prefix = re.sub(r'[^A-Za-z0-9_]', '', file_prefix or output_dir.name) or "deck"

    doc = pymupdf.open(pdf_path)
    total_pages = len(doc)
    layout = detect_pdf_layout(doc)

    # First pass: count how many distinct pages each image xref appears on to detect template/watermark graphics
    xref_page_counts: Dict[int, int] = {}
    for pno in range(total_pages):
        seen_on_page = set()
        for img_info in doc[pno].get_images(full=True):
            xref = img_info[0]
            if xref not in seen_on_page:
                seen_on_page.add(xref)
                xref_page_counts[xref] = xref_page_counts.get(xref, 0) + 1

    slides_data = []
    unit_blacklist = re.compile(
        r'^(?:kJ|kcal|J|cal|mol|mmol|μmol|umol|nmol|M|mM|μM|uM|nM|pM|mg|g|kg|μg|ug|ng|L|mL|μL|uL|'
        r'Hz|kHz|ms|s|sec|min|hr|h|nm|μm|um|mm|cm|m|km|V|mV|pH|atm|bar|Pa|kPa|%|°C|K|Da|kDa|Å|'
        r'BPG|bisphosphoglycerate|fold|times|x)\b',
        re.IGNORECASE
    )
    section_line_pattern = re.compile(
        r'^\s*(?:(?:Section|Topic|Part|Module)\s+(\d{1,2}[a-zA-Z]?(?:\.\d+)*)|(\d{1,2}[a-zA-Z]?(?:\.\d+)+))\s*[:.\-–—)]?\s+([A-Z][A-Za-z0-9\s,:\-–—/&+()\'’]{2,65})\s*$'
    )
    all_sections_detected = []

    for pno in range(total_pages):
        page = doc[pno]
        text_blocks = []
        b_list = page.get_text("blocks")
        page_sections = []

        for b in b_list:
            raw_block = b[4].strip()
            if not raw_block:
                continue
            for raw_line in raw_block.splitlines():
                line_clean = raw_line.strip()
                m_sec = section_line_pattern.match(line_clean)
                if m_sec:
                    sec_num = (m_sec.group(1) or m_sec.group(2) or "").strip()
                    sec_title = (m_sec.group(3) or "").strip()
                    if sec_num and sec_title and not unit_blacklist.match(sec_title):
                        clean_sec = f"{sec_num} {sec_title[:40]}".strip()
                        if clean_sec not in page_sections:
                            page_sections.append(clean_sec)
                        if clean_sec not in all_sections_detected:
                            all_sections_detected.append(clean_sec)
            t = raw_block.replace('\n', ' ')
            if t:
                text_blocks.append(t)

        # Save rendered slide snapshot
        slide_img_name = f"slide_{pno+1:02d}.png"
        slide_img_path = images_dir / slide_img_name
        pix = page.get_pixmap(dpi=150)
        pix.save(str(slide_img_path))

        # Extract embedded educational figures (excluding decorative photos & template art)
        embedded_figures = []
        for img_idx, img_info in enumerate(page.get_images(full=True)):
            xref = img_info[0]
            try:
                base_img = doc.extract_image(xref)
                img_bytes = base_img["image"]
                ext = base_img["ext"]
                if not _is_valid_educational_figure(
                    img_bytes,
                    pno=pno,
                    total_pages=total_pages,
                    page_occurrence_count=xref_page_counts.get(xref, 1)
                ):
                    continue
                img_hash = hashlib.sha1(img_bytes).hexdigest()[:6]
                fig_name = f"{clean_prefix}_slide_{pno+1:02d}_fig_{img_idx+1}_{img_hash}.{ext}"
                fig_path = images_dir / fig_name
                with open(fig_path, "wb") as f_out:
                    f_out.write(img_bytes)
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

    doc.close()

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
    course_compact = re.sub(r'[^A-Za-z0-9]', '', course_code) or "COURSE"
    clean_session = re.sub(r'[^A-Za-z0-9_-]', '', str(session_num)) or "1"
    extract_dir = base_dir / "extracted" / f"{course_compact}_Session_{clean_session}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    cache_file = extract_dir / "audit.json"

    # Return cached audit if PDF hasn't been modified and schema version is current
    if cache_file.exists():
        try:
            if os.path.getmtime(str(cache_file)) >= os.path.getmtime(pdf_path):
                cached = json.loads(cache_file.read_text(encoding="utf-8"))
                if cached.get("audit_version") == 3:
                    return cached
        except Exception:
            pass

    assets = extract_pdf_assets(pdf_path, extract_dir, file_prefix=f"{course_compact}_S{clean_session}")

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
        "audit_version": 3,
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


DEFAULT_MODELS_TO_TRY = [
    "gemini-3.5-flash",        # Tier 1: Primary flagship 3.5 Flash (highest quality & accuracy)
    "gemini-3-flash-preview",  # Tier 2: Full Gemini 3 Flash fallback
    "gemini-2.5-flash",        # Tier 3: Stable 2.5 Flash fallback
    "gemini-3.5-flash-lite",   # Tier 4: High-quota 3.5 Flash Lite (last-resort fallback)
    "gemini-3.1-flash-lite",   # Tier 5: Backup high-quota Lite tier
]


def _create_genai_client(api_key: str, timeout_ms: int = 60_000) -> genai.Client:
    """
    Creates a Gemini client with a strict per-request timeout and single attempt
    (disabling hidden multi-minute SDK backoff loops) so model/key failover is immediate.
    """
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=timeout_ms,
            retry_options=types.HttpRetryOptions(attempts=1)
        )
    )


def _generate_with_thinking(
    client: genai.Client,
    model: str,
    contents: List[Any],
    system_instruction: str,
    response_schema: Any,
    temperature: float = 0.25,
    thinking_budget: int = 4096
):
    """
    Invokes `client.models.generate_content` with a bounded `thinking_budget` (default 4096 tokens)
    so the model has full reasoning depth for 4–6 cards without stalling in runaway thinking loops.
    Automatically retries without `thinking_config` if an endpoint does not support it.
    """
    try:
        return client.models.generate_content(
            model=model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=response_schema,
                temperature=temperature,
                thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget)
            )
        )
    except Exception as e:
        err_lower = str(e).lower()
        if "thinking" in err_lower or ("400" in err_lower and "invalid_argument" in err_lower):
            return client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    response_schema=response_schema,
                    temperature=temperature
                )
            )
        raise


def _ordered_candidate_models(preferred_model: Optional[str], dead_models: set) -> List[str]:
    """
    Returns candidate models for a batch, placing the proven working full-tier model first
    and skipping any model endpoints that previously returned 404 / NOT_FOUND.
    """
    candidates = []
    if preferred_model and preferred_model not in dead_models:
        candidates.append(preferred_model)
    for m in DEFAULT_MODELS_TO_TRY:
        if m not in dead_models and m not in candidates:
            candidates.append(m)
    return candidates or list(DEFAULT_MODELS_TO_TRY)


def _group_slides_by_subsections(
    slides_data: List[Dict[str, Any]],
    max_subsections_per_batch: int = 4,
    max_slides_per_batch: int = 6
) -> List[Dict[str, Any]]:
    """
    Groups slides into logical batches covering up to `max_subsections_per_batch`
    detected sub-sections (or up to `max_slides_per_batch` slides when no numbered
    sub-sections are present).
    """
    batches = []
    cur_slides = []
    cur_sections = []

    for s in slides_data:
        s_secs = [sec for sec in s.get("sections", []) if sec not in cur_sections]
        would_exceed_secs = (len(cur_sections) + len(s_secs) > max_subsections_per_batch) and len(cur_slides) > 0
        would_exceed_slides = len(cur_slides) >= max_slides_per_batch

        if would_exceed_secs or would_exceed_slides:
            batches.append({
                "slides": cur_slides,
                "subsections": cur_sections,
                "start_slide": cur_slides[0]["page_num"],
                "end_slide": cur_slides[-1]["page_num"]
            })
            cur_slides = []
            cur_sections = []
            s_secs = list(s.get("sections", []))

        cur_slides.append(s)
        for sec in s_secs:
            if sec not in cur_sections:
                cur_sections.append(sec)

    if cur_slides:
        batches.append({
            "slides": cur_slides,
            "subsections": cur_sections,
            "start_slide": cur_slides[0]["page_num"],
            "end_slide": cur_slides[-1]["page_num"]
        })

    return batches


def _allocate_cards_across_batches(batches: List[Dict[str, Any]], target_count: int) -> List[int]:
    """
    Allocates `target_count` proportionally across logical sub-section batches
    based on each batch's slide count and sub-section density.
    """
    n = len(batches)
    if n == 0:
        return []
    if n == 1:
        return [max(1, target_count)]

    weights = [max(1.0, len(b["slides"]) + 0.5 * len(b.get("subsections", []))) for b in batches]
    total_w = sum(weights)
    effective_target = max(target_count, 2 * n)

    allocs = [max(2, int(round(effective_target * (w / total_w)))) for w in weights]
    diff = effective_target - sum(allocs)
    # Adjust largest/smallest batches so total matches effective_target
    order = sorted(range(n), key=lambda i: weights[i], reverse=(diff > 0))
    idx = 0
    while diff != 0 and idx < n * 4:
        b_i = order[idx % n]
        if diff > 0:
            allocs[b_i] += 1
            diff -= 1
        elif diff < 0 and allocs[b_i] > 2:
            allocs[b_i] -= 1
            diff += 1
        idx += 1
    return allocs


def _build_lecture_header_md(
    slides_data: List[Dict[str, Any]],
    course_code: str,
    session_num: str,
    course_rules: str,
    base_dir: Path
) -> Tuple[Path, Dict[str, str], List[str]]:
    """
    Builds and saves `<guide_id>_header.md` containing course rules, the complete
    lecture sub-section roadmap, figure inventory, and slide text for Gemini File API reference.
    """
    guide_id = re.sub(r'[^A-Za-z0-9]', '', course_code).upper() or "COURSE"
    clean_session = re.sub(r'[^A-Za-z0-9_-]', '', str(session_num)) or "1"
    guide_id = f"{guide_id}_Session_{clean_session}"

    figure_map: Dict[str, str] = {}
    all_detected_sections: List[str] = []
    slide_lines: List[str] = []

    for s in slides_data:
        pno = s["page_num"]
        s_secs = s.get("sections", [])
        for sec in s_secs:
            if sec not in all_detected_sections:
                all_detected_sections.append(sec)

        s_figs = []
        for fig_p in s.get("figure_paths", []):
            fname = Path(fig_p).name
            figure_map[fname] = fig_p
            s_figs.append(fname)

        slide_lines.append(f"\n### Slide {pno}")
        if s_secs:
            slide_lines.append(f"- **Detected Sub-Sections:** {', '.join(s_secs)}")
        if s_figs:
            slide_lines.append(f"- **Extracted Slide Figures:** {', '.join(s_figs)}")
        slide_lines.append(s.get("text", ""))

    roadmap_lines = (
        [f"- {sec}" for sec in all_detected_sections]
        if all_detected_sections
        else [f"- Slides 1 to {len(slides_data)}"]
    )

    header_md_lines = [
        f"# Lecture Reference Header: {course_code} (Session/Chapter {session_num})",
        "",
        "## 1. Course Pedagogical Profile & Rules",
        course_rules,
        "",
        "## 2. Complete Lecture Sub-Section Roadmap",
        *roadmap_lines,
        "",
        "## 3. Slide-by-Slide Lecture Content & Figure Inventory",
        *slide_lines,
    ]

    guides_dir = base_dir / "extracted" / "study_guides"
    guides_dir.mkdir(parents=True, exist_ok=True)
    header_md_path = guides_dir / f"{guide_id}_header.md"
    header_md_path.write_text("\n".join(header_md_lines), encoding="utf-8")
    return header_md_path, figure_map, all_detected_sections


def generate_cards_chunked(
    slides_data: List[Dict[str, Any]],
    course_code: str,
    session_num: str,
    density_mode: str,
    target_count: int,
    custom_guidance: str,
    base_dir: Path,
    api_key: Optional[str] = None,
    api_keys_pool: Optional[List[str]] = None,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> Dict[str, Any]:
    """
    Executes chunked multimodal card generation using Gemini Flash:
    - Groups slides into logical sub-section batches (up to 4 sub-sections / 6 slides)
    - Uploads consolidated `<guide_id>_header.md` once via Gemini File API so every batch
      has full-lecture roadmap context while focusing on its assigned sub-sections
    - Preserves full 150 DPI native slide snapshots for maximum diagram/subscript legibility
    - Enforces the Mandatory Testing Mandate (no hiding core facts in extra)
    - Enforces Hierarchical Spaced-Repetition (Parent list card + Child deep-dive cards)
    - Automatically fails over across user personal keys, project keys, and sticky model tiers
    - Returns a merged deck payload with packed media
    """
    raw_keys = (api_keys_pool or []) + ([api_key] if api_key else [])
    if not raw_keys:
        env_key = os.getenv("GEMINI_API_KEY")
        if env_key:
            raw_keys.append(env_key)

    active_keys = []
    seen = set()
    for k in raw_keys:
        if not k:
            continue
        clean = k.strip()
        if not (clean.startswith("AQ.") or clean.startswith("AIzaSy")):
            clean = f"AQ.{clean}"
        if clean not in seen:
            seen.add(clean)
            active_keys.append(clean)

    if not active_keys:
        raise ValueError("No Gemini API key available. Please provide an API key in your Google Account profile or Settings.")

    course_rules = get_course_rules(course_code, base_dir)
    course_compact = course_code.replace(" ", "")
    unit_type = "Chapter" if "::Chapter::" in course_rules else "Session"
    deck_tag = f"#{course_compact}::{unit_type}::{session_num}"

    # 1. Build consolidated Lecture Reference Header (.md) for full-lecture context
    header_md_path, _, _ = _build_lecture_header_md(
        slides_data=slides_data,
        course_code=course_code,
        session_num=str(session_num),
        course_rules=course_rules,
        base_dir=base_dir
    )

    # 2. Group slides by logical sub-sections (up to 4 sub-sections or 6 slides per batch)
    batches = _group_slides_by_subsections(
        slides_data,
        max_subsections_per_batch=4,
        max_slides_per_batch=6
    )
    num_batches = max(1, len(batches))
    batch_allocations = _allocate_cards_across_batches(batches, target_count)

    all_notes = []
    used_media_files = set()
    figure_path_by_name: Dict[str, str] = {}

    system_instruction = f"""You are a master university flashcard architect specializing in high-yield Anki Cloze generation.
Course: {course_code} ({unit_type} {session_num})
Density Setting: {density_mode}

### COURSE PEDAGOGICAL RULES & FORMULATION STYLE:
{course_rules}

### CARD GENERATION MANDATES:
0. **CHRONOLOGICAL SLIDE-BY-SLIDE SEQUENCING RULE (STRICT SLIDE ORDER)**:
   - You MUST process slides in **strict ascending numerical order** (e.g., all cards for Slide 1 first, then all cards for Slide 2, then Slide 3, etc.).
   - **NEVER jump back and forth between slides** in your card sequence.
   - Set `slide_number` accurately on every `FlashcardNote` to match the 1-based slide number where that concept appears.
   - Within a single slide, place any overarching **Parent / Roadmap Card** first, immediately followed by its **Child / Mechanism Cards** for that same slide before advancing to the next slide.
1. **100% TESTABLE MATERIAL COVERAGE & IMAGE/CLARIFICATION-ONLY EXTRA FIELD RULE**:
   - **Complete Testable Coverage Mandate**: Every single exam-testable fact on each slide (definitions, pathways, reaction types, enzymes, cofactors, ΔG′° values, allosteric activators/inhibitors, catalytic residues, anatomical structures, physiological mechanisms, and experimental results) **MUST BE COVERED BY ACTIVE-RECALL CLOZE CARDS** (`{{{{c1::...}}}}`, `{{{{c2::...}}}}`, `{{{{c3::...}}}}` in `text`).
   - **What BELONGS in `extra` (STRICTLY IMAGES & BRIEF CLARIFICATION)**:
     • **Slide Images / Diagrams**: An embedded figure tag (`<img src="FILENAME">`) when an extracted figure exists for that slide.
     • **Brief Clarification Only**: At most a short 1-sentence visual pointer or non-testable clarifying note (or leave `extra` empty `""` if no image or clarification is needed).
   - **What is STRICTLY FORBIDDEN in `extra`**:
     • **NEVER** place testable subject matter, definitions, reaction classifications, ΔG′° numbers, allosteric regulators, cofactors, anatomical pathways, or physiological cascades in `extra`.
2. **THE "EXTRA EXTRACTION" & COVERAGE AUDIT RULE (CARD SPAWNING)**:
   - Before outputting your JSON notes for a batch, perform a mandatory **Coverage & Extra Audit** across every slide in the batch:
     1) *Is every testable concept on Slide X covered by an active-recall Cloze deletion in `text`?*
     2) *Does any card's `extra` field contain a testable fact, term, reaction type, regulator, ΔG′° value, or mechanism?*
   - If **YES** to (2), or if any testable concept on a slide is missing a card, you **MUST remove the testable material from `extra` and spawn a dedicated `FlashcardNote` for that slide** (placed in proper slide sequence). Treat the requested card count as a baseline minimum—always generate additional cards rather than burying testable material in `extra`.
   - **Benchmark Comparison**:
     ❌ *BAD (Buried Testable Material in Extra):*
       Text: "The {{{{c1::utricle}}}} senses acceleration in the horizontal plane."
       Extra: "<img src="fig.png"><br>The utricle contains calcium carbonate stones called otoconia resting atop a gelatinous otolithic membrane. Underneath, hair cells have stereocilia that bend towards a single tall kinocilium to open mechanically gated potassium channels (K+ influx), causing depolarization."
       *(Otoconia, kinocilium, K+ influx, and depolarization are testable exam concepts buried in extra!)*
     ✅ *GOOD (Extracted into Dedicated Cards, Extra has Image + Brief Clarification Only):*
       • Card 1 (Slide 4 - Organ & Plane): "Within the otolith organs, the {{{{c1::saccule}}}} senses acceleration in {{{{c2::the vertical plane}}}}, whereas the {{{{c1::utricle}}}} senses acceleration in {{{{c2::the horizontal plane}}}} as well as {{{{c2::head tilt}}}} relative to gravity."
         Extra: "<img src="fig.png"><br><b>Diagram note:</b> Notice the perpendicular orientation of the utricular and saccular maculae."
       • Card 2 (Slide 4 - Otoconia & Inertia): "The otolithic membrane consists of a gelatinous matrix weighted by dense calcium carbonate crystals called {{{{c1::otoconia}}}}, which impart {{{{c2::inertial mass}}}} that deflects underlying hair cell bundles during linear acceleration."
         Extra: ""
       • Card 3 (Slide 4 - Hair Cell Transduction): "In vestibular hair cells, bundle deflection {{{{c1::towards}}}} the kinocilium opens mechanically gated channels causing {{{{c2::K⁺ influx and depolarization}}}}, whereas deflection {{{{c1::away from}}}} the kinocilium causes {{{{c2::hyperpolarization}}}}."
         Extra: ""
3. **UNBUNDLE MULTI-STEP ENZYMATIC CASCADES & HIERARCHICAL PARENT/CHILD CARDS**:
   - **Never cram a multi-step enzymatic cascade (e.g., PDH E1 → E2 → E3) into a single run-on sentence with 6–8 clozes!**
   - Instead:
     a) Create a **Parent / Subunit Card** pairing subunit abbreviations (`c1`) with full enzyme names (`c2`):
        `"The Pyruvate Dehydrogenase (PDH) complex is composed of three catalytic subunits: {{{{c1::E1}}}} ({{{{c2::pyruvate dehydrogenase}}}}), {{{{c1::E2}}}} ({{{{c2::dihydrolipoyl transacetylase}}}}), and {{{{c1::E3}}}} ({{{{c2::dihydrolipoyl dehydrogenase}}}})."`
     b) Immediately follow it (in sequential order) with **1 concise card per partial reaction step**, each beginning with a clear **Pathway/Subunit Context Prefix** (e.g., `PDH (E1 Decarboxylation):`, `PDH (E1 → E2 Transfer):`, `PDH (E2 Transesterification):`, `PDH (E3 Reoxidation):`) and embedding the corresponding slide diagram in `extra`.
4. **COORDINATED 2-TIER FUNCTIONAL CLOZE GROUPING & ATOMIC CLOZE HYGIENE**:
   - **Prefer 2 Coordinated Cloze Tiers (`c1` and `c2`)** on conceptual and mechanistic cards (reserving `c3` for 3-part balanced reaction equations when needed):
     • **`c1` (Structural / Entity / Subunit / Cofactor Tier):** Cloze anatomical structures, enzyme subunits, cofactors, orbitals, or bond types.
     • **`c2` (Functional / Outcome / Intermediate / Mechanism Tier):** Cloze corresponding physiological roles, reaction outcomes, intermediates, or qualitative thermodynamic properties.
   - **Max 3–4 Cloze Boxes per Card**: Never place 5–9 cloze boxes in a single sentence, and never collapse 4+ blanks into `c1` ("Swiss cheese sentence"). If a slide has 6–8 testable facts, split them into 2 concise sequential cards on that slide.
   - **No Adjacent Cognate Giveaways**: Never place root-related words in adjacent clozes (e.g., never write `the {{{{c1::carboxylate}}}} group {{{{c2::decarboxylates}}}}` where the visible word gives away the blank).
   - Benchmark Examples to ALWAYS emulate:
     • *CoA Structure/Function:* `"{{{{c2::Coenzyme A (CoA)}}}} is an activated {{{{c1::acyl-group}}}} carrier with a high transfer potential that attaches acyl groups to its terminal {{{{c1::thiol (-SH)}}}} group."`
     • *Vestibular End Organs:* `"The vestibular system detects head acceleration using two sets of end organs: the {{{{c1::otoliths}}}} (which sense {{{{c2::linear}}}} acceleration) and the {{{{c1::semicircular canals}}}} (which sense {{{{c2::angular}}}} acceleration)."`
     • *Muscle Spindle Fibers & Afferents:* `"Within the muscle spindle, {{{{c1::dynamic bag1}}}} fibres are innervated primarily by {{{{c2::Group Ia}}}} afferents, whereas {{{{c1::static bag2 and chain}}}} fibres are innervated primarily by {{{{c2::Group II}}}} afferents."`
5. **NATURAL SUBJECT-FIRST BIDIRECTIONAL DEFINITIONS (NO 20-WORD "JEOPARDY" CLAUSES)**:
   - Write definitions in natural **Subject → Predicate** order. NEVER start a card by clozing a 15–25 word definition clause (`"{{{{c2::Long 20-word definition...}}}} is called {{{{c1::Term}}}}"`).
   - Instead, put the term in `c1` (or `c2`) at the subject position and cloze the short 1–4 word defining functional phrases in `c2` (or `c1`) so both directions are tested with crisp, atomic blanks:
     • *Ping-Pong Mechanism:* `"The PDH complex operates via a {{{{c1::Ping-Pong}}}} kinetic mechanism (classified as a {{{{c2::tri-tri}}}} reaction), in which {{{{c2::products are released sequentially between substrate additions}}}} via covalent enzyme intermediates."`
     • *Accommodation:* `"{{{{c1::Accommodation}}}} is the dynamic process of {{{{c2::altering the shape and curvature of the crystalline lens}}}} to focus objects at varying distances onto the retina, driven by the {{{{c2::ciliary muscles}}}}."`
6. **QUALITATIVE THERMODYNAMICS, ZERO HISTORICAL TRIVIA, & TYPO FACT-CHECKING**:
   - **Qualitative Thermodynamics Over Raw Decimals**: Cloze whether a reaction is `{{{{c1::exergonic}}}}`/`endergonic` and `{{{{c1::irreversible}}}}`/`reversible` along with the chemical/orbital rationale (`{{{{c1::3p}}}}` vs `{{{{c1::2p}}}}` orbital overlap, `{{{{c1::C–S}}}}` vs `{{{{c1::C–O}}}}` bond stability, `{{{{c2::resonance stabilization}}}}`), keeping exact ΔG′° decimal numbers (`–29.6 kJ/mol`, `–33.5 kJ/mol`) un-clozed in parentheses for context unless the slide specifically contrasts energy-yield tiers.
   - **Zero Historical Trivia & Zero Recap Duplicates**: Never generate cards testing scientist names, Nobel Prizes, or discovery years (e.g., Fritz Lipmann / Hans Krebs 1953). Never generate duplicate summary cards from a lecture's final recap slide when those facts were already tested on earlier slides.
   - **Biochemical Fact-Checking of Slide Typos**: If a slide has an obvious scientific typo (e.g., stating NAD⁺ is derived from Vitamin B12 instead of **Vitamin B3 / niacin**), always test the **biochemically accurate fact** (`{{{{c2::Vitamin B3 (niacin)}}}}`) on the card front and mention the slide typo in `extra`.
7. **SLIDE DIAGRAM EMBEDDING & STRICT VISUAL RELEVANCE GATE**:
   - Visually inspect each `[Candidate Figure on Slide X: FILENAME]` before embedding `<img src="FILENAME">` in `extra`.
   - **ONLY** embed `<img src="FILENAME">` if that specific image is a **scientific diagram, chemical structure, reaction scheme, pathway flowchart, graph, or anatomical/molecular model** that **directly illustrates the exact concept tested on that card** (and belongs to the same slide!).
   - **NEVER** embed campus/building photographs (e.g., SFU buildings), classroom/student photos, portraits of scientists, decorative stock graphics, or unrelated figures from a different slide/step. If no candidate figure on that slide is a relevant scientific diagram for the card, leave `<img ...>` out of `extra`.
8. **ATOMICITY & NO BINARY CLOZES**:
   - Cloze specific molecular players, anatomical structures, or mechanisms. Never cloze generic binary words like high/low, yes/no, increase/decrease, or arbitrary step index numbers (`Step {{{{c1::0}}}}`).
9. **FORMATTING**:
   - Use clean HTML (<b>, <br>) and Unicode symbols (α, β, γ, Δ, ⇌, →, °, ², ⁺). NEVER use LaTeX backslashes.
"""

    uploaded_refs: Dict[str, Any] = {}
    dead_models: set = set()
    preferred_model: Optional[str] = None
    last_err = None

    try:
        for b_idx, batch in enumerate(batches):
            b_target = batch_allocations[b_idx]
            start_slide = batch["start_slide"]
            end_slide = batch["end_slide"]
            sub_secs = batch.get("subsections", [])
            batch_slides = batch["slides"]

            if sub_secs:
                sec_label = ", ".join(sub_secs[:3])
                msg = f"Generating {b_target} cards for Sub-sections {sec_label} (Slides {start_slide}–{end_slide})..."
            else:
                msg = f"Generating {b_target} cards for Slides {start_slide}–{end_slide}..."

            if progress_callback:
                progress_callback(b_idx + 1, num_batches, msg)

            # Prepare multimodal content for batch (preserving full 150 DPI snapshots)
            batch_text_parts = [f"=== SLIDE BATCH: Slides {start_slide} to {end_slide} ==="]
            if sub_secs:
                batch_text_parts.append(f"Assigned Sub-Sections in this batch: {', '.join(sub_secs)}")
            batch_images = []
            batch_available_figures = []

            for s in batch_slides:
                batch_text_parts.append(f"\n--- Slide {s['page_num']} ---")
                if s.get("sections"):
                    batch_text_parts.append(f"Sections on this slide: {', '.join(s['sections'])}")
                s_fig_names = [Path(fp).name for fp in s.get("figure_paths", [])]
                if s_fig_names:
                    batch_text_parts.append(f"Extracted Figures on Slide {s['page_num']}: {', '.join(s_fig_names)}")
                else:
                    batch_text_parts.append(f"Extracted Figures on Slide {s['page_num']}: None")
                batch_text_parts.append(s["text"])

                # Attach full-resolution 150 DPI slide snapshot image if exists
                snap = s.get("snapshot_path")
                if snap and os.path.exists(snap):
                    try:
                        with Image.open(snap) as im:
                            im.load()
                            batch_images.append(im.copy())
                    except Exception:
                        pass

                # Track extracted figures and attach labeled visual thumbnail for relevance verification
                for fig_p in s.get("figure_paths", []):
                    fig_name = Path(fig_p).name
                    batch_available_figures.append(fig_name)
                    figure_path_by_name[fig_name] = fig_p
                    if os.path.exists(fig_p):
                        try:
                            with Image.open(fig_p) as fim:
                                fim.load()
                                thumb = fim.copy()
                                thumb.thumbnail((256, 256))
                                batch_images.append(f"[Candidate Figure on Slide {s['page_num']}: {fig_name}]")
                                batch_images.append(thumb)
                        except Exception:
                            pass

            if batch_available_figures:
                batch_text_parts.append(
                    f"\nValid diagram filenames in this batch (ONLY embed if visually verified as a relevant scientific diagram for that card): {', '.join(batch_available_figures)}"
                )

            if custom_guidance:
                batch_text_parts.append(f"\nUser Custom Focus Guidance:\n{custom_guidance}")

            subsec_context = (
                f"covering Sub-sections ({', '.join(sub_secs)}) on Slides {start_slide}–{end_slide}"
                if sub_secs
                else f"for Slides {start_slide}–{end_slide}"
            )

            batch_prompt = f"""Referencing the uploaded Lecture Reference Header (.md) for overall lecture context, generate at least {b_target} distinct, high-yield Anki Cloze flashcards specifically {subsec_context}.
CRITICAL SEQUENCING, COVERAGE & IMAGE RELEVANCE RULES FOR THIS BATCH:
1. **Strict Slide Sequence**: Walk through Slides {start_slide} to {end_slide} in exact numerical order (Slide {start_slide} first, then Slide {min(start_slide + 1, end_slide)}, ..., up to Slide {end_slide}). Set `slide_number` on every note and NEVER jump back and forth between slides.
2. **100% Testable Coverage (Zero Testable Material in `extra`)**: Every testable concept, mechanism, reaction type, enzyme, cofactor, ΔG′° value, regulator, or definition on Slides {start_slide}–{end_slide} MUST be tested via `{{{{c1::...}}}}`/`{{{{c2::...}}}}`/`{{{{c3::...}}}}` clozes in `text`. If a slide has more testable material than fits on one card, spawn additional cards for that slide!
3. **Strict Visual Relevance Gate for `extra`**: Visually inspect the `[Candidate Figure on Slide X: FILENAME]` thumbnails before embedding `<img src="FILENAME">`. ONLY embed a figure if it is a genuine scientific diagram, chemical structure, pathway chart, or graph from that card's slide that directly illustrates the tested concept. NEVER embed campus/building photos, portraits, decorative graphics, or unrelated figures!

Slide Content for this Batch:
{chr(10).join(batch_text_parts)}
"""

            response = None
            candidate_models = _ordered_candidate_models(preferred_model, dead_models)

            for m_idx, m in enumerate(candidate_models):
                model_503 = False
                for k in active_keys:
                    client = _create_genai_client(k, timeout_ms=60_000)
                    try:
                        if k not in uploaded_refs and header_md_path and header_md_path.exists():
                            try:
                                uploaded_refs[k] = client.files.upload(
                                    file=str(header_md_path),
                                    config={"mime_type": "text/markdown"}
                                )
                            except Exception:
                                uploaded_refs[k] = None

                        file_ref = uploaded_refs.get(k)
                        contents = ([file_ref] if file_ref else []) + batch_images + [batch_prompt]

                        response = _generate_with_thinking(
                            client=client,
                            model=m,
                            contents=contents,
                            system_instruction=system_instruction,
                            response_schema=BatchCardPayload,
                            temperature=0.25,
                            thinking_budget=4096
                        )
                        if response and response.text:
                            if "lite" not in m:
                                preferred_model = m
                            break
                    except Exception as e:
                        last_err = e
                        err_str = str(e)
                        if "404" in err_str or "NOT_FOUND" in err_str:
                            dead_models.add(m)
                            break
                        elif "503" in err_str or "UNAVAILABLE" in err_str or "timeout" in err_str.lower() or "timed out" in err_str.lower():
                            # 503 or timeout -> immediately switch to next model tier
                            model_503 = True
                            break
                        elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            # Quota reached on this key -> try next key in pool
                            continue
                        else:
                            break
                if response and response.text:
                    break
                if m_idx + 1 < len(candidate_models) and progress_callback:
                    next_m = candidate_models[m_idx + 1]
                    progress_callback(
                        b_idx + 1,
                        num_batches,
                        f"Model {m} busy/unavailable, failing over to {next_m} for Slides {start_slide}–{end_slide}..."
                    )
                if model_503:
                    continue

            if response and response.text:
                parsed = _safe_parse_json(response.text)
                batch_notes = parsed.get("notes", [])
                for n in batch_notes:
                    s_num = n.get("slide_number")
                    if not isinstance(s_num, int) or s_num < start_slide or s_num > end_slide:
                        n["slide_number"] = start_slide
                # Strip any <img src="..."> that is not in the whitelisted batch figures
                _sanitize_note_extra_images(batch_notes, set(batch_available_figures))
                # Deterministic stable sort by slide_number within the batch
                batch_notes.sort(key=lambda n: int(n.get("slide_number") or start_slide))
                all_notes.extend(batch_notes)
            else:
                print(f"Warning: Batch {b_idx + 1} generation encountered error: {last_err}")
    finally:
        for k, ref in uploaded_refs.items():
            if ref is not None:
                try:
                    _create_genai_client(k, timeout_ms=15_000).files.delete(name=ref.name)
                except Exception:
                    pass

    if not all_notes and last_err:
        raise RuntimeError(f"Card generation failed: {last_err}")

    # Guarantee final deck-wide chronological slide ordering
    all_notes.sort(key=lambda n: int(n.get("slide_number") or 9999))

    # Only include media files that are actually referenced in the generated notes
    img_src_re = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\']', re.IGNORECASE)
    for n in all_notes:
        for fname in img_src_re.findall(n.get("extra", "")):
            if fname in figure_path_by_name:
                used_media_files.add(figure_path_by_name[fname])

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


FOOTER_START_MARKER = "<!-- ANKI_STUDIO_FOOTER_START -->"
FOOTER_END_MARKER = "<!-- ANKI_STUDIO_FOOTER_END -->"


def get_study_guide_id(course_code: str, session_num: str) -> str:
    """Returns canonical study guide identifier (e.g. 'BPK207_Session_2')."""
    clean_course = re.sub(r'[^A-Za-z0-9]', '', course_code).upper() or "COURSE"
    clean_session = re.sub(r'[^A-Za-z0-9_-]', '', str(session_num)) or "1"
    return f"{clean_course}_Session_{clean_session}"


def clean_card_text_for_prompt(raw_text: str) -> str:
    """Strips Anki cloze brackets and HTML tags to yield clean, readable text for a Gemini prompt."""
    if not raw_text:
        return ""
    # Replace {{c1::answer::hint}} or {{c1::answer}} with answer
    text = re.sub(r'\{\{c\d+::(.*?)(?:::[^}]*)?\}\}', r'\1', raw_text)
    # Replace <br> with space
    text = re.sub(r'<br\s*/?>', ' ', text, flags=re.IGNORECASE)
    # Remove remaining HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Unescape HTML entities and normalize whitespace
    text = html.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def strip_card_footer(extra_html: str) -> str:
    """Removes the auto-generated Anki Studio footer from a card's extra field if present."""
    if not extra_html:
        return ""
    pattern = re.compile(
        re.escape(FOOTER_START_MARKER) + r'.*?' + re.escape(FOOTER_END_MARKER),
        re.DOTALL
    )
    cleaned = pattern.sub('', extra_html)
    return cleaned.strip()


def build_ask_gemini_url(
    front_text: str,
    extra_text: str = "",
    course_code: str = "Course",
    session_num: str = "1"
) -> str:
    """
    Builds a pre-filled Google Search AI Mode (udm=50) URL that immediately explains
    the specific flashcard concept in detail.
    """
    clean_front = clean_card_text_for_prompt(front_text)
    clean_extra = clean_card_text_for_prompt(strip_card_footer(extra_text))

    prompt = (
        f"I am studying {course_code} (Session/Chapter {session_num}). "
        f"Please explain this flashcard concept in detail, including the underlying mechanism, "
        f"how the components relate, and key exam takeaways: \"{clean_front}\""
    )
    if clean_extra and len(clean_extra) < 180:
        prompt += f" (Context: {clean_extra})"

    if len(prompt) > 750:
        prompt = prompt[:747] + '..."'

    return f"https://www.google.com/search?udm=50&q={urllib.parse.quote_plus(prompt)}"


def build_study_guide_url(
    course_code: str,
    session_num: str,
    app_base_url: str = "https://anki.maranica.com/"
) -> str:
    """Builds the deep-link URL to the hosted Supplementary Study Guide inside Anki Flashcard Studio."""
    guide_id = get_study_guide_id(course_code, session_num)
    base = app_base_url.rstrip("/")
    return f"{base}/?guide={urllib.parse.quote(guide_id)}"


def build_card_footer_html(
    front_text: str,
    extra_text: str,
    course_code: str,
    session_num: str,
    app_base_url: str = "https://anki.maranica.com/"
) -> str:
    """Generates the compact HTML footer bar with 'Ask Gemini' and 'Session Study Guide' links."""
    ask_url = html.escape(build_ask_gemini_url(front_text, extra_text, course_code, session_num), quote=True)
    guide_url = html.escape(build_study_guide_url(course_code, session_num, app_base_url), quote=True)

    footer_inner = (
        f'<div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(128,128,128,0.25);'
        f'font-size:0.85em;line-height:1.4;">'
        f'<a href="{ask_url}" target="_blank" rel="noopener noreferrer" '
        f'style="color:#1a73e8;text-decoration:none;font-weight:600;margin-right:10px;">'
        f'💬 Ask Gemini</a>'
        f'<span style="color:#9aa0a6;margin-right:10px;">•</span>'
        f'<a href="{guide_url}" target="_blank" rel="noopener noreferrer" '
        f'style="color:#1a73e8;text-decoration:none;font-weight:600;">'
        f'📚 Session Study Guide</a>'
        f'</div>'
    )
    return f"{FOOTER_START_MARKER}{footer_inner}{FOOTER_END_MARKER}"


def attach_card_footer(
    front_text: str,
    extra_html: str,
    course_code: str,
    session_num: str,
    app_base_url: str = "https://anki.maranica.com/"
) -> str:
    """Idempotently attaches the fresh 'Ask Gemini' & 'Session Study Guide' footer to a card's extra field."""
    clean_extra = strip_card_footer(extra_html)
    footer = build_card_footer_html(front_text, clean_extra, course_code, session_num, app_base_url)
    if clean_extra:
        return f"{clean_extra}\n{footer}"
    return footer


def attach_footers_to_notes(
    notes: List[Dict[str, str]],
    course_code: str,
    session_num: str,
    app_base_url: str = "https://anki.maranica.com/"
) -> List[Dict[str, str]]:
    """Returns a copy of notes with the 'Ask Gemini' and 'Session Study Guide' footer embedded in extra."""
    enriched = []
    for n in notes:
        front = n.get("text", "")
        raw_extra = n.get("extra", "")
        new_extra = attach_card_footer(front, raw_extra, course_code, session_num, app_base_url)
        item = dict(n)
        item["extra"] = new_extra
        enriched.append(item)
    return enriched


def _encode_image_to_data_uri(img_path: str) -> str:
    """Encodes a local image file into a self-contained base64 data URI."""
    if not img_path or not os.path.exists(img_path):
        return ""
    try:
        mime, _ = mimetypes.guess_type(img_path)
        if not mime:
            mime = "image/png"
        raw = Path(img_path).read_bytes()
        b64 = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


def render_study_guide_markdown(guide_data: Dict[str, Any]) -> str:
    """Converts a StudyGuide dictionary into clean Markdown text."""
    lines = [
        f"# 📚 {guide_data.get('title', 'Supplementary Study Guide')}",
        f"**Course:** {guide_data.get('course_code', '')} • **Session/Chapter:** {guide_data.get('session_num', '')}",
        "",
        "## 🎯 Executive Summary",
        guide_data.get("executive_summary", ""),
        ""
    ]
    for sec in guide_data.get("sections", []):
        lines.append("---")
        lines.append(f"## {sec.get('heading', '')}")
        lines.append("")
        lines.append(sec.get("content_markdown", ""))
        lines.append("")
        if sec.get("figure_filename"):
            lines.append(f"> 🖼️ **Referenced Slide Figure (`{sec['figure_filename']}`):** {sec.get('figure_caption', '')}")
            lines.append("")
        takeaways = sec.get("exam_takeaways", [])
        if takeaways:
            lines.append("### ⚡ High-Yield Exam Takeaways")
            for t in takeaways:
                lines.append(f"- {t}")
            lines.append("")
    return "\n".join(lines)


def render_study_guide_html(guide_data: Dict[str, Any], app_base_url: str = "https://anki.maranica.com/") -> str:
    """
    Renders a StudyGuide dictionary into a self-contained, responsive HTML document
    with embedded base64 slide diagrams.
    """
    title = html.escape(guide_data.get("title", "Supplementary Study Guide"))
    course = html.escape(guide_data.get("course_code", ""))
    session = html.escape(str(guide_data.get("session_num", "")))
    exec_sum = html.escape(guide_data.get("executive_summary", "")).replace("\n", "<br>")

    def _md_to_basic_html(md_text: str) -> str:
        """Lightweight markdown-to-HTML converter for paragraphs, bold, lists, and tables."""
        if not md_text:
            return ""
        text = html.escape(md_text)
        # Bold & Italic
        text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)

        out_lines = []
        in_list = False
        in_table = False
        table_header_done = False

        for line in text.splitlines():
            stripped = line.strip()
            # Table rows
            if stripped.startswith("|") and stripped.endswith("|") and len(stripped) > 2:
                if in_list:
                    out_lines.append("</ul>")
                    in_list = False
                cells = [c.strip() for c in stripped.strip("|").split("|")]
                # Skip markdown separator row |---|---|
                if all(re.match(r'^:?-{2,}:?$', c) for c in cells if c):
                    continue
                if not in_table:
                    out_lines.append("<table>")
                    in_table = True
                    table_header_done = False
                if not table_header_done:
                    out_lines.append("<thead><tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr></thead><tbody>")
                    table_header_done = True
                else:
                    out_lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
                continue
            else:
                if in_table:
                    out_lines.append("</tbody></table>")
                    in_table = False
                    table_header_done = False

            if stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("• "):
                if not in_list:
                    out_lines.append("<ul>")
                    in_list = True
                out_lines.append(f"<li>{stripped[2:].strip()}</li>")
            else:
                if in_list:
                    out_lines.append("</ul>")
                    in_list = False
                if stripped.startswith("#### "):
                    out_lines.append(f"<h4>{stripped[5:]}</h4>")
                elif stripped.startswith("### "):
                    out_lines.append(f"<h4>{stripped[4:]}</h4>")
                elif stripped.startswith("## "):
                    out_lines.append(f"<h3>{stripped[3:]}</h3>")
                elif stripped == "":
                    out_lines.append("<br>")
                else:
                    out_lines.append(f"<p>{stripped}</p>")
        if in_list:
            out_lines.append("</ul>")
        if in_table:
            out_lines.append("</tbody></table>")
        return "\n".join(out_lines)

    sections_html = []
    for sec in guide_data.get("sections", []):
        sec_heading = html.escape(sec.get("heading", ""))
        sec_body = _md_to_basic_html(sec.get("content_markdown", ""))
        fig_uri = sec.get("figure_data_uri", "")
        fig_caption = html.escape(sec.get("figure_caption", ""))
        fig_name = html.escape(sec.get("figure_filename", ""))

        fig_block = ""
        if fig_uri:
            fig_block = f"""
            <div class="figure-box">
                <img src="{fig_uri}" alt="{fig_name}" />
                <div class="figure-caption"><strong>🖼️ Diagram Walkthrough ({fig_name}):</strong> {fig_caption}</div>
            </div>
            """

        takeaways = sec.get("exam_takeaways", [])
        takeaways_block = ""
        if takeaways:
            items_html = "".join(f"<li>{_md_to_basic_html(t).replace('<p>', '').replace('</p>', '')}</li>" for t in takeaways)
            takeaways_block = f"""
            <div class="takeaways-box">
                <div class="takeaways-title">⚡ High-Yield Exam Takeaways & Common Traps</div>
                <ul>{items_html}</ul>
            </div>
            """

        sections_html.append(f"""
        <section class="guide-section">
            <h2>{sec_heading}</h2>
            <div class="sec-content">{sec_body}</div>
            {fig_block}
            {takeaways_block}
        </section>
        """)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title} — Anki Flashcard Studio</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            color: #202124;
            background-color: #f8f9fa;
            margin: 0;
            padding: 24px 16px;
            line-height: 1.6;
        }}
        .container {{
            max-width: 900px;
            margin: 0 auto;
            background: #ffffff;
            padding: 36px 40px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.06);
        }}
        .top-bar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            font-size: 0.9rem;
        }}
        .top-bar a {{
            color: #1a73e8;
            text-decoration: none;
            font-weight: 600;
        }}
        h1 {{
            color: #1E88E5;
            font-size: 1.85rem;
            margin-top: 0;
            margin-bottom: 6px;
        }}
        .meta {{
            color: #5f6368;
            font-size: 0.95rem;
            margin-bottom: 24px;
        }}
        .exec-summary {{
            background-color: #e8f0fe;
            border-left: 4px solid #1a73e8;
            padding: 16px 20px;
            border-radius: 6px;
            margin-bottom: 28px;
        }}
        .exec-summary-title {{
            font-weight: 700;
            color: #174ea6;
            margin-bottom: 6px;
        }}
        .guide-section {{
            border-top: 1px solid #e1e5ea;
            padding-top: 24px;
            margin-top: 24px;
        }}
        .guide-section h2 {{
            color: #202124;
            font-size: 1.35rem;
            margin-top: 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 14px 0;
            font-size: 0.92rem;
        }}
        th, td {{
            border: 1px solid #dadce0;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background-color: #f1f3f4;
            font-weight: 600;
        }}
        .figure-box {{
            background: #f8f9fa;
            border: 1px solid #dadce0;
            border-radius: 8px;
            padding: 16px;
            margin: 18px 0;
            text-align: center;
        }}
        .figure-box img {{
            max-width: 100%;
            max-height: 420px;
            border-radius: 4px;
        }}
        .figure-caption {{
            margin-top: 10px;
            font-size: 0.9rem;
            color: #3c4043;
            text-align: left;
        }}
        .takeaways-box {{
            background: #fef7e0;
            border-left: 4px solid #f9ab00;
            padding: 14px 18px;
            border-radius: 6px;
            margin-top: 16px;
        }}
        .takeaways-title {{
            font-weight: 700;
            color: #b06000;
            margin-bottom: 6px;
        }}
        code {{
            background: #f1f3f4;
            padding: 2px 5px;
            border-radius: 4px;
            font-size: 0.9em;
        }}
        @media (max-width: 600px) {{
            .container {{ padding: 20px 16px; }}
            h1 {{ font-size: 1.45rem; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <span>📇 <strong>Anki Flashcard Studio</strong> • Supplementary Study Guide</span>
            <a href="{html.escape(app_base_url, quote=True)}">⬅️ Open Studio</a>
        </div>
        <h1>📚 {title}</h1>
        <div class="meta"><strong>Course:</strong> {course} &nbsp;•&nbsp; <strong>Session / Chapter:</strong> {session}</div>
        <div class="exec-summary">
            <div class="exec-summary-title">🎯 Big-Picture Synthesis</div>
            <div>{exec_sum}</div>
        </div>
        {"".join(sections_html)}
    </div>
</body>
</html>"""


def render_study_guide_pdf(
    guide_data: Dict[str, Any],
    pdf_path: Path,
    app_base_url: str = "https://anki.maranica.com/"
) -> Path:
    """
    Renders the Study Guide (including embedded base64 slide diagrams and tables)
    directly to a multi-page Letter PDF using PyMuPDF Story.
    """
    html_str = render_study_guide_html(guide_data, app_base_url=app_base_url)
    # Strip multi-byte color emojis that standard PDF fonts lack
    for emoji_char in ["📇 ", "⬅️ ", "📚 ", "🎯 ", "🖼️ ", "⚡ "]:
        html_str = html_str.replace(emoji_char, "")

    mediabox = pymupdf.paper_rect("letter")
    where = mediabox + (36, 36, -36, -36)
    story = pymupdf.Story(html=html_str)
    writer = pymupdf.DocumentWriter(str(pdf_path))
    more = True
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    return pdf_path


def save_study_guide_files(
    guide_data: Dict[str, Any],
    base_dir: Path,
    app_base_url: str = "https://anki.maranica.com/"
) -> Dict[str, Path]:
    """Saves the Study Guide as JSON, self-contained HTML, PDF, and Markdown in extracted/study_guides/."""
    guides_dir = base_dir / "extracted" / "study_guides"
    guides_dir.mkdir(parents=True, exist_ok=True)

    guide_id = guide_data.get("guide_id") or get_study_guide_id(
        guide_data.get("course_code", "Course"),
        guide_data.get("session_num", "1")
    )
    guide_data["guide_id"] = guide_id

    json_path = guides_dir / f"{guide_id}_guide.json"
    html_path = guides_dir / f"{guide_id}_Study_Guide.html"
    pdf_path = guides_dir / f"{guide_id}_Study_Guide.pdf"
    md_path = guides_dir / f"{guide_id}_Study_Guide.md"

    json_path.write_text(json.dumps(guide_data, indent=2), encoding="utf-8")
    html_path.write_text(render_study_guide_html(guide_data, app_base_url), encoding="utf-8")
    md_path.write_text(render_study_guide_markdown(guide_data), encoding="utf-8")
    try:
        render_study_guide_pdf(guide_data, pdf_path, app_base_url=app_base_url)
    except Exception as e:
        print(f"Warning: could not render PDF for study guide: {e}")

    return {
        "json_path": json_path,
        "html_path": html_path,
        "pdf_path": pdf_path,
        "md_path": md_path
    }



def load_local_study_guide(guide_id: str, base_dir: Path) -> Optional[Dict[str, Any]]:
    """Loads a saved Study Guide JSON by its guide_id if present on disk."""
    clean_id = re.sub(r'[^A-Za-z0-9_-]', '', guide_id)
    json_path = base_dir / "extracted" / "study_guides" / f"{clean_id}_guide.json"
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def delete_local_study_guide(guide_id: str, base_dir: Path) -> List[str]:
    """Deletes all local study guide files for a given guide_id."""
    clean_id = re.sub(r'[^A-Za-z0-9_-]', '', guide_id)
    if not clean_id:
        return []
    guides_dir = base_dir / "extracted" / "study_guides"
    if not guides_dir.exists():
        return []

    deleted = []
    candidates = [
        f"{clean_id}_guide.json",
        f"{clean_id}_Study_Guide.html",
        f"{clean_id}_Study_Guide.pdf",
        f"{clean_id}_Study_Guide.md",
        f"{clean_id}_header.md"
    ]
    for c in candidates:
        p = guides_dir / c
        if p.exists():
            try:
                p.unlink()
                deleted.append(c)
            except Exception as e:
                print(f"Could not delete {p}: {e}")
    return deleted


def generate_study_guide(
    slides_data: List[Dict[str, Any]],
    course_code: str,
    session_num: str,
    custom_focus: str,
    base_dir: Path,
    api_key: Optional[str] = None,
    api_keys_pool: Optional[List[str]] = None,
    app_base_url: str = "https://anki.maranica.com/",
    progress_callback: Optional[Callable[..., None]] = None
) -> Dict[str, Any]:
    """
    Generates an illustrated, multimodal Supplementary Study Guide & Concept Explainer:
    1. Builds a consolidated `<guide_id>_header.md` file (course rules, sub-section roadmap,
       figure inventory, and slide text) and uploads it once to the Gemini File API (`file_uri`).
    2. Processes the lecture in batches of 3–4 detected sub-sections using full Flash models,
       passing the lightweight `file_uri` reference alongside native slide snapshots.
    3. Merges all sections, embeds extracted slide figures as base64 data URIs, and saves JSON/HTML/MD.
    """
    raw_keys = (api_keys_pool or []) + ([api_key] if api_key else [])
    if not raw_keys:
        env_key = os.getenv("GEMINI_API_KEY")
        if env_key:
            raw_keys.append(env_key)

    active_keys = []
    seen = set()
    for k in raw_keys:
        if not k:
            continue
        clean = k.strip()
        if not (clean.startswith("AQ.") or clean.startswith("AIzaSy")):
            clean = f"AQ.{clean}"
        if clean not in seen:
            seen.add(clean)
            active_keys.append(clean)

    if not active_keys:
        raise ValueError("No Gemini API key available. Please provide an API key in your Google Account profile or Settings.")

    def _notify(batch_idx: int, total_batches: int, msg: str):
        if not progress_callback:
            return
        try:
            progress_callback(batch_idx, total_batches, msg)
        except TypeError:
            progress_callback(msg)

    course_rules = get_course_rules(course_code, base_dir)
    guide_id = get_study_guide_id(course_code, session_num)

    # 1. Build figure inventory and consolidated Header Reference Markdown (.md)
    header_md_path, figure_map, _ = _build_lecture_header_md(
        slides_data=slides_data,
        course_code=course_code,
        session_num=str(session_num),
        course_rules=course_rules,
        base_dir=base_dir
    )
    available_figs_str = ", ".join(figure_map.keys()) if figure_map else "None"

    # Group slides into batches of 3–4 detected sub-sections
    batches = _group_slides_by_subsections(slides_data, max_subsections_per_batch=3, max_slides_per_batch=5)
    num_batches = max(1, len(batches))

    system_instruction = f"""You are a master university professor and study guide author for {course_code} (Session/Chapter {session_num}).
Your task is to create an illustrated, exam-focused Supplementary Study Guide & Concept Explainer that makes complex mechanisms intuitive, rigorous, and memorable.

### STUDY GUIDE MANDATES:
1. **Intuitive Causal Explanations**: Explain *how* and *why* each physiological, anatomical, or biochemical mechanism works step-by-step (e.g. stimulus → receptor transduction → afferent coding → central integration → motor/metabolic output).
2. **Comparison Tables & Contrasts**: Use Markdown tables or structured bullet comparisons to contrast easily confused pairs (e.g., Utricle vs. Saccule, Muscle Spindle Ia/II vs. GTO Ib, ΔG′° vs. ΔG′).
3. **Diagram Integration**: Match relevant extracted slide figures from `{available_figs_str}` into `figure_filename` and write a clear `figure_caption` walking the student through what to observe in the diagram.
4. **High-Yield Exam Takeaways**: Conclude every section with 2–4 concrete exam pearls or common exam traps.
5. **Formatting**: Use clean GitHub-flavored Markdown and Unicode symbols (ΔG′°, α, β, γ, ⇌, →, ⁺, ²⁺) instead of LaTeX backslashes.
"""

    uploaded_refs: Dict[str, Any] = {}
    dead_models: set = set()
    preferred_model: Optional[str] = None
    guide_title = f"{course_code} — Session {session_num} Study Guide"
    executive_summary = ""
    all_sections = []
    last_err = None

    try:
        for b_idx, batch in enumerate(batches):
            start_s = batch["start_slide"]
            end_s = batch["end_slide"]
            sub_secs = batch["subsections"]

            if sub_secs:
                sec_label = ", ".join(sub_secs[:3])
                msg = f"Batch {b_idx + 1}/{num_batches}: Generating Study Guide for Sub-sections {sec_label} (Slides {start_s}–{end_s})..."
            else:
                msg = f"Batch {b_idx + 1}/{num_batches}: Generating Study Guide for Slides {start_s}–{end_s}..."
            _notify(b_idx + 1, num_batches, msg)

            # Collect native 150 DPI snapshots for this batch's slides (up to 3 slides)
            batch_thumbs = []
            batch_figs = []
            for s in batch["slides"]:
                for fp in s.get("figure_paths", []):
                    batch_figs.append(Path(fp).name)
                if len(batch_thumbs) < 3:
                    snap = s.get("snapshot_path")
                    if snap and os.path.exists(snap):
                        try:
                            with Image.open(snap) as im:
                                im.load()
                                batch_thumbs.append(im.copy())
                        except Exception:
                            pass

            focus_clause = (
                f"\nStudent Custom Focus Request: {custom_focus}"
                if custom_focus and custom_focus.strip()
                else ""
            )
            subsec_clause = (
                f"Detected Sub-Sections in this batch: {', '.join(sub_secs)}"
                if sub_secs
                else f"Slides in this batch: {start_s} to {end_s}"
            )
            figs_clause = (
                f"Extracted figures on these slides (use in `figure_filename`): {', '.join(batch_figs)}"
                if batch_figs
                else f"Available lecture figures: {available_figs_str}"
            )

            batch_prompt = (
                f"Referencing the uploaded Lecture Reference Header (.md), generate the in-depth Study Guide sections "
                f"specifically covering Slides {start_s}–{end_s}.\n"
                f"- {subsec_clause}\n"
                f"- {figs_clause}"
                f"{focus_clause}\n"
                f"Write 2 to 3 thorough, exam-grade `sections` covering all mechanisms and concepts in Slides {start_s}–{end_s}."
            )

            response = None
            candidate_models = _ordered_candidate_models(preferred_model, dead_models)

            for m_idx, m in enumerate(candidate_models):
                model_503 = False
                for k in active_keys:
                    client = _create_genai_client(k, timeout_ms=60_000)
                    try:
                        # Upload the .md header file once per API key and reuse its HTTPS file_uri reference
                        if k not in uploaded_refs and header_md_path and header_md_path.exists():
                            try:
                                uploaded_refs[k] = client.files.upload(
                                    file=str(header_md_path),
                                    config={"mime_type": "text/markdown"}
                                )
                            except Exception:
                                uploaded_refs[k] = None
                        file_ref = uploaded_refs.get(k)
                        contents = ([file_ref] if file_ref else []) + batch_thumbs + [batch_prompt]

                        response = _generate_with_thinking(
                            client=client,
                            model=m,
                            contents=contents,
                            system_instruction=system_instruction,
                            response_schema=StudyGuidePayload,
                            temperature=0.3,
                            thinking_budget=4096
                        )
                        if response and response.text:
                            if "lite" not in m:
                                preferred_model = m
                            break
                    except Exception as e:
                        last_err = e
                        err_str = str(e)
                        if "404" in err_str or "NOT_FOUND" in err_str:
                            dead_models.add(m)
                            break
                        elif "503" in err_str or "UNAVAILABLE" in err_str or "timeout" in err_str.lower() or "timed out" in err_str.lower():
                            model_503 = True
                            break
                        elif "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                            continue
                        else:
                            break
                if response and response.text:
                    break
                if m_idx + 1 < len(candidate_models):
                    next_m = candidate_models[m_idx + 1]
                    _notify(
                        b_idx + 1,
                        num_batches,
                        f"Batch {b_idx + 1}/{num_batches}: Model {m} busy, switching to {next_m}..."
                    )
                if model_503:
                    continue

            if response and response.text:
                parsed = _safe_parse_json(response.text)
                if b_idx == 0:
                    guide_title = parsed.get("title") or guide_title
                    executive_summary = parsed.get("executive_summary") or executive_summary
                batch_sections = parsed.get("sections", [])
                all_sections.extend(batch_sections)
            else:
                print(f"Warning: Study Guide batch {b_idx + 1} encountered error: {last_err}")
    finally:
        # Clean up uploaded remote header files from Gemini File API
        for k, ref in uploaded_refs.items():
            if ref is not None:
                try:
                    genai.Client(api_key=k).files.delete(name=ref.name)
                except Exception:
                    pass

    if not all_sections:
        raise RuntimeError(f"Study Guide generation failed: {last_err}")

    # Enrich sections with base64 figure data URIs for self-contained persistence
    enriched_sections = []
    for s_idx, sec in enumerate(all_sections):
        # Ensure clean sequential numbering if multiple batches generated headings
        raw_heading = re.sub(r'^\d+[\.\)]\s*', '', sec.get("heading", "").strip())
        sec["heading"] = f"{s_idx + 1}. {raw_heading}" if raw_heading else f"Section {s_idx + 1}"

        fig_name = sec.get("figure_filename", "").strip()
        fig_path = figure_map.get(fig_name, "")
        if not fig_path and fig_name:
            cand = base_dir / "extracted" / guide_id / "images" / fig_name
            if cand.exists():
                fig_path = str(cand)
        sec["figure_path"] = fig_path if (fig_path and os.path.exists(fig_path)) else ""
        sec["figure_data_uri"] = _encode_image_to_data_uri(sec["figure_path"]) if sec["figure_path"] else ""
        enriched_sections.append(sec)

    guide_data = {
        "guide_id": guide_id,
        "title": guide_title,
        "course_code": course_code,
        "session_num": str(session_num),
        "executive_summary": executive_summary,
        "sections": enriched_sections,
        "created_at": int(time.time())
    }

    save_study_guide_files(guide_data, base_dir, app_base_url=app_base_url)
    return guide_data


