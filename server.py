"""
Python Backend REST API Server for Intelligent Candidate Discovery & Ranking System.
Runs out-of-the-box using Python's standard library http.server + JSON.

Usage:
    python server.py [--port 8000] [--data path_to_candidates]
"""

import os
import sys
import json
import time
import argparse
import io
import csv
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Import project scoring pipeline modules
from utils import load_candidates, generate_reasoning
from honeypot_detector import is_honeypot
from candidate_scorer import compute_core_fit
try:
    from text_scorer import compute_text_scores
except Exception as e:
    print(f"Warning: text_scorer failed to import ({e}). Using basic text similarity fallback.")
    def compute_text_scores(candidates):
        import numpy as np
        return np.array([0.5 for _ in candidates])

from behavioral_scorer import compute_behavioral_modifier
import config

# Global in-memory cache for candidate data and scoring results
CACHE = {
    "candidates": [],
    "scored_candidates": [],  # list of dicts with full score details
    "ranked_list": [],        # list sorted by final score
    "stats": {},
    "data_path": None,
    "last_computed": 0,
    "custom_config": {
        "CORE_FIT_WEIGHT": config.CORE_FIT_WEIGHT,
        "TEXT_RELEVANCE_WEIGHT": config.TEXT_RELEVANCE_WEIGHT,
        "TITLE_WEIGHT": config.TITLE_WEIGHT,
        "SKILLS_WEIGHT": config.SKILLS_WEIGHT,
        "CAREER_WEIGHT": config.CAREER_WEIGHT,
        "EXPERIENCE_WEIGHT": config.EXPERIENCE_WEIGHT,
        "LOCATION_WEIGHT": config.LOCATION_WEIGHT,
        "EDUCATION_WEIGHT": config.EDUCATION_WEIGHT,
        "JD_QUERY": config.JD_QUERY
    }
}


def find_default_dataset():
    """Find candidate dataset path automatically across root and nested directories."""
    base_dir = Path(__file__).parent
    
    # 1. Check root directory sample_candidates.json
    root_sample = base_dir / "sample_candidates.json"
    if root_sample.exists():
        return str(root_sample)

    # 2. Check recursive search for sample_candidates.json or candidates.jsonl
    for match in base_dir.rglob("sample_candidates.json"):
        if match.exists():
            return str(match)

    for match in base_dir.rglob("candidates.jsonl"):
        if match.exists():
            return str(match)

    # 3. Check any json file in base dir
    for f in base_dir.glob("*.json"):
        if f.exists() and f.name not in ("package.json", "candidate_schema.json"):
            return str(f)

    return str(root_sample)


def generate_fallback_candidates():
    """Generate sample candidates if dataset file is missing on host."""
    return [
        {
            "candidate_id": "CAND_0002025",
            "profile": {
                "anonymized_name": "Aarav Sharma",
                "headline": "Senior AI Engineer | PyTorch, LLMs, Vector Search",
                "summary": "Senior AI Engineer with 5.9 years experience building scale NLP and search systems.",
                "location": "Noida",
                "country": "India",
                "years_of_experience": 5.9,
                "current_title": "Senior AI Engineer",
                "current_company": "Apple",
                "current_industry": "Technology"
            },
            "career_history": [
                {"company": "Apple", "title": "Senior AI Engineer", "duration_months": 24, "industry": "AI/ML", "description": "Deployed vector retrieval models in production."}
            ],
            "skills": [
                {"name": "NLP", "proficiency": "expert", "endorsements": 45, "duration_months": 36},
                {"name": "PyTorch", "proficiency": "expert", "endorsements": 50, "duration_months": 48},
                {"name": "FAISS", "proficiency": "expert", "endorsements": 30, "duration_months": 24}
            ],
            "redrob_signals": {"open_to_work_flag": True, "notice_period_days": 15, "recruiter_response_rate": 0.9}
        }
    ]


