"""
TrueFit-AI Database CLI Tool
Utility for inspecting, seeding, migrating, and managing PostgreSQL/SQLite databases.

Usage:
    python db.py status
    python db.py init
    python db.py seed [--data path_to_dataset]
    python db.py runs
    python db.py export [--out submission.csv]
"""

import sys
import argparse
import time
import json
from pathlib import Path

from database import get_db
from utils import load_candidates, generate_reasoning
from honeypot_detector import is_honeypot
from candidate_scorer import compute_core_fit
try:
    from text_scorer import compute_text_scores
except Exception:
    def compute_text_scores(candidates):
        import numpy as np
        return np.array([0.5 for _ in candidates])
from behavioral_scorer import compute_behavioral_modifier
import config


def find_default_dataset():
    """Auto-detect candidate dataset file."""
    base_dir = Path(__file__).parent
    for p in [
        base_dir / "sample_candidates.json",
        *base_dir.rglob("sample_candidates.json"),
        *base_dir.rglob("candidates.jsonl")
    ]:
        if p.exists():
            return str(p)
    return None


def cmd_status(args):
    db = get_db()
    status = db.get_db_status()
    print("\n================ TrueFit-AI Database Status ================")
    print(f"  Engine:            {status['engine_display']}")
    print(f"  Status:            {status['status'].upper()}")
    print(f"  Target:            {status['db_target']}")
    print(f"  DATABASE_URL set:  {status['database_url_configured']}")
    print(f"  Total Candidates:  {status['total_candidates']}")
    print(f"  Total Scoring Runs:{status['total_runs']}")
    print(f"  Active Run ID:     {status['active_run_id'] or 'None'}")
    print(f"  Shortlisted Count: {status['shortlisted_count']}")
    print("============================================================\n")


def cmd_init(args):
    db = get_db()
    db.create_tables()
    print(f"Database schema initialized successfully for {db.engine_type.upper()}.")


def cmd_seed(args):
    db = get_db()
    dataset_path = args.data or find_default_dataset()
    if not dataset_path or not Path(dataset_path).exists():
        print(f"[Error] Dataset file not found: {dataset_path}")
        return

    print(f"[Seed] Loading candidates from: {dataset_path}")
    t0 = time.time()
    candidates = list(load_candidates(dataset_path))
    print(f"[Seed] Loaded {len(candidates)} candidates in {time.time() - t0:.2f}s")

    # Save candidates to database
    print("[Seed] Ingesting candidates into database...")
    db.save_candidates_batch(candidates)
    print(f"[Seed] Successfully saved {len(candidates)} candidates into DB table 'candidates'.")

    # Run scoring pipeline and persist scoring run
    print("[Seed] Running 4-layer scoring pipeline...")
    t1 = time.time()

    honeypot_flags = [is_honeypot(c) for c in candidates]
    honeypot_count = sum(1 for f in honeypot_flags if f)
    core_scores = [compute_core_fit(c) for c in candidates]
    text_scores = compute_text_scores(candidates)
    behavioral_mods = [compute_behavioral_modifier(c) for c in candidates]

    scored_list = []
    for i, c in enumerate(candidates):
        is_hp = honeypot_flags[i]
        core = core_scores[i]
        text_rel = float(text_scores[i])
        beh = behavioral_mods[i]

        final = (
            config.CORE_FIT_WEIGHT * core["core_fit"]
            + config.TEXT_RELEVANCE_WEIGHT * text_rel
        ) * beh

        if is_hp:
            final = 0.0

        scores_dict = {
            **core,
            "text_relevance": round(text_rel, 4),
            "behavioral": round(beh, 4),
            "final": round(final, 4),
            "is_honeypot": is_hp
        }

        reasoning = generate_reasoning(c, scores_dict)
        scored_list.append({
            "candidate_id": c["candidate_id"],
            "is_honeypot": is_hp,
            "scores": scores_dict,
            "reasoning": reasoning
        })

    # Sort & assign rank
    valid = [r for r in scored_list if not r["is_honeypot"]]
    valid.sort(key=lambda x: (-x["scores"]["final"], x["candidate_id"]))
    for idx, r in enumerate(valid, start=1):
        r["rank"] = idx

    for r in scored_list:
        if r["is_honeypot"]:
            r["rank"] = -1

    top_scores = [r["scores"]["final"] for r in valid[:100]] if valid else [0]
    avg_score = sum(top_scores) / max(len(top_scores), 1)

    run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    stats = {
        "total_candidates": len(candidates),
        "valid_candidates": len(valid),
        "honeypots_count": honeypot_count,
        "top_score": top_scores[0] if top_scores else 0,
        "cutoff_score_100": top_scores[-1] if len(top_scores) >= 100 else (top_scores[-1] if top_scores else 0),
        "avg_top100_score": round(avg_score, 4),
        "top_titles": {},
        "top_countries": {},
        "execution_time_sec": round(time.time() - t1, 2)
    }

    weights_cfg = {
        "CORE_FIT_WEIGHT": config.CORE_FIT_WEIGHT,
        "TEXT_RELEVANCE_WEIGHT": config.TEXT_RELEVANCE_WEIGHT,
        "TITLE_WEIGHT": config.TITLE_WEIGHT,
        "SKILLS_WEIGHT": config.SKILLS_WEIGHT,
        "CAREER_WEIGHT": config.CAREER_WEIGHT,
        "EXPERIENCE_WEIGHT": config.EXPERIENCE_WEIGHT,
        "LOCATION_WEIGHT": config.LOCATION_WEIGHT,
        "EDUCATION_WEIGHT": config.EDUCATION_WEIGHT
    }

    db.save_scoring_run(run_id, stats, weights_cfg, scored_list, dataset_source=dataset_path)
    print(f"[Seed] Successfully recorded scoring run '{run_id}' with {len(scored_list)} scores.")
    print("Database seeding completed successfully!")


