# MBB 321 Anki Flashcard Generation — Master Guiding Prompt

Use this prompt (or reference this file) whenever creating or overhauling Anki flashcards from MBB 321 (Intermediary Metabolism) lecture slides.

---

## 🎯 Role & Objective
Act as an expert biochemistry educator and spaced-repetition (Anki) designer. Your goal is to transform lecture slides (including instructor/student annotations) into high-yield, atomic, exam-ready **Cloze deletion** flashcards that test both **pathway mechanics** and **deep conceptual understanding** (thermodynamics, redox balance, regulation, and physiological rationale).

---

## 📐 Core Card Design Principles

### 1. Standardized Biochemical Reaction Format (The "3-Cloze Equation Rule")
Never test an entire reaction equation as a single massive blank (`{{c1::A + B -> C + D}}`), and never waste cards testing arbitrary step index numbers (`Step {{c2::6}}`).
Instead, write every biochemical reaction in **equation form** using a single note with up to **3 functional cloze groups**:
- **`c1` (Carbon Pathway):** Main carbon substrate(s) and product(s)
- **`c2` (Catalyst):** The enzyme name placed inside brackets over the arrow: `——[{{c2::Enzyme}}]——>`
- **`c3` (Energetics / Cofactors):** Energy carriers, coenzymes, and inorganic molecules (`ATP`, `ADP`, `NAD⁺`, `NADH + H⁺`, `FAD`, `FADH₂`, `Pi`, `CO₂`, `H₂O`)

**Template:**
```text
[Pathway Name] (Reaction/Step X):<br>{{c1::Substrate}} + {{c3::Cofactor/ATP}} ——[{{c2::Enzyme Name}}]——> {{c1::Product}} + {{c3::Byproduct/ADP/NADH}}
```
**Back Extra (`Extra` field):** Always populate the Extra field with concise high-yield context:
- Which phase of the pathway it belongs to
- Reaction type (e.g., *substrate-level phosphorylation*, *isomerization*, *aldol cleavage*, *oxidative decarboxylation*)
- Thermodynamic/regulatory status (e.g., *Irreversible, $\Delta G'^\circ \ll 0$, committed step, allosterically regulated by...*)

---

### 2. Deep Conceptual & Thermodynamic Coverage
University biochemistry exams test *why* pathways work, not just *what* the intermediates are. Always inspect the slides (and handwritten annotations!) for:
1. **Thermodynamics & Bioenergetics ($\Delta G'^\circ$):**
   - How endergonic reactions are driven forward (e.g., coupling to ATP hydrolysis, cleavage, or product depletion).
   - Which steps have large negative $\Delta G'^\circ$ (irreversible / regulatory control points) vs. near-equilibrium ($\Delta G \approx 0$) steps.
2. **Redox Balance & Electron Accounting:**
   - Track carbon oxidation state changes across reactions.
   - How coenzyme pools ($\text{NAD}^+/\text{NADH}$, $\text{NADP}^+/\text{NADPH}$, $\text{FAD}/\text{FADH}_2$) are consumed and regenerated across compartments.
3. **Net Stoichiometry & ATP Accounting:**
   - Create explicit cards for the **net balanced equation** of a pathway.
   - Distinguish between *ATP invested*, *ATP recovered*, and *net ATP payoff*.
4. **Physiological & Chemical Rationale ("Why" Questions):**
   - Why a chemical modification happens (e.g., *phosphate tagging prevents membrane diffusion, provides binding recognition, and conserves group transfer potential*).
   - Tissue-specific differences (e.g., *Liver vs. Muscle vs. Brain roles*).
5. **Pathway Intersections & Precursors:**
   - How intermediates branch into other pathways (e.g., amino acid synthesis, lipid backbones, nucleotide synthesis, PPP, gluconeogenesis, TCA).

---

### 3. Minimum Information Principle & Cloze Hygiene
- **Avoid Trivial Binary Clozes:** Never cloze words like `{{c1::high}}` vs `low` or `{{c1::yes}}` vs `no`. Instead, cloze the physiological outcome or mechanism.
- **Unbundle Long Lists:** If a card lists 4+ precursors or functions, either:
  - Group them with a clear numerical cue in the prompt (e.g., *"The 3 biological roles of X are..."* or *"4 non-carbohydrate precursors for gluconeogenesis:"*), OR
  - Split them into distinct functional clozes (`c1`, `c2`, `c3`) by category.
- **Consistent Tagging:** Tag all notes for a given lecture using the hierarchy:
  `#MBB321::Session::<Session_Number>`

---

## 🛠️ Automated Workflow Instructions (For Agent Execution)

When given a new session PDF or Google Drive link:
1. **Download Source & Current Deck:**
   - Use `.venv/bin/python gdrive_sync.py download <FILE_ID>` to pull the annotated lecture PDF and the latest `.apkg` deck.
2. **Extract All Text & Annotations:**
   - Use `pymupdf` (`fitz`) to extract both slide text blocks and handwritten/typed margin annotations (which often contain exam hints like *"Steps 6, 7, 10 have big $\Delta G$"* or *"no net oxidation"*).
3. **Audit Against Learning Objectives:**
   - Cross-check every Learning Objective slide against the generated cards to ensure 100% coverage.
4. **Package & Sync to Shared Folder:**
   - Update `collection.anki21b` (decompress with `zstandard`, update `notes` and `cards` tables in SQLite, recompress with `zstandard`), repackage `.apkg`, and upload/move directly to the shared Google Drive folder (`1JD0rlrkJIFJ6n4hv5Mxc9zLSP-UEZJja`).
