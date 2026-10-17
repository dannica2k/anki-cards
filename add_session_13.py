#!/usr/bin/env python3
"""
Add Session 13 cards to 'MBB 321 - Intermediary Metabolism Flashcards - Updated.apkg'.
Follows MBB_ANKI_PROMPT.md guidelines.
"""

import os
import time
import zlib
import re
import random
import string
import zipfile
import sqlite3
import tempfile
import zstandard as zstd

DECK_APKG = 'MBB 321 - Intermediary Metabolism Flashcards - Updated.apkg'

def gen_guid():
    chars = string.ascii_letters + string.digits + "!#$%&()*+,-./:;<=>?@[]^_`{|}~"
    return "".join(random.choice(chars) for _ in range(10))

def extract_cloze_numbers(text):
    matches = re.findall(r'\{\{c(\d+)::', text)
    return sorted(list(set(int(m) for m in matches)))

def add_session_13():
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting '{DECK_APKG}'...")
        with zipfile.ZipFile(DECK_APKG, 'r') as z:
            z.extractall(tmpdir)

        anki21b_path = os.path.join(tmpdir, 'collection.anki21b')
        db_path = os.path.join(tmpdir, 'collection.anki21')

        dctx = zstd.ZstdDecompressor()
        with open(anki21b_path, 'rb') as ifh, open(db_path, 'wb') as ofh:
            dctx.copy_stream(ifh, ofh)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Get model_id and deck_id
        cur.execute('SELECT mid, did FROM cards JOIN notes ON cards.nid = notes.id LIMIT 1')
        mid, did = cur.fetchone()

        # Remove any existing Session 13 notes if re-running
        cur.execute('SELECT id FROM notes WHERE tags LIKE "%Session::13%"')
        existing = [r[0] for r in cur.fetchall()]
        if existing:
            print(f"Removing {len(existing)} existing Session 13 notes...")
            for nid in existing:
                cur.execute('DELETE FROM cards WHERE nid = ?', (nid,))
                cur.execute('DELETE FROM notes WHERE id = ?', (nid,))

        # Define Session 13 Notes
        session_13_notes = [
            # --- REACTION 1: HEXOKINASE ---
            (
                "Hexokinase Cofactor Role (Reaction 1):<br>Hexokinase requires {{c1::Mg²⁺–ATP}} (not free ATP) because {{c1::Mg²⁺}} coordinates the {{c2::β- and γ-phosphates}}, shielding negative charges to make the {{c2::γ-phosphate}} more electrophilic for attack by the {{c3::C6–OH}} of glucose.",
                "Mg2+ also stabilizes the developing negative charge on the ADP leaving group."
            ),
            (
                "Hexokinase Kinetic Mechanism & Regulation (Reaction 1):<br>Hexokinase operates via a {{c1::Random Bi–Bi}} kinetic mechanism (forming a {{c1::ternary complex}} before phosphoryl transfer) and is regulated via {{c2::product inhibition}} by {{c2::glucose-6-phosphate (G6P)}}.",
                "Endergonic G6P formation is driven by coupling to highly exergonic ATP hydrolysis. Highest kcat/Km for D-glucose among hexoses."
            ),

            # --- REACTION 2: PHOSPHOHEXOSE ISOMERASE ---
            (
                "Phosphohexose Isomerase Ring & Chemical Rationale (Reaction 2):<br>Phosphohexose isomerase (PGI) converts the {{c1::6-membered pyranose}} ring of G6P (an {{c1::aldose}}) into the {{c2::5-membered furanose}} ring of F6P (a {{c2::ketose}}) via an {{c3::enediol}} intermediate.",
                "Reversible (ΔG'° ≈ 0); direction driven by substrate/product concentrations."
            ),
            (
                "Why Isomerize G6P to F6P in Reaction 2?<br>1. Exposes an {{c1::exocyclic primary hydroxyl group at C1}} for easy phosphorylation by PFK-1.<br>2. Positions the carbonyl at {{c2::C2}}, enabling subsequent {{c2::symmetric aldol cleavage}} (between C3–C4) into two 3-carbon sugars.",
                "Without isomerization to a ketose, aldol cleavage would yield unequal carbon fragments."
            ),

            # --- REACTION 3: PFK-1 ---
            (
                "PFK-1 Commitment & Allosteric Regulation (Reaction 3):<br>Phosphofructokinase-1 (PFK-1) catalyzes the {{c1::first committed, rate-limiting step}} of glycolysis:<br>• Allosteric Activators (R state): {{c2::AMP, ADP, and Fructose-2,6-bisphosphate (F-2,6-BP)}}<br>• Allosteric Inhibitors (T state): {{c3::ATP and Citrate}}",
                "Highly exergonic and essentially irreversible. Require Mg2+ to stabilize ATP."
            ),

            # --- REACTION 4: ALDOLASE ---
            (
                "Aldolase Thermodynamics in the Cell (Reaction 4):<br>Although the cleavage of F-1,6-BP into GAP + DHAP has a {{c1::strongly positive standard free energy (ΔG′° > 0)}}, the actual physiological ΔG′ in the cell is {{c2::near zero (reversible)}} because {{c3::products (GAP and DHAP) are rapidly consumed}}, keeping the mass-action ratio Q low.",
                "ΔG' = ΔG'° + RT ln([DHAP][GAP]/[F1,6BP]). Allows Aldolase to operate in both glycolysis and gluconeogenesis."
            ),
            (
                "Aldolase Chemical Mechanism (Reaction 4):<br>Aldolase breaks the C3–C4 bond via a reversible {{c1::aldol elimination}} mechanism:<br>1. A general base deprotonates the {{c2::C4 hydroxyl}}, forming the aldehyde {{c2::GAP}}.<br>2. Cleavage ejects a resonance-stabilized {{c3::enolate anion (α-carbanion)}} leaving group, which is protonated at the α-carbon to yield {{c3::DHAP}}.",
                "In the reverse direction (gluconeogenesis), the enolate of DHAP acts as a nucleophile to attack the carbonyl of GAP (aldol addition)."
            ),

            # --- REACTION 5: TRIOSE PHOSPHATE ISOMERASE (TPI) ---
            (
                "Triose Phosphate Isomerase (TPI) Purpose & Mechanism (Reaction 5):<br>TPI interconverts {{c1::DHAP (ketose)}} and {{c1::GAP (aldose)}} via an {{c2::enediol intermediate}} using {{c2::Asp and His}} for acid/base catalysis.",
                "Essential because only GAP can enter the payoff phase; prevents loss of half the carbons of glucose."
            ),
            (
                "TPI Kinetics & Thermodynamics (Reaction 5):<br>• Thermodynamics: Endergonic under standard conditions, but pulled forward in cells by {{c1::low [GAP]}} (rapid consumption by GAPDH).<br>• Kinetics: Operates at the {{c2::diffusion limit}} (kcat/Km ≈ 2 × 10⁸ M⁻¹s⁻¹), making it a {{c2::catalytically perfect enzyme}}.",
                "Directly analogous in mechanism to Reaction 2 (phosphohexose isomerase)."
            ),

            # --- REACTION 6: GAPDH ---
            (
                "GAPDH 4-Step Catalytic Mechanism (Reaction 6):<br>1. <b>Nucleophilic attack:</b> Active-site {{c1::Cys149}} attacks the C1 aldehyde of GAP to form a covalent {{c1::thiohemiacetal}}.<br>2. <b>Oxidation:</b> Hydride transfer to {{c2::NAD⁺}} oxidizes it into a high-energy {{c2::acyl-enzyme thioester}} (generating NADH).<br>3. <b>Cofactor exchange:</b> Bound NADH is replaced by fresh {{c2::NAD⁺}}.<br>4. <b>Phosphorolysis:</b> {{c3::Inorganic phosphate (Pi)}} attacks the thioester, releasing {{c3::1,3-BPG}}.",
                "Couples favorable aldehyde oxidation to unfavorable phosphorylation without using ATP."
            ),
            (
                "Chemical Nature of 1,3-Bisphosphoglycerate (Reaction 6 & 7):<br>At C1, 1,3-BPG contains an ultra high-energy {{c1::acyl phosphate}} bond (ΔG′° of hydrolysis ≈ {{c2::−49.0 kJ/mol}}), giving it a high {{c3::phosphoryl-transfer potential}} to drive ATP synthesis (+30.5 kJ/mol).",
                "In cells, Reaction 6 is pulled forward because 1,3-BPG is immediately consumed by PGK in Reaction 7."
            ),

            # --- REACTION 7: PHOSPHOGLYCERATE KINASE (PGK) ---
            (
                "Phosphoglycerate Kinase (PGK) Energetics & Role (Reaction 7):<br>PGK catalyzes the first {{c1::substrate-level phosphorylation}} of glycolysis, transferring the C1 acyl-phosphate of {{c2::1,3-BPG}} to {{c2::ADP}} (with {{c3::Mg²⁺}} coordination) to repay the {{c3::2 ATP}} invested in Phase 1.",
                "Net ΔG'° ≈ -18.5 kJ/mol (-49.0 + 30.5 kJ/mol), strongly favorable."
            ),

            # --- REACTION 8: PHOSPHOGLYCERATE MUTASE (PGM) ---
            (
                "Phosphoglycerate Mutase (PGM) Mechanism (Reaction 8):<br>PGM repositions the phosphate from C3 to C2 via a phosphorylated {{c1::Histidine (pHis)}} active site:<br>1. pHis transfers its phosphate to C2 of 3-PG, forming a transient {{c2::2,3-bisphosphoglycerate (2,3-BPG)}} intermediate.<br>2. The {{c3::C3 phosphate}} is transferred back to the enzyme His, releasing {{c3::2-PG}} and regenerating pHis.",
                "Driven forward physiologically by high [3-PG] relative to [2-PG]."
            ),

            # --- REACTION 9: ENOLASE ---
            (
                "Enolase Bioenergetic Rationale (Reaction 9):<br>Enolase (a lyase) dehydrates {{c1::2-PG}} to {{c1::PEP}}, which redistributes intramolecular energy and raises the ΔG′° of phosphate hydrolysis from {{c2::−15.6 kJ/mol}} (low-energy ester) to {{c2::−61.9 kJ/mol}} (ultra high-energy enol phosphate).",
                "Prepares the phosphoryl group for the final ATP-generating step."
            ),
            (
                "Enolase Catalytic Mechanism (Reaction 9):<br>1. {{c1::Mg²⁺}} coordinates the carboxylate of 2-PG.<br>2. Active-site {{c2::Lysine}} abstracts the C2 proton, forming a Mg²⁺-stabilized {{c2::dianion intermediate}}.<br>3. Collapse of the dianion eliminates the C3–OH as {{c3::H₂O}}, assisted by protonation from {{c3::Glutamate}}.",
                "Creates the C2=C3 double bond of phosphoenolpyruvate (PEP)."
            ),

            # --- REACTION 10: PYRUVATE KINASE (PK) ---
            (
                "Pyruvate Kinase (PK) & Tautomerization Driving Force (Reaction 10):<br>Pyruvate kinase catalyzes the {{c1::most exergonic}} reaction of glycolysis (PEP + ADP → Pyruvate + ATP). Its massive thermodynamic driving force comes from the rapid, non-enzymatic {{c2::enol-to-keto tautomerization}} of pyruvate after phosphoryl transfer.",
                "PEP is trapped in the unstable enol form by its phosphate group; removing the phosphate allows conversion to the highly stable keto tautomer."
            ),

            # --- INTEGRATED PATHWAY OVERVIEW (SLIDE 15 STUDY TIP) ---
            (
                "High-Energy Phosphoryl Donors of Glycolysis (Reactions 7 & 10):<br>The two glycolytic intermediates capable of direct <b>substrate-level phosphorylation</b> of ADP (ΔG′° of hydrolysis more negative than ATP's −30.5 kJ/mol) are:<br>1. {{c1::1,3-Bisphosphoglycerate (1,3-BPG)}} (ΔG′° ≈ −49.0 kJ/mol)<br>2. {{c2::Phosphoenolpyruvate (PEP)}} (ΔG′° ≈ −61.9 kJ/mol)",
                "Slide 15 Study Tip: Mastering the structures and chemical rationale of Glucose, F-1,6-BP, 1,3-BPG, and PEP connects the entire pathway."
            ),
            (
                "Thermodynamic Driving Strategies in Glycolysis:<br>• Irreversible regulatory steps driven by negative ΔG′°: Reactions {{c1::1 (Hexokinase), 3 (PFK-1), and 10 (Pyruvate kinase)}}.<br>• Standard-state endergonic steps pulled forward in vivo by rapid product depletion (low Q): Reactions {{c2::4 (Aldolase), 5 (TPI), 6 (GAPDH), and 8 (PGM)}}.",
                "Demonstrates how ΔG' = ΔG'° + RT ln Q allows endergonic standard reactions to proceed smoothly in the cell."
            )
        ]

        tag_str = " #MBB321::Session::13 "
        now_ts = int(time.time())

        print(f"Adding {len(session_13_notes)} high-yield notes for Session 13...")
        for idx, (front_text, extra_text) in enumerate(session_13_notes):
            nid = int(time.time() * 1000) + idx * 43 + random.randint(1, 30)
            guid = gen_guid()
            flds = f"{front_text}\x1f{extra_text}"
            sfld = front_text
            csum = zlib.crc32(sfld.encode('utf-8')) & 0xffffffff

            cur.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, -1, ?, ?, ?, ?, 0, "")
            ''', (nid, guid, mid, now_ts, tag_str, flds, sfld, csum))

            cloze_nums = extract_cloze_numbers(front_text)
            for ord_idx in cloze_nums:
                cid = int(time.time() * 1000) + random.randint(1000, 999999)
                cur.execute('''
                    INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                    VALUES (?, ?, ?, ?, ?, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "")
                ''', (cid, nid, did, ord_idx - 1, now_ts))

        conn.commit()

        cur.execute('SELECT count(*) FROM notes')
        tot_notes = cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM cards')
        tot_cards = cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM notes WHERE tags LIKE "%Session::13%"')
        s13_notes = cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM cards JOIN notes ON cards.nid = notes.id WHERE notes.tags LIKE "%Session::13%"')
        s13_cards = cur.fetchone()[0]

        print(f"\nUpdated Deck Statistics:")
        print(f"  Session 13 Notes Added: {s13_notes}")
        print(f"  Session 13 Cards Added: {s13_cards}")
        print(f"  Total Notes in Deck:    {tot_notes}")
        print(f"  Total Cards in Deck:    {tot_cards}")

        conn.close()

        # Recompress to collection.anki21b
        cctx = zstd.ZstdCompressor(level=3)
        with open(db_path, 'rb') as ifh, open(anki21b_path, 'wb') as ofh:
            cctx.copy_stream(ifh, ofh)

        os.remove(db_path)

        with zipfile.ZipFile(DECK_APKG, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, tmpdir)
                    zout.write(full_p, rel_p)

    print(f"Successfully updated '{DECK_APKG}'!")

if __name__ == '__main__':
    add_session_13()
