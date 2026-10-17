---
name: anki-card-generator
description: >-
  Generates, refines, and syncs Anki flashcard decks (.apkg) from lecture PDFs or Google Drive links across multiple university courses (such as MBB 321). Activate this skill whenever the user provides lecture slides, a Google Drive link to course material, asks to generate or update Anki flashcards, or provides feedback on flashcard formatting for any course.
---

# Multi-Course Anki Flashcard Generator Skill

This skill provides a streamlined, end-to-end workflow for turning lecture slides (including handwritten annotations and diagrams) into high-yield Anki Cloze flashcards (`.apkg`) and syncing them directly with Google Drive.

---

## 1. File Naming & Deck Resolution Convention

- **Course Detection:** Always infer the course code (e.g., `MBB321` / `MBB 321`) and session number (e.g., `Session 13`) from the input filename or user prompt.
- **Output `.apkg` Convention:**
  - Look in the shared Google Drive folder (`1JD0rlrkJIFJ6n4hv5Mxc9zLSP-UEZJja`) and local workspace for an existing `.apkg` file matching `<COURSE_CODE>*.apkg` (e.g., `MBB321*.apkg` or `MBB 321*.apkg`).
  - **If it exists:** Download and update that exact `.apkg` file in place.
  - **If it does not exist:** Automatically generate a new `.apkg` file named `<COURSE_CODE> - Flashcards.apkg` (e.g., `MBB321 - Flashcards.apkg`) and upload it to the shared Google Drive folder.

---

## 2. Progressive Course Profiles (`references/`)

Each course has its own pedagogical style, visual/image requirements, and formatting rules stored in `references/<course-code>.md`:
- **Existing Courses:**
  - **MBB 321 (Intermediary Metabolism):** Read [references/mbb-321.md](./references/mbb-321.md) before generating cards for `MBB 321`.
- **New Courses:**
  - If the user provides material for a course that does not yet have a file in `references/`, check [references/_course_template.md](./references/_course_template.md), ask the user (or infer from a sample deck) whether the course is equation-focused, text-focused, or diagram/image-heavy, and create `references/<course-code>.md`.
- **Continuous Feedback Loop:**
  - Whenever Mara or the user gives feedback on card style, cloze grouping, image usage, or level of detail, **immediately update the corresponding `references/<course-code>.md` file** so the preference is permanently saved for all future sessions.

---

## 3. Universal Spaced-Repetition Quality Rules

1. **Minimum Information Principle (Atomicity):**
   - Never cloze an entire multi-part sentence or full equation as a single giant blank.
   - Group clozes logically (`c1`, `c2`, `c3`) so each card tests one cohesive concept.
2. **No Trivial Binary Clozes:**
   - Never cloze `{{c1::high}}` vs. `low` or `{{c1::yes}}` vs. `no`. Cloze the physiological outcome, mechanism, or molecular player instead.
3. **Cue Lists Clearly:**
   - When testing a list of items, include the count in the prompt (e.g., *"The 3 biological roles of X:"*) so the learner knows what is expected.
4. **Always Populate the `extra` Field:**
   - Use the `extra` field on every note to provide brief high-yield context, physiological rationale, or an embedded slide diagram (`<img src="...">`).

---

## 4. Two-Step Automated Execution Workflow

To minimize tool calls and avoid unnecessary user approval prompts, **do not write ad-hoc Python scripts**. Always use the pre-built CLI tool [scripts/anki_cli.py](./scripts/anki_cli.py):

### Step 1: Inspect the Source PDF & Check Deck Status
Run the `inspect` command on the Google Drive link/ID or local PDF path (add `--extract-images` if the course profile requires slide figures/diagrams):
- **Linux / macOS:**
  ```bash
  .venv/bin/python .agents/skills/anki-card-generator/scripts/anki_cli.py inspect "<DRIVE_URL_OR_ID>"
  ```
- **Windows (PowerShell):**
  ```powershell
  .\.venv\Scripts\python.exe .agents/skills/anki-card-generator/scripts/anki_cli.py inspect "<DRIVE_URL_OR_ID>"
  ```
Then use `view_file` to read the generated `extracted/<COURSE>_Session_<N>/extracted_slides.md` file and the course profile in `references/<course>.md`.

### Step 2: Write `cards.json` and Sync to Google Drive
1. Write the generated notes to `extracted/<COURSE>_Session_<N>/cards.json` using `write_to_file`:
   ```json
   {
     "course_display": "MBB 321",
     "course_compact": "MBB321",
     "session": "13",
     "tag": "#MBB321::Session::13",
     "deck_name": "MBB 321 - Intermediary Metabolism",
     "media_files": [],
     "notes": [
       {
         "text": "Front text with {{c1::cloze}} deletions",
         "extra": "Concise high-yield explanation or <img src=\"...\">"
       }
     ]
   }
   ```
2. Run the `sync` command to build/update the `.apkg` and push it to the shared Google Drive folder:
   - **Linux / macOS:**
     ```bash
     .venv/bin/python .agents/skills/anki-card-generator/scripts/anki_cli.py sync "extracted/<COURSE>_Session_<N>/cards.json"
     ```
   - **Windows (PowerShell):**
     ```powershell
     .\.venv\Scripts\python.exe .agents/skills/anki-card-generator/scripts/anki_cli.py sync "extracted/<COURSE>_Session_<N>/cards.json"
     ```
3. Report the summary of generated cards, total deck counts, and the Google Drive link to the user.
