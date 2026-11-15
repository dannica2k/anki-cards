# MBB 321 Anki Flashcard Generation — Master Guiding Prompt

Use this prompt (or reference this file) whenever creating or overhauling Anki flashcards from MBB 321 (Intermediary Metabolism) lecture slides.

---

## 🎯 Role & Objective
Act as an expert biochemistry educator and spaced-repetition (Anki) designer. Your goal is to transform lecture slides (including instructor/student annotations) into high-yield, atomic, exam-ready **Cloze deletion** flashcards that test both **pathway mechanics** and **deep conceptual understanding** (thermodynamics, redox balance, regulation, and physiological rationale), following strict chronological slide order.

---

## 📐 Core Card Design Principles

### 1. Standardized Biochemical Reaction Format (The "Equation Cloze Rule")
Never test an entire reaction equation as a single massive blank (`{{c1::A + B -> C + D}}`), and never waste cards testing arbitrary step index numbers (`Step {{c2::6}}`).
Instead, write every biochemical reaction in **equation form** using a single note with **2 or 3 coordinated functional cloze groups**:
- **`c1` (Carbon Pathway):** Main carbon substrate(s) and product(s)
- **`c2` (Catalyst):** The enzyme name placed inside brackets over the arrow: `——[{{c2::Enzyme}}]——>`
- **`c3` (Energetics / Cofactors):** Energy carriers, coenzymes, and inorganic molecules (`ATP`, `ADP`, `NAD⁺`, `NADH + H⁺`, `FAD`, `FADH₂`, `HS-CoA`, `Pi`, `CO₂`, `H₂O`)

**Template:**
```text
[Pathway / Step Prefix]:<br>{{c1::Substrate}} + {{c3::Cofactor/ATP}} ——[{{c2::Enzyme Name}}]——> {{c1::Product}} + {{c3::Byproduct/ADP/NADH}}
```
**Back Extra (`Extra` field — Strictly Images & Brief Clarification Only):**
- **NEVER place testable facts in `Extra`!** Pathway phase, reaction type (*substrate-level phosphorylation*, *isomerization*, *aldol cleavage*, *oxidative decarboxylation*), thermodynamic status, committed step status, and allosteric regulators are **testable exam material** and MUST be tested as active-recall Cloze deletions (`{{c1::...}}`, `{{c2::...}}`) on their own card (immediately following the reaction card on the same slide).
- The `Extra` field should ONLY contain the relevant extracted slide figure (`<img src="...">`) and/or a brief 1-sentence visual pointer or non-testable clarification.

---

### 2. Unbundle Multi-Step Enzymatic Cascades (1 Step = 1 Card)
- Never cram a multi-step enzymatic cascade (e.g., PDH E1 $\rightarrow$ E2 $\rightarrow$ E3) into a single run-on sentence with 6–8 clozes.
- Start with a **Parent Subunit Card** that pairs subunit abbreviations (`c1`) with full enzyme names (`c2`):
  `"The Pyruvate Dehydrogenase (PDH) complex is composed of three catalytic subunits: {{c1::E1}} ({{c2::pyruvate dehydrogenase}}), {{c1::E2}} ({{c2::dihydrolipoyl transacetylase}}), and {{c1::E3}} ({{c2::dihydrolipoyl dehydrogenase}})."`
- Follow with **1 concise sequential card per partial reaction step**, each with a clear pathway/subunit prefix (`PDH (E1 Decarboxylation):`, `PDH (E1 → E2 Transfer):`, `PDH (E2 Transesterification):`, `PDH (E3 Reoxidation):`) and the corresponding slide diagram in `extra`.

---

### 3. Natural Subject-First Sentence Structure & Atomic Cloze Hygiene
- **Subject-First Definitions (No "Jeopardy" Paragraph Clozes):** Never start a card by clozing a 15–25 word definition clause (`"{{c2::Long definition...}} is called {{c1::Term}}"`). Put the term at the start (`{{c2::Coenzyme A (CoA)}} is an activated {{c1::acyl-group}} carrier...`) and cloze short 1–4 word atomic phrases.
- **2-Tier Mutual-Cue Clozes (`c1` & `c2` Preferred, Max 3–4 Cloze Boxes):** Prefer 2 coordinated cloze tiers (`c1` = structure/subunit/cofactor, `c2` = function/intermediate/outcome) with at most 3–4 total cloze boxes per card. Never collapse 5+ blanks into `c1` ("Swiss cheese sentence") and never place cognate words in adjacent clozes (`{{c1::carboxylate}} {{c2::decarboxylates}}`).

---

### 4. Qualitative Thermodynamics, Zero Historical Trivia, & Typo Fact-Checking
1. **Qualitative Thermodynamics & Chemical Rationale Over Raw Decimals:**
   - Cloze whether a step is `{{c1::exergonic}}`/`endergonic` and `{{c1::irreversible}}`/`reversible`, and the chemical/orbital reason why (`3p` vs `2p` orbital overlap, `C–S` vs `C–O` bond stability, `resonance stabilization`), keeping raw $\Delta G'^\circ$ decimals (`–29.6 kJ/mol`, `–33.5 kJ/mol`) un-clozed in parentheses for context.
2. **No Historical Trivia & No Recap Duplicates:**
   - Never generate cards on scientist names, discovery dates, or Nobel Prizes (e.g., Fritz Lipmann / Hans Krebs 1953).
   - Never generate duplicate summary cards from a lecture's final recap slide when those concepts were already tested on earlier slides.
3. **Biochemical Fact-Checking of Slide Typos:**
   - If a slide contains an obvious biochemical typo (e.g., stating $\text{NAD}^+$ is derived from Vitamin B12 instead of **Vitamin B3 / niacin**), test the biochemically correct fact (`{{c2::Vitamin B3 (niacin)}}`) on the card front and note the slide typo briefly in `extra`.
