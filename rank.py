"""
Main ranking pipeline: reads candidates, scores them, outputs top 100.

Usage:
    python rank.py --candidates ./candidates.jsonl --out ./submission.csv
"""

import argparse
import time
import sys

from utils import load_candidates, write_submission_csv
from honeypot_detector import is_honeypot
from candidate_scorer import compute_core_fit
from text_scorer import compute_text_scores
from behavioral_scorer import compute_behavioral_modifier
import config


def main():
    parser = argparse.ArgumentParser(description="Rank candidates for Senior AI Engineer role")
    parser.add_argument("--candidates", required=True, help="Path to candidates.jsonl")
    parser.add_argument("--out", required=True, help="Output CSV path")
    parser.add_argument("--save-db", action="store_true", help="Also persist candidates and ranking run to the database")
    args = parser.parse_args()

    t0 = time.time()

    # =========================================================================
    # Phase 1: Load all candidates
    # =========================================================================
    print("[1/6] Loading candidates...")
    candidates = list(load_candidates(args.candidates))
    print(f"       Loaded {len(candidates)} candidates in {time.time() - t0:.1f}s")

    # =========================================================================
    # Phase 2: Honeypot detection
    # =========================================================================
    t1 = time.time()
    print("[2/6] Detecting honeypots...")
    honeypot_flags = []
    honeypot_count = 0
    for c in candidates:
        flag = is_honeypot(c)
        honeypot_flags.append(flag)
        if flag:
            honeypot_count += 1
    print(f"       Flagged {honeypot_count} honeypots in {time.time() - t1:.1f}s")

    # =========================================================================
    # Phase 3: Core fit scoring
    # =========================================================================
    t2 = time.time()
    print("[3/6] Computing core fit scores...")
    core_scores = []
    for c in candidates:
        core_scores.append(compute_core_fit(c))
    print(f"       Done in {time.time() - t2:.1f}s")

    # =========================================================================
    # Phase 4: TF-IDF text relevance
    # =========================================================================
    t3 = time.time()
    print("[4/6] Computing TF-IDF text relevance...")
    text_scores = compute_text_scores(candidates)
    print(f"       Done in {time.time() - t3:.1f}s")

    # =========================================================================
    # Phase 5: Behavioral modifiers
    # =========================================================================
    t4 = time.time()
    print("[5/6] Computing behavioral modifiers...")
    behavioral_mods = []
    for c in candidates:
        behavioral_mods.append(compute_behavioral_modifier(c))
    print(f"       Done in {time.time() - t4:.1f}s")

    # =========================================================================
    # Phase 6: Combine scores, sort, output
    # =========================================================================
    t5 = time.time()
    print("[6/6] Combining scores and ranking...")

    scored = []
    for i, c in enumerate(candidates):
        if honeypot_flags[i]:
            continue  # skip honeypots entirely

        core = core_scores[i]
        text_rel = float(text_scores[i])
        beh = behavioral_mods[i]

        final = (
            config.CORE_FIT_WEIGHT * core["core_fit"]
            + config.TEXT_RELEVANCE_WEIGHT * text_rel
        ) * beh

        scores_dict = {
            **core,
            "text_relevance": text_rel,
            "behavioral": beh,
            "final": final,
        }
        scored.append((c, scores_dict))

    # Sort by final score descending, then candidate_id ascending for tiebreak
    scored.sort(key=lambda x: (-x[1]["final"], x[0]["candidate_id"]))

    # Write top 100
    write_submission_csv(scored[:100], args.out)

    total = time.time() - t0
    print(f"\n       Wrote top 100 to {args.out}")
    print(f"       Total runtime: {total:.1f}s")

    # Quick stats on output
    if scored:
        top = scored[0][1]["final"]
        bottom = scored[99][1]["final"] if len(scored) >= 100 else scored[-1][1]["final"]
        print(f"       Score range: {top:.4f} (rank 1) to {bottom:.4f} (rank 100)")

    # Show top 5 for quick inspection
    print("\n       Top 5 candidates:")
    for i, (c, s) in enumerate(scored[:5], 1):
        p = c["profile"]
        print(f"         {i}. {c['candidate_id']} | {p['current_title']} at {p['current_company']} "
              f"| {p['years_of_experience']} yrs | score={s['final']:.4f}")

    if args.save_db:
        from database import get_db
        from datetime import datetime
        print("\n[DB] Persisting candidates and scoring run to database...")
        db = get_db()
        db.save_candidates_batch(candidates)

        scored_records = []
        for rank_idx, (cand, sc) in enumerate(scored, 1):
            scored_records.append({
                "candidate_id": cand["candidate_id"],
                "rank": rank_idx,
                "is_honeypot": False,
                "scores": sc,
                "reasoning": f"{cand['profile']['current_title']} at {cand['profile']['current_company']}"
            })

        run_id = f"cli_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        stats = {
            "total_candidates": len(candidates),
            "valid_candidates": len(scored),
            "honeypots_count": honeypot_count,
            "top_score": top,
            "cutoff_score_100": bottom,
            "avg_top100_score": sum(s[1]["final"] for s in scored[:100]) / max(len(scored[:100]), 1),
            "top_titles": {},
            "top_countries": {},
            "execution_time_sec": round(total, 2)
        }
        weights_cfg = {
            "CORE_FIT_WEIGHT": config.CORE_FIT_WEIGHT,
            "TEXT_RELEVANCE_WEIGHT": config.TEXT_RELEVANCE_WEIGHT
        }
        db.save_scoring_run(run_id, stats, weights_cfg, scored_records, dataset_source=args.candidates)
        print(f"[DB] Successfully saved run '{run_id}' to {db.engine_type.upper()} database.")


if __name__ == "__main__":
    main()
