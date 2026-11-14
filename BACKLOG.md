# Project Backlog — Anki Flashcard Studio

This file is the single source of truth for features, enhancements, and bug fixes across all development machines.

---

## Completed Items

- [x] **`BL-01` — On-Demand Illustrated Supplementary Study Guide & Per-Card AI Tutor Links (`v1.4.0`–`v1.4.3`)**
  - Embedded `💬 Ask Gemini` (`https://www.google.com/search?udm=50&q=...`) and `📚 Session Study Guide` (`https://anki.maranica.com/?guide=<COURSE>_Session_<N>`) footer links in every exported Anki card's `Extra` field.
  - Built chunked multimodal Study Guide generator (`3–4` detected sub-sections per batch) using the Gemini File API (`client.files.upload`) to reference a consolidated `<guide_id>_header.md` context file across batches.
  - Added interactive Study Guide viewer (`?guide=...`), formatted Letter PDF export (`render_study_guide_pdf` via PyMuPDF `Story` + `DocumentWriter`), self-contained HTML export, and automatic Google Drive backup (`.json`, `.html`, `.pdf`).

- [x] **`BL-02` — Fix Google Sign-In Same-Tab Navigation & `Ctrl+F5` Session Persistence (`v1.4.4`)**
  - Replaced `st.link_button` (`target="_blank"`) with a same-tab (`target="_self"`) Sign-In button so Google OAuth completes in the active browser tab without spawning duplicate tabs.
  - Fixed `_load_cached_creds()` in `google_auth.py` where `Credentials.from_authorized_user_info()` threw `ValueError: missing fields refresh_token` on `F5` / `Ctrl+F5` reloads whenever Google returned an access token without a refresh token.
  - Preserved existing `refresh_token` across subsequent logins and kept `?sid=<sid>` synchronized on reload.

- [x] **`BL-04` — Upgrade Flashcard Generation (`generate_cards_chunked`) with Sub-Section Batching, Gemini File API Header Reference & Real-Time SSE Progress**
  - Unified `generate_cards_chunked()` in `generator.py` with sub-section batching (`_group_slides_by_subsections`), proportional per-batch card allocation (`_allocate_cards_across_batches`), and shared `<guide_id>_header.md` context uploaded via `client.files.upload()` while preserving full 150 DPI slide snapshots.
  - Added sticky working-model promotion and 404 dead-model pruning across `DEFAULT_MODELS_TO_TRY` (`gemini-3.8-flash` -> `gemini-3.7-flash` -> `gemini-3.5-flash` -> `gemini-3-flash-preview` -> `gemini-2.5-flash` -> `-lite` fallbacks).
  - Fixed HTMX SSE progress freeze at 10% (`hx-swap="innerHTML"` on `#sse-event-sink` and offloading `analyze_lecture_pdf` to background executor threads).

---

## Queued / Upcoming Backlog

- [ ] **`BL-03` — Study Guide Library & Browser in Left Navigation Rail + Pre-Flashcard Generation**
  - Add a **📚 Study Guides** icon popover/drawer in the left Gmail-style navigation rail (`app.py`) to browse, open, or download previously generated Study Guides (`.html` / `.pdf`) across all courses (`MBB 321`, `BPK 207`, `BPK 305`) from Google Drive or local disk.
  - Allow generating a Supplementary Study Guide directly after auditing a lecture PDF, even before generating flashcards.

- [ ] **`BL-05` — Static HTTPS Serving (`/app/static/...`) for Instant Study Guide & PDF Links**
  - Enable Streamlit static file serving (`--server.enableStaticServing=true` in `Dockerfile`) and publish generated `.html`, `.pdf`, and `.md` study guides to `./static/` so `https://anki.maranica.com/app/static/<guide_id>.html` (and `.pdf`) resolve instantaneously on mobile/iPad without spinning up a Streamlit WebSocket session.

- [ ] **`BL-06` — Per-Card "✨ Refine / Spawn Follow-Up Card" Action in Review Mode**
  - Add a quick per-card action in the Review list (`app.py`) allowing the student to split a complex card, add a missing mechanism, or spawn a follow-up Cloze card on that specific concept.