def cmd_runs(args):
    db = get_db()
    runs = db.get_all_runs()
    print("\n================== Scoring Runs History ==================")
    for r in runs:
        active_mark = " [ACTIVE]" if r.get("is_active") else ""
        print(f"Run ID: {r['run_id']}{active_mark}")
        print(f"  Created:     {r['created_at']}")
        print(f"  Candidates:  Total={r['total_candidates']}, Valid={r['valid_candidates']}, Honeypots={r['honeypots_count']}")
        print(f"  Scores:      Top={r['top_score']:.4f}, Cutoff-100={r['cutoff_score_100']:.4f}, Avg={r['avg_top100_score']:.4f}")
        print(f"  Runtime:     {r['execution_time_sec']}s | Source: {r['dataset_source']}")
        print("-" * 58)
    print("==========================================================\n")


def cmd_export(args):
    import csv
    db = get_db()
    out_file = args.out or "submission.csv"
    res = db.query_candidates(page=1, page_size=100, top_only=True)
    top100 = res.get("candidates", [])
    
    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for c in top100:
            writer.writerow([c["candidate_id"], c["rank"], f"{c['scores']['final']:.4f}", c["reasoning"]])

    print(f"Exported {len(top100)} candidates directly from database to {out_file}")


def main():
    parser = argparse.ArgumentParser(description="TrueFit-AI Database CLI")
    subparsers = parser.add_subparsers(dest="command", help="Subcommand")

    # status
    sub = subparsers.add_parser("status", help="Show database status and statistics")
    sub.set_defaults(func=cmd_status)

    # init
    sub = subparsers.add_parser("init", help="Initialize tables and indexes")
    sub.set_defaults(func=cmd_init)

    # seed
    sub = subparsers.add_parser("seed", help="Seed dataset and compute baseline ranking")
    sub.add_argument("--data", type=str, default=None, help="Dataset file path")
    sub.set_defaults(func=cmd_seed)

    # runs
    sub = subparsers.add_parser("runs", help="List all scoring runs")
    sub.set_defaults(func=cmd_runs)

    # export
    sub = subparsers.add_parser("export", help="Export top 100 CSV from active run")
    sub.add_argument("--out", type=str, default="submission.csv", help="Output file path")
    sub.set_defaults(func=cmd_export)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    from datetime import datetime
    args.func(args)


if __name__ == "__main__":
    main()
