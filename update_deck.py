#!/usr/bin/env python3
"""
Overhaul Session 12 cards in 'MBB 321 - Intermediary Metabolism Flashcards.apkg'.
"""

import os
import sys
import time
import json
import zlib
import re
import random
import string
import zipfile
import sqlite3
import tempfile
import zstandard as zstd
from pathlib import Path

SOURCE_APKG = 'MBB 321 - Intermediary Metabolism Flashcards.apkg'
OUTPUT_APKG = 'MBB 321 - Intermediary Metabolism Flashcards - Updated.apkg'

def gen_guid():
    chars = string.ascii_letters + string.digits + "!#$%&()*+,-./:;<=>?@[]^_`{|}~"
    return "".join(random.choice(chars) for _ in range(10))

def extract_cloze_numbers(text):
    """Finds all distinct cloze indices (e.g. {{c1::...}}, {{c2::...}}) in text."""
    matches = re.findall(r'\{\{c(\d+)::', text)
    return sorted(list(set(int(m) for m in matches)))

def update_deck():
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Extracting '{SOURCE_APKG}'...")
        with zipfile.ZipFile(SOURCE_APKG, 'r') as z:
            z.extractall(tmpdir)

        anki21b_path = os.path.join(tmpdir, 'collection.anki21b')
        db_path = os.path.join(tmpdir, 'collection.anki21')

        # Decompress zstd
        dctx = zstd.ZstdDecompressor()
        with open(anki21b_path, 'rb') as ifh, open(db_path, 'wb') as ofh:
            dctx.copy_stream(ifh, ofh)

        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Find deck ID and model ID for Cloze
        cur.execute('SELECT mid, did FROM cards JOIN notes ON cards.nid = notes.id WHERE tags LIKE "%12%" LIMIT 1')
        mid, did = cur.fetchone()
        print(f"Found model_id: {mid}, deck_id: {did}")

        # List existing Session 12 notes
        cur.execute('SELECT id, flds FROM notes WHERE tags LIKE "%12%"')
        s12_notes = cur.fetchall()
        print(f"Current Session 12 notes: {len(s12_notes)}")

        # Notes to delete: old reaction notes (Cards 13-22 in our previous list)
        # Identify them by matching "Glycolysis step" or "Glycolysis Step"
        delete_nids = []
        for nid, flds in s12_notes:
            front = flds.split('\x1f')[0]
            if re.search(r'Glycolysis\s+[Ss]tep\s+\{\{c2::\d+\}\}', front):
                delete_nids.append(nid)

        print(f"Deleting {len(delete_nids)} old single-string reaction notes...")
        for nid in delete_nids:
            cur.execute('DELETE FROM cards WHERE nid = ?', (nid,))
            cur.execute('DELETE FROM notes WHERE id = ?', (nid,))

        # Update Card 2 (Gluconeogenesis precursors) to be cleaner and not overly bundled
        # Find note containing gluconeogenesis
        for nid, flds in s12_notes:
            if "gluconeogenesis" in flds:
                print(f"Refining note {nid} (gluconeogenesis)...")
                new_flds = "The liver & kidney cells perform {{c1::gluconeogenesis}} to synthesize {{c2::glucose}} from non-carbohydrate precursors: {{c3::pyruvate}}, {{c3::lactate}}, {{c3::glycerol}}, and {{c3::glucogenic amino acids}}.\x1f"
                sfld = "The liver & kidney cells perform {{c1::gluconeogenesis}} to synthesize {{c2::glucose}} from non-carbohydrate precursors: {{c3::pyruvate}}, {{c3::lactate}}, {{c3::glycerol}}, and {{c3::glucogenic amino acids}}."
                csum = zlib.crc32(sfld.encode('utf-8')) & 0xffffffff
                now = int(time.time())
                cur.execute('UPDATE notes SET flds = ?, sfld = ?, csum = ?, mod = ? WHERE id = ?', (new_flds, sfld, csum, now, nid))
                # Update cards for this note
                cur.execute('DELETE FROM cards WHERE nid = ?', (nid,))
                clozes = extract_cloze_numbers(new_flds)
                for ord_idx in clozes:
                    cid = int(time.time() * 1000) + random.randint(100, 99999)
                    cur.execute('''
                        INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                        VALUES (?, ?, ?, ?, ?, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "")
                    ''', (cid, nid, did, ord_idx - 1, now))

        # Define the new standardized Reaction notes (1 to 10)
        # Using the agreed format: c1 = substrate & product, c2 = enzyme, c3 = cofactors / energy
        reaction_notes = [
            (
                "Glycolysis (Reaction 1):<br>{{c1::Glucose}} + {{c3::ATP}} ——[{{c2::Hexokinase}}]——> {{c1::Glucose-6-phosphate (G-6-P)}} + {{c3::ADP}}",
                "Phase 1: Investment. Irreversible (regulatory) step. Phosphate tag traps glucose inside cell."
            ),
            (
                "Glycolysis (Reaction 2):<br>{{c1::Glucose-6-phosphate (G-6-P)}} ——[{{c2::Phosphoglucose isomerase (PGI)}}]——> {{c1::Fructose-6-phosphate (F-6-P)}}",
                "Phase 1: Investment. Isomerization (aldose to ketose conversion)."
            ),
            (
                "Glycolysis (Reaction 3):<br>{{c1::Fructose-6-phosphate (F-6-P)}} + {{c3::ATP}} ——[{{c2::Phosphofructokinase-1 (PFK-1)}}]——> {{c1::Fructose-1,6-bisphosphate (F-1,6-BP)}} + {{c3::ADP}}",
                "Phase 1: Investment. First committed step of glycolysis. Highly regulated."
            ),
            (
                "Glycolysis (Reaction 4):<br>{{c1::Fructose-1,6-bisphosphate (F-1,6-BP)}} ——[{{c2::Aldolase}}]——> {{c1::GAP}} + {{c1::DHAP}}",
                "Phase 1: Investment (Cleavage). Splitting 6C hexose into two 3C triose sugars."
            ),
            (
                "Glycolysis (Reaction 5):<br>{{c1::Dihydroxyacetone phosphate (DHAP)}} ——[{{c2::Triose phosphate isomerase (TPI)}}]——> {{c1::Glyceraldehyde-3-phosphate (GAP)}}",
                "Phase 1: Investment. End of Phase 1: yields two molecules of GAP per initial glucose."
            ),
            (
                "Glycolysis (Reaction 6):<br>{{c1::GAP}} + {{c3::Pi + NAD⁺}} ——[{{c2::GAPDH}}]——> {{c1::1,3-Bisphosphoglycerate (1,3-BPG)}} + {{c3::NADH + H⁺}}",
                "Phase 2: Payoff. Oxidation coupled to phosphorylation using free inorganic phosphate (Pi), producing NADH."
            ),
            (
                "Glycolysis (Reaction 7):<br>{{c1::1,3-Bisphosphoglycerate (1,3-BPG)}} + {{c3::ADP}} ——[{{c2::Phosphoglycerate kinase (PGK)}}]——> {{c1::3-Phosphoglycerate (3-PG)}} + {{c3::ATP}}",
                "Phase 2: Payoff. First substrate-level phosphorylation (recovers invested ATP)."
            ),
            (
                "Glycolysis (Reaction 8):<br>{{c1::3-Phosphoglycerate (3-PG)}} ——[{{c2::Phosphoglycerate mutase (PGM)}}]——> {{c1::2-Phosphoglycerate (2-PG)}}",
                "Phase 2: Payoff. Intramolecular shift of the phosphate group."
            ),
            (
                "Glycolysis (Reaction 9):<br>{{c1::2-Phosphoglycerate (2-PG)}} ——[{{c2::Enolase}}]——> {{c1::Phosphoenolpyruvate (PEP)}} + {{c3::H₂O}}",
                "Phase 2: Payoff. Dehydration creating a high-energy enol phosphate bond."
            ),
            (
                "Glycolysis (Reaction 10):<br>{{c1::Phosphoenolpyruvate (PEP)}} + {{c3::ADP}} ——[{{c2::Pyruvate kinase (PK)}}]——> {{c1::Pyruvate}} + {{c3::ATP}}",
                "Phase 2: Payoff. Second substrate-level phosphorylation. Irreversible (regulatory) step generating net payoff ATP."
            ),
        ]

        # Define new conceptual and mechanistic notes
        conceptual_notes = [
            (
                "Glycolysis Central Paradox (Slide 8):<br>Glycolysis extracts energy with <b>no net oxidation</b> because the {{c1::exergonic oxidation}} of glyceraldehyde (Reaction 6) is coupled to ATP synthesis, while clearing NADH by {{c2::reducing pyruvate to lactate}} is {{c2::mildly endergonic}}.",
                "Overall total carbon oxidation state of glucose and lactate is identical; energy is released because lactate is thermodynamically more stable."
            ),
            (
                "Carbon Oxidation State in Glycolysis (Slide 8):<br>In anaerobic glycolysis (Glc → 2 Lactate), there is {{c1::no net change}} in the overall carbon oxidation state. Carbon-1 gets {{c2::oxidized}} (forming carboxylate in lactate), while Carbon-2 gets {{c2::reduced}} (forming alcohol in lactate).",
                "This internal disproportionation allows energy capture without external electron acceptors."
            ),
            (
                "Net Balanced Equation for Anaerobic Glycolysis (Slide 4, 7):<br>{{c1::Glucose}} + {{c2::2 Pi}} + {{c2::2 ADP}} ——> {{c1::2 Lactate}} + {{c3::2 ATP (net)}}",
                "Gross ATP produced = 4 ATP (2 recovered investment + 2 new payoff). Net ATP = 2 ATP."
            ),
            (
                "ATP Accounting in Glycolysis (Slide 6, 7):<br>Per molecule of glucose:<br>• Investment Phase: consumes {{c1::2 ATP}}<br>• Payoff Phase: produces {{c2::4 ATP}} total ({{c2::2 recovered}} + {{c2::2 new payoff}})<br>• Net Gain: {{c3::+2 ATP}}",
                "Each 3-carbon triose undergoes payoff steps twice (2x)."
            ),
            (
                "The 3 Biological Roles of Phosphate Tagging in Glycolysis (Slide 6):<br>1. Prevents {{c1::diffusion / leakage out of the cell}} (negatively charged).<br>2. Enables {{c1::recognition and binding by glycolytic enzymes}}.<br>3. {{c1::Stores chemical energy}} to later drive ATP synthesis.",
                "Hexokinase and PFK-1 attach the two initial phosphate tags at the cost of 2 ATP."
            ),
            (
                "Yeast Ethanol Fermentation Pathway (Slide 9):<br>Step 1: Pyruvate ——[{{c2::Pyruvate decarboxylase}}]——> {{c1::Acetaldehyde}} + {{c3::CO₂}}<br>Step 2: Acetaldehyde + {{c3::NADH + H⁺}} ——[{{c2::Alcohol dehydrogenase}}]——> {{c1::Ethanol}} + {{c3::NAD⁺}}",
                "Primary purpose: Regenerate NAD+ to sustain Reaction 6 (GAPDH) of glycolysis under anaerobic conditions."
            ),
            (
                "Fermentation and the NAD⁺/NADH Pool (Slide 9):<br>Under anaerobic conditions, fermentation produces no additional ATP; its essential function is to {{c1::regenerate NAD⁺}} from NADH so that {{c2::GAP dehydrogenase (Reaction 6)}} can continue.",
                "Without NAD+ regeneration, glycolysis stops immediately due to lack of coenzyme for GAPDH."
            ),
            (
                "Irreversible / Regulatory Reactions of Glycolysis:<br>The reactions in glycolysis that have large negative ΔG′° are reactions {{c1::1}}, {{c1::3}}, and {{c1::10}}, catalyzed by {{c2::Hexokinase}}, {{c2::PFK-1}}, and {{c2::Pyruvate kinase}}.",
                "These three irreversible kinase steps are the primary control points of glycolytic flux."
            )
        ]

        all_new_notes = reaction_notes + conceptual_notes
        print(f"Adding {len(all_new_notes)} new notes ({len(reaction_notes)} reaction notes + {len(conceptual_notes)} conceptual notes)...")

        tag_str = " #MBB321::Session::12 "
        now_ts = int(time.time())

        for idx, (front_text, extra_text) in enumerate(all_new_notes):
            nid = int(time.time() * 1000) + idx * 37 + random.randint(1, 20)
            guid = gen_guid()
            flds = f"{front_text}\x1f{extra_text}"
            sfld = front_text
            csum = zlib.crc32(sfld.encode('utf-8')) & 0xffffffff

            cur.execute('''
                INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data)
                VALUES (?, ?, ?, ?, -1, ?, ?, ?, ?, 0, "")
            ''', (nid, guid, mid, now_ts, tag_str, flds, sfld, csum))

            # Create cards for each cloze
            cloze_nums = extract_cloze_numbers(front_text)
            for ord_idx in cloze_nums:
                cid = int(time.time() * 1000) + random.randint(1000, 999999)
                cur.execute('''
                    INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data)
                    VALUES (?, ?, ?, ?, ?, -1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, "")
                ''', (cid, nid, did, ord_idx - 1, now_ts))

        conn.commit()

        # Check total counts
        cur.execute('SELECT count(*) FROM notes')
        tot_notes = cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM cards')
        tot_cards = cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM notes WHERE tags LIKE "%12%"')
        s12_notes_cnt = cur.fetchone()[0]
        cur.execute('SELECT count(*) FROM cards JOIN notes ON cards.nid = notes.id WHERE notes.tags LIKE "%12%"')
        s12_cards_cnt = cur.fetchone()[0]

        print(f"\nFinal Deck Stats:")
        print(f"  Total Notes in Deck: {tot_notes}")
        print(f"  Total Cards in Deck: {tot_cards}")
        print(f"  Session 12 Notes: {s12_notes_cnt}")
        print(f"  Session 12 Cards: {s12_cards_cnt}")

        conn.close()

        # Re-compress database with zstd to collection.anki21b
        cctx = zstd.ZstdCompressor(level=3)
        with open(db_path, 'rb') as ifh, open(anki21b_path, 'wb') as ofh:
            cctx.copy_stream(ifh, ofh)

        # Remove uncompressed db
        os.remove(db_path)

        # Re-package apkg
        print(f"Repackaging into '{OUTPUT_APKG}'...")
        with zipfile.ZipFile(OUTPUT_APKG, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root, _, files in os.walk(tmpdir):
                for f in files:
                    full_p = os.path.join(root, f)
                    rel_p = os.path.relpath(full_p, tmpdir)
                    zout.write(full_p, rel_p)

    print("Overhaul complete!")
    return OUTPUT_APKG

if __name__ == '__main__':
    update_deck()