def run_pipeline(data_path=None, custom_cfg=None):
    """Run candidate evaluation pipeline and store results in CACHE."""
    t0 = time.time()
    if data_path is None:
        data_path = CACHE.get("data_path") or find_default_dataset()
        
    cfg = custom_cfg or CACHE["custom_config"]
    config.CORE_FIT_WEIGHT = cfg.get("CORE_FIT_WEIGHT", config.CORE_FIT_WEIGHT)
    config.TEXT_RELEVANCE_WEIGHT = cfg.get("TEXT_RELEVANCE_WEIGHT", config.TEXT_RELEVANCE_WEIGHT)
    config.TITLE_WEIGHT = cfg.get("TITLE_WEIGHT", config.TITLE_WEIGHT)
    config.SKILLS_WEIGHT = cfg.get("SKILLS_WEIGHT", config.SKILLS_WEIGHT)
    config.CAREER_WEIGHT = cfg.get("CAREER_WEIGHT", config.CAREER_WEIGHT)
    config.EXPERIENCE_WEIGHT = cfg.get("EXPERIENCE_WEIGHT", config.EXPERIENCE_WEIGHT)
    config.LOCATION_WEIGHT = cfg.get("LOCATION_WEIGHT", config.LOCATION_WEIGHT)
    config.EDUCATION_WEIGHT = cfg.get("EDUCATION_WEIGHT", config.EDUCATION_WEIGHT)
    if "JD_QUERY" in cfg and cfg["JD_QUERY"]:
        config.JD_QUERY = cfg["JD_QUERY"]

    print(f"[Pipeline] Loading dataset from: {data_path}")
    if not CACHE["candidates"] or CACHE["data_path"] != data_path:
        try:
            if Path(data_path).exists():
                CACHE["candidates"] = list(load_candidates(data_path))
                CACHE["data_path"] = data_path
            else:
                found = find_default_dataset()
                if Path(found).exists():
                    CACHE["candidates"] = list(load_candidates(found))
                    CACHE["data_path"] = found
                else:
                    raise FileNotFoundError(f"Dataset path {data_path} not found")
        except Exception as e:
            print(f"[Pipeline Warning] Could not load dataset file ({e}). Using sample candidate dataset.")
            CACHE["candidates"] = generate_fallback_candidates()
            CACHE["data_path"] = "Embedded Sample Dataset"

    candidates = CACHE["candidates"]
    total_count = len(candidates)
    print(f"[Pipeline] Loaded {total_count} candidates.")

    # Honeypots
    honeypot_flags = [is_honeypot(c) for c in candidates]
    honeypot_count = sum(1 for f in honeypot_flags if f)

    # Core Fit
    core_scores = [compute_core_fit(c) for c in candidates]

    # Text relevance
    text_scores = compute_text_scores(candidates)

    # Behavioral
    behavioral_mods = [compute_behavioral_modifier(c) for c in candidates]

    # Scored records
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
            final = 0.0  # Honeypot candidates are excluded/zeroed out

        scores_dict = {
            **core,
            "text_relevance": round(text_rel, 4),
            "behavioral": round(beh, 4),
            "final": round(final, 4),
            "is_honeypot": is_hp
        }

        # Build candidate view record
        prof = c.get("profile", {})
        signals = c.get("redrob_signals", {})
        
        reasoning = generate_reasoning(c, scores_dict)

        record = {
            "candidate_id": c["candidate_id"],
            "name": prof.get("anonymized_name", c["candidate_id"]),
            "title": prof.get("current_title", "N/A"),
            "company": prof.get("current_company", "N/A"),
            "industry": prof.get("current_industry", "N/A"),
            "location": prof.get("location", "N/A"),
            "country": prof.get("country", "N/A"),
            "years_of_experience": prof.get("years_of_experience", 0),
            "headline": prof.get("headline", ""),
            "summary": prof.get("summary", ""),
            "skills": [s.get("name") for s in c.get("skills", [])],
            "is_honeypot": is_hp,
            "scores": scores_dict,
            "reasoning": reasoning,
            "redrob_signals": {
                "open_to_work": signals.get("open_to_work_flag", False),
                "notice_period_days": signals.get("notice_period_days", 0),
                "recruiter_response_rate": signals.get("recruiter_response_rate", 0),
                "last_active_date": signals.get("last_active_date", "N/A"),
                "willing_to_relocate": signals.get("willing_to_relocate", False)
            },
            "raw": c
        }
        scored_list.append(record)

    # Sort candidates
    # Non-honeypots sorted descending by final score, honeypots placed at the bottom
    valid_candidates = [r for r in scored_list if not r["is_honeypot"]]
    valid_candidates.sort(key=lambda x: (-x["scores"]["final"], x["candidate_id"]))
    
    honeypot_candidates = [r for r in scored_list if r["is_honeypot"]]
    honeypot_candidates.sort(key=lambda x: x["candidate_id"])

    ranked = valid_candidates + honeypot_candidates

    # Attach rank
    for rank_idx, record in enumerate(valid_candidates, start=1):
        record["rank"] = rank_idx
    for record in honeypot_candidates:
        record["rank"] = -1  # Disqualified

    # Compute Statistics
    top_scores = [r["scores"]["final"] for r in valid_candidates[:100]] if valid_candidates else [0]
    avg_score = sum(top_scores) / max(len(top_scores), 1)
    
    # Title distribution in top 100
    titles_count = {}
    for r in valid_candidates[:100]:
        t = r["title"]
        titles_count[t] = titles_count.get(t, 0) + 1
        
    country_count = {}
    for r in valid_candidates[:100]:
        c = r["country"]
        country_count[c] = country_count.get(c, 0) + 1

    stats = {
        "total_candidates": total_count,
        "valid_candidates": len(valid_candidates),
        "honeypots_count": honeypot_count,
        "top_score": top_scores[0] if top_scores else 0,
        "cutoff_score_100": top_scores[-1] if len(top_scores) >= 100 else top_scores[-1] if top_scores else 0,
        "avg_top100_score": round(avg_score, 4),
        "top_titles": titles_count,
        "top_countries": country_count,
        "execution_time_sec": round(time.time() - t0, 2)
    }

    CACHE["scored_candidates"] = scored_list
    CACHE["ranked_list"] = ranked
    CACHE["stats"] = stats
    CACHE["last_computed"] = time.time()
    print(f"[Pipeline] Completed ranking in {stats['execution_time_sec']}s. Honeypots flagged: {honeypot_count}")
    return stats


class APIHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler providing REST API and static file serving."""

    def _set_headers(self, status=200, content_type="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_OPTIONS(self):
        self._set_headers(204)

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)

        # API Endpoints
        if path == "/api/health":
            self._set_headers(200)
            res = {
                "status": "online",
                "dataset_path": CACHE["data_path"],
                "candidates_loaded": len(CACHE["candidates"]),
                "last_computed": CACHE["last_computed"]
            }
            self.wfile.write(json.dumps(res).encode("utf-8"))

        elif path == "/api/stats":
            self._set_headers(200)
            self.wfile.write(json.dumps(CACHE["stats"]).encode("utf-8"))

        elif path == "/api/config":
            self._set_headers(200)
            self.wfile.write(json.dumps(CACHE["custom_config"]).encode("utf-8"))

        elif path == "/api/candidates":
            self._handle_get_candidates(query)

        elif path.startswith("/api/candidates/"):
            cid = path.split("/api/candidates/")[1]
            self._handle_get_candidate_by_id(cid)

        elif path == "/api/honeypots":
            self._set_headers(200)
            honeypots = [c for c in CACHE["scored_candidates"] if c["is_honeypot"]]
            self.wfile.write(json.dumps({
                "count": len(honeypots),
                "candidates": honeypots
            }).encode("utf-8"))

        elif path == "/api/export":
            self._handle_export_csv()

        else:
            # Serve Static Files
            self._serve_static(path)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception:
            body = {}

        if path in ("/api/rank", "/api/config"):
            # Update custom weights/config & re-run pipeline
            for k in ["CORE_FIT_WEIGHT", "TEXT_RELEVANCE_WEIGHT", "TITLE_WEIGHT", 
                      "SKILLS_WEIGHT", "CAREER_WEIGHT", "EXPERIENCE_WEIGHT", 
                      "LOCATION_WEIGHT", "EDUCATION_WEIGHT", "JD_QUERY"]:
                if k in body:
                    CACHE["custom_config"][k] = body[k]

            stats = run_pipeline()
            self._set_headers(200)
            res = {
                "message": "Ranking pipeline re-executed successfully",
                "stats": stats,
                "config": CACHE["custom_config"]
            }
            self.wfile.write(json.dumps(res).encode("utf-8"))
        else:
            self._set_headers(404)
            self.wfile.write(json.dumps({"error": "Endpoint not found"}).encode("utf-8"))

    def _handle_get_candidates(self, query):
        search = query.get("search", [""])[0].lower().strip()
        title_filter = query.get("title", [""])[0].lower().strip()
        country_filter = query.get("country", [""])[0].lower().strip()
        min_exp = float(query.get("min_exp", [0])[0])
        max_exp = float(query.get("max_exp", [100])[0])
        honeypot_only = query.get("honeypot_only", ["false"])[0].lower() == "true"
        top_only = query.get("top_only", ["false"])[0].lower() == "true"
        
        page = int(query.get("page", [1])[0])
        page_size = int(query.get("page_size", [20])[0])

        candidates = CACHE["ranked_list"]

        # Filter logic
        filtered = []
        for c in candidates:
            if honeypot_only and not c["is_honeypot"]:
                continue
            if not honeypot_only and c["is_honeypot"] and not query.get("include_honeypot", ["false"])[0].lower() == "true":
                continue
            if top_only and (c["rank"] < 1 or c["rank"] > 100):
                continue
            if min_exp > 0 and c["years_of_experience"] < min_exp:
                continue
            if max_exp < 100 and c["years_of_experience"] > max_exp:
                continue
            if country_filter and country_filter not in c["country"].lower():
                continue
            if title_filter and title_filter not in c["title"].lower():
                continue
            if search:
                text_to_check = f"{c['name']} {c['title']} {c['company']} {c['location']} {' '.join(c['skills'])} {c['reasoning']}".lower()
                if search not in text_to_check:
                    continue
            filtered.append(c)

        # Pagination
        total_items = len(filtered)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paged_items = filtered[start_idx:end_idx]

        # Strip heavy raw data for list endpoint to keep response lightweight
        lightweight_items = []
        for item in paged_items:
            clean_item = dict(item)
            clean_item.pop("raw", None)
            lightweight_items.append(clean_item)

        response = {
            "total": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": max((total_items + page_size - 1) // page_size, 1),
            "candidates": lightweight_items
        }

        self._set_headers(200)
        self.wfile.write(json.dumps(response).encode("utf-8"))

    def _handle_get_candidate_by_id(self, candidate_id):
        for c in CACHE["scored_candidates"]:
            if c["candidate_id"] == candidate_id:
                self._set_headers(200)
                self.wfile.write(json.dumps(c).encode("utf-8"))
                return
        self._set_headers(404)
        self.wfile.write(json.dumps({"error": f"Candidate {candidate_id} not found"}).encode("utf-8"))

    def _handle_export_csv(self):
        valid_top100 = [c for c in CACHE["ranked_list"] if not c["is_honeypot"]][:100]
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for c in valid_top100:
            writer.writerow([c["candidate_id"], c["rank"], f"{c['scores']['final']:.4f}", c["reasoning"]])

        csv_content = output.getvalue()
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", 'attachment; filename="submission.csv"')
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(csv_content.encode("utf-8"))

    def _serve_static(self, req_path):
        static_dir = Path(__file__).parent / "static"
        if req_path in ("/", ""):
            file_path = static_dir / "index.html"
        else:
            file_path = static_dir / req_path.lstrip("/")

        if not file_path.exists() or file_path.is_dir():
            file_path = static_dir / "index.html"

        if not file_path.exists():
            self._set_headers(404, "text/plain")
            self.wfile.write(b"404 Not Found")
            return

        ext = file_path.suffix.lower()
        content_types = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
            ".json": "application/json",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".svg": "image/svg+xml"
        }
        content_type = content_types.get(ext, "application/octet-stream")

        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self._set_headers(200, content_type)
            self.wfile.write(content)
        except Exception as e:
            self._set_headers(500, "text/plain")
            self.wfile.write(f"500 Internal Error: {e}".encode("utf-8"))


def main():
    default_port = int(os.environ.get("PORT", 8000))
    parser = argparse.ArgumentParser(description="HR Discovery & Ranking Backend API Server")
    parser.add_argument("--port", type=int, default=default_port, help="Port to listen on (default: 8000 or PORT env)")
    parser.add_argument("--data", type=str, default=None, help="Path to candidates dataset file")
    args = parser.parse_args()

    # Pre-run pipeline
    run_pipeline(args.data)

    server_address = ("", args.port)
    httpd = HTTPServer(server_address, APIHandler)
    print(f"\n===========================================================")
    print(f" HR Talent Discovery & Ranking Server is running!")
    print(f" Dashboard UI & API: http://localhost:{args.port}")
    print(f" REST API Health:     http://localhost:{args.port}/api/health")
    print(f" REST Candidates:     http://localhost:{args.port}/api/candidates")
    print(f"===========================================================\n")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        httpd.server_close()


if __name__ == "__main__":
    main()
