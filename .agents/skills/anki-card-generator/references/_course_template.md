# Course Profile Template: <COURSE_CODE> — <COURSE_TITLE>

Copy this file to `references/<course-code-lowercase>.md` when setting up a new course for Mara.

## 1. Course Metadata & Naming Conventions
- **Course Code:** `<COURSE_COMPACT>` (e.g., `BIO201`)
- **Course Title:** `<COURSE_TITLE>`
- **Target Deck File Pattern:** `<COURSE_COMPACT>*.apkg` (Default new: `<COURSE_COMPACT> - Flashcards.apkg`)
- **Deck Name inside Anki:** `<COURSE_DISPLAY> - <COURSE_TITLE>`
- **Tag Format:** `#<COURSE_COMPACT>::Session::<Session_Number>`
- **Shared Google Drive Folder ID:** `1JD0rlrkJIFJ6n4hv5Mxc9zLSP-UEZJja`

---

## 2. Modality & Card Design Preferences
- **Image / Diagram Usage:**
  - `[ ] Text/Equation Only` (Default for quantitative/pathway courses)
  - `[ ] Include Slide Figures in Extra Field` (Run `anki_cli.py inspect --extract-images` and embed `<img src="filename.png">` in `extra`)
  - `[ ] Image-First / Visual Identification` (Embed figure on the front of the card and test anatomical/structural labels)
- **Primary Focus Areas:**
  - List what exams in this course emphasize (e.g., *definitions, pathways, clinical correlations, anatomical structures, experimental techniques*).
- **Custom Formatting Rules & Feedback History:**
  - Record any specific formatting adjustments requested by Mara here so future sessions follow them automatically.

---

## 3. The "Support-Only" Extra Field Rule & Extra Extraction Principle
- **Support-Only Extra:** The `extra` field exists strictly to support the tested clozes (via diagram grounding `<img src="...">`, cross-referencing other cards, or a 1-sentence physiological/mechanistic rationale). It must NEVER introduce new, untested concepts or structures.
- **The Testability Axiom:** If a piece of information is testable on an exam, it MUST have its own active-recall Cloze card.
- **Extra Extraction Check:** Before finalizing `extra`, ask: *"Does this contain a key term, mechanism, or step that could be asked on an exam?"* If YES, extract it out into a dedicated card and keep `extra` strictly supportive!
