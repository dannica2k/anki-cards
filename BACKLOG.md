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

---

## Queued / Upcoming Backlog

- [ ] **`BL-03` — Study Guide Library & Browser in Left Navigation Rail + Pre-Flashcard Generation**
  - Add a **📚 Study Guides** icon popover/drawer in the left Gmail-style navigation rail (`app.py`) to browse, open, or download previously generated Study Guides (`.html` / `.pdf`) across all courses (`MBB 321`, `BPK 207`, `BPK 305`) from Google Drive or local disk.
  - Allow generating a Supplementary Study Guide directly after auditing a lecture PDF, even before generating flashcards.

- [ ] **`BL-04` — Upgrade Flashcard Generation (`generate_cards_chunked`) with Sub-Section Batching & Gemini File API Header Reference**
  - Unify `generate_cards_chunked()` in `generator.py` with the `v1.4.2` Study Guide architecture: group slide batches by `3–4` detected sub-sections instead of fixed 5-page slices, and upload the lecture `<guide_id>_header.md` via `client.files.upload()` once so every flashcard batch has full-lecture context with minimal prompt overhead.

- [ ] **`BL-05` — Static HTTPS Serving (`/app/static/...`) for Instant Study Guide & PDF Links**
  - Enable Streamlit static file serving (`--server.enableStaticServing=true` in `Dockerfile`) and publish generated `.html`, `.pdf`, and `.md` study guides to `./static/` so `https://anki.maranica.com/app/static/<guide_id>.html` (and `.pdf`) resolve instantaneously on mobile/iPad without spinning up a Streamlit WebSocket session.

- [ ] **`BL-06` — Per-Card "✨ Refine / Spawn Follow-Up Card" Action in Review Mode**
  - Add a quick per-card action in the Review list (`app.py`) allowing the student to split a complex card, add a missing mechanism, or spawn a follow-up Cloze card on that specific concept.
