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

## 3. Chronological Slide Sequencing & Image/Clarification-Only Extra Field Rule
- **Chronological Slide Sequence:** Generate cards in strict ascending slide order (`Slide 1`, then `Slide 2`, then `Slide 3`, etc.). Never jump back and forth between slides.
- **100% Testable Coverage Check:** Audit every slide so all testable material is directly tested inside `{{c1::...}}`/`{{c2::...}}`/`{{c3::...}}` clozes in `text`.
- **Image & Clarification-Only `extra`:** The `extra` field must ONLY contain the embedded slide diagram (`<img src="...">`) and/or a brief 1-sentence visual pointer or non-testable clarification. NEVER place testable subject matter in `extra`—if `extra` contains a testable fact, extract it out into a dedicated card on that slide!

---

## 4. Bidirectional Definition Testing Rule (Term ↔ Meaning)
When a card tests a definition, phenomenon, or core scientific concept, test both ways on the note:
- **`c1` (Term Recall):** `[Definition / Description] → [Term]`
- **`c2` (Definition / Meaning Recall):** `[Term] → [What it actually means/does]`
- **`c3` (Mechanistic Driver / Effector):** Key effector, organ, enzyme, or driver.
