# Project Rules — Anki Flashcard Studio

## Mandatory UI Verification Before Deployment
1. **Never push or deploy UI changes (`app.py`, CSS, layout) without first taking a live screenshot of the local running server (`http://localhost:8501`) and visually inspecting it using `view_file`.**
2. Check every screenshot for:
   - Column widths and proportions (ensure no CSS selector like `:first-of-type` accidentally targets nested `st.columns` inside forms or tabs!).
   - Proper positioning, height, and edge-alignment of navigation rails/bars.
   - Text or header truncation, button sizing, and spacing.
3. Only commit and `git push` after visual verification confirms the UI looks clean and proportional.
