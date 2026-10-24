"""
TrueFit-AI Database Layer
Provides unified relational storage for PostgreSQL and SQLite.

Supports:
- PostgreSQL (Production / Cloud: Render, Supabase, Neon, AWS RDS, Docker)
- SQLite (Local development, zero-config embedded fallback: truefit.db)
"""

import os
import sys
import json
import time
import sqlite3
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Optional psycopg2 import for PostgreSQL
POSTGRES_AVAILABLE = False
try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    POSTGRES_AVAILABLE = True
except ImportError:
    try:
        import psycopg as psycopg2
        POSTGRES_AVAILABLE = True
    except ImportError:
        POSTGRES_AVAILABLE = False


class DatabaseManager:
    """
    Unified Database Manager supporting PostgreSQL and SQLite with identical schemas.
    """

    def __init__(self, db_url=None):
        self.raw_url = db_url or os.environ.get("DATABASE_URL", "")
        self.engine_type = "sqlite"
        self.db_path = None
        self.pg_conn_info = None
        self.pg_pool = None
        self._init_connection()
        self.create_tables()

    def _init_connection(self):
        """Detect and initialize either PostgreSQL or SQLite connection."""
        url = self.raw_url.strip()

        # Handle Render/Heroku legacy postgres:// URL prefix
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)

        if url.startswith("postgresql://"):
            if not POSTGRES_AVAILABLE:
                print("[Database Warning] DATABASE_URL provided for PostgreSQL, but 'psycopg2' is not installed.")
                print("                  Falling back to SQLite (truefit.db). Run: pip install psycopg2-binary")
                self._setup_sqlite()
                return

            try:
                # Test connection to PostgreSQL
                conn = psycopg2.connect(url, connect_timeout=5)
                conn.close()
                self.engine_type = "postgresql"
                self.pg_conn_info = url
                # Create a simple connection pool (min 1, max 10)
                try:
                    self.pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, url)
                except Exception:
                    self.pg_pool = None
                parsed = urlparse(url)
                print(f"[Database] Successfully connected to PostgreSQL: {parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}")
                return
            except Exception as e:
                print(f"[Database Warning] Failed to connect to PostgreSQL at {url} ({e}).")
                print("                  Falling back to local SQLite (truefit.db).")
                self._setup_sqlite()
                return

        # Default: SQLite
        self._setup_sqlite()

    def _setup_sqlite(self):
        self.engine_type = "sqlite"
        # On serverless platforms like Vercel or AWS Lambda, root directory is read-only
        if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            self.db_path = Path("/tmp") / "truefit.db"
        else:
            base_dir = Path(__file__).parent
            self.db_path = base_dir / "truefit.db"
        print(f"[Database] Using SQLite database: {self.db_path}")

    def get_connection(self):
        """Obtain a database connection depending on active engine."""
        if self.engine_type == "postgresql":
            if self.pg_pool:
                return self.pg_pool.getconn()
            return psycopg2.connect(self.pg_conn_info)
        else:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30.0)
            conn.row_factory = sqlite3.Row
            return conn

    def release_connection(self, conn):
        """Release or close connection."""
        if self.engine_type == "postgresql":
            if self.pg_pool:
                self.pg_pool.putconn(conn)
            else:
                conn.close()
        else:
            conn.close()

    def _adapt_sql(self, sql):
        """Convert standard ? parameter placeholders to %s for PostgreSQL."""
        if self.engine_type == "postgresql":
            # Replace '?' with '%s' when not inside quotes
            return sql.replace("?", "%s")
        return sql

    def execute_query(self, sql, params=(), commit=False):
        """Execute a query and optionally commit."""
        conn = self.get_connection()
        adapted_sql = self._adapt_sql(sql)
        try:
            cur = conn.cursor()
            cur.execute(adapted_sql, params)
            if commit:
                conn.commit()
            return conn, cur
        except Exception as e:
            if commit:
                try:
                    conn.rollback()
                except Exception:
                    pass
            self.release_connection(conn)
            raise e

    def execute_non_query(self, sql, params=()):
        """Execute INSERT / UPDATE / DELETE and commit."""
        conn = self.get_connection()
        adapted_sql = self._adapt_sql(sql)
        try:
            cur = conn.cursor()
            cur.execute(adapted_sql, params)
            conn.commit()
            last_id = getattr(cur, "lastrowid", None)
            row_count = cur.rowcount
            cur.close()
            return row_count, last_id
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise e
        finally:
            self.release_connection(conn)

    def execute_many(self, sql, seq_of_params):
        """Execute batch insert/update."""
        if not seq_of_params:
            return 0
        conn = self.get_connection()
        adapted_sql = self._adapt_sql(sql)
        try:
            cur = conn.cursor()
            cur.executemany(adapted_sql, seq_of_params)
            conn.commit()
            row_count = cur.rowcount
            cur.close()
            return row_count
        except Exception as e:
            try:
                conn.rollback()
            except Exception:
                pass
            raise e
        finally:
            self.release_connection(conn)

    def fetch_one(self, sql, params=()):
        """Fetch a single record as a dict."""
        conn = self.get_connection()
        adapted_sql = self._adapt_sql(sql)
        try:
            cur = conn.cursor()
            cur.execute(adapted_sql, params)
            row = cur.fetchone()
            if not row:
                cur.close()
                return None
            
            # Format row as dict
            if self.engine_type == "postgresql":
                colnames = [desc[0] for desc in cur.description]
                res = dict(zip(colnames, row))
            else:
                res = dict(row)
            cur.close()
            return res
        finally:
            self.release_connection(conn)

    def fetch_all(self, sql, params=()):
        """Fetch all records as a list of dicts."""
        conn = self.get_connection()
        adapted_sql = self._adapt_sql(sql)
        try:
            cur = conn.cursor()
            cur.execute(adapted_sql, params)
            rows = cur.fetchall()
            if not rows:
                cur.close()
                return []
            
            if self.engine_type == "postgresql":
                colnames = [desc[0] for desc in cur.description]
                res = [dict(zip(colnames, r)) for r in rows]
            else:
                res = [dict(r) for r in rows]
            cur.close()
            return res
        finally:
            self.release_connection(conn)

    def create_tables(self):
        """Create relational tables and indexes if they do not already exist."""
        auto_id = "SERIAL PRIMARY KEY" if self.engine_type == "postgresql" else "INTEGER PRIMARY KEY AUTOINCREMENT"
        timestamp_default = "CURRENT_TIMESTAMP"

        # 1. Candidates table
        self.execute_non_query(f"""
            CREATE TABLE IF NOT EXISTS candidates (
                candidate_id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(255),
                title VARCHAR(255),
                company VARCHAR(255),
                industry VARCHAR(128),
                location VARCHAR(128),
                country VARCHAR(128),
                years_of_experience REAL DEFAULT 0.0,
                headline TEXT,
                summary TEXT,
                skills_json TEXT,
                career_history_json TEXT,
                education_json TEXT,
                redrob_signals_json TEXT,
                raw_json TEXT,
                created_at TIMESTAMP DEFAULT {timestamp_default},
                updated_at TIMESTAMP DEFAULT {timestamp_default}
            );
        """)

        # 2. Scoring Runs table
        self.execute_non_query(f"""
            CREATE TABLE IF NOT EXISTS scoring_runs (
                run_id VARCHAR(64) PRIMARY KEY,
                created_at TIMESTAMP DEFAULT {timestamp_default},
                dataset_source VARCHAR(255),
                total_candidates INTEGER DEFAULT 0,
                valid_candidates INTEGER DEFAULT 0,
                honeypots_count INTEGER DEFAULT 0,
                top_score REAL DEFAULT 0.0,
                cutoff_score_100 REAL DEFAULT 0.0,
                avg_top100_score REAL DEFAULT 0.0,
                weights_json TEXT,
                top_titles_json TEXT,
                top_countries_json TEXT,
                execution_time_sec REAL DEFAULT 0.0,
                is_active INTEGER DEFAULT 1
            );
        """)

        # 3. Candidate Scores table
        self.execute_non_query(f"""
            CREATE TABLE IF NOT EXISTS candidate_scores (
                id {auto_id},
                run_id VARCHAR(64) NOT NULL,
                candidate_id VARCHAR(64) NOT NULL,
                rank INTEGER DEFAULT -1,
                final_score REAL DEFAULT 0.0,
                core_fit_score REAL DEFAULT 0.0,
                text_relevance_score REAL DEFAULT 0.0,
                behavioral_modifier REAL DEFAULT 1.0,
                title_score REAL DEFAULT 0.0,
                skills_score REAL DEFAULT 0.0,
                career_score REAL DEFAULT 0.0,
                experience_score REAL DEFAULT 0.0,
                location_score REAL DEFAULT 0.0,
                education_score REAL DEFAULT 0.0,
                is_honeypot INTEGER DEFAULT 0,
                reasoning TEXT,
                created_at TIMESTAMP DEFAULT {timestamp_default}
            );
        """)

        # 4. Shortlists table (Recruiter bookmarks, notes, and hiring stages)
        self.execute_non_query(f"""
            CREATE TABLE IF NOT EXISTS shortlists (
                id {auto_id},
                candidate_id VARCHAR(64) UNIQUE NOT NULL,
                status VARCHAR(32) DEFAULT 'shortlisted',
                starred INTEGER DEFAULT 1,
                recruiter_notes TEXT,
                tags TEXT,
                updated_at TIMESTAMP DEFAULT {timestamp_default}
            );
        """)

        # 5. Audit Activity Logs
        self.execute_non_query(f"""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id {auto_id},
                action VARCHAR(64) NOT NULL,
                details TEXT,
                timestamp TIMESTAMP DEFAULT {timestamp_default}
            );
        """)

        # Create indexes for high performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_candidates_title ON candidates(title);",
            "CREATE INDEX IF NOT EXISTS idx_candidates_country ON candidates(country);",
            "CREATE INDEX IF NOT EXISTS idx_candidates_exp ON candidates(years_of_experience);",
            "CREATE INDEX IF NOT EXISTS idx_runs_active ON scoring_runs(is_active);",
            "CREATE INDEX IF NOT EXISTS idx_scores_run_rank ON candidate_scores(run_id, rank);",
            "CREATE INDEX IF NOT EXISTS idx_scores_run_final ON candidate_scores(run_id, final_score DESC);",
            "CREATE INDEX IF NOT EXISTS idx_scores_candidate ON candidate_scores(candidate_id);",
            "CREATE INDEX IF NOT EXISTS idx_scores_honeypot ON candidate_scores(is_honeypot);",
            "CREATE INDEX IF NOT EXISTS idx_shortlists_candidate ON shortlists(candidate_id);",
            "CREATE INDEX IF NOT EXISTS idx_shortlists_status ON shortlists(status);"
        ]
        for idx in indexes:
            try:
                self.execute_non_query(idx)
            except Exception:
                pass

    # =========================================================================
    # Candidate Operations
    # =========================================================================

    def save_candidates_batch(self, candidates):
        """Batch insert or update candidate profiles."""
        if not candidates:
            return 0

        sql = """
            INSERT INTO candidates (
                candidate_id, name, title, company, industry, location, country,
                years_of_experience, headline, summary, skills_json, career_history_json,
                education_json, redrob_signals_json, raw_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT (candidate_id) DO UPDATE SET
                name = EXCLUDED.name,
                title = EXCLUDED.title,
                company = EXCLUDED.company,
                industry = EXCLUDED.industry,
                location = EXCLUDED.location,
                country = EXCLUDED.country,
                years_of_experience = EXCLUDED.years_of_experience,
                headline = EXCLUDED.headline,
                summary = EXCLUDED.summary,
                skills_json = EXCLUDED.skills_json,
                career_history_json = EXCLUDED.career_history_json,
                education_json = EXCLUDED.education_json,
                redrob_signals_json = EXCLUDED.redrob_signals_json,
                raw_json = EXCLUDED.raw_json,
                updated_at = CURRENT_TIMESTAMP
        """

        params_list = []
        for c in candidates:
            prof = c.get("profile", {})
            params_list.append((
                c["candidate_id"],
                prof.get("anonymized_name", c["candidate_id"]),
                prof.get("current_title", "N/A"),
                prof.get("current_company", "N/A"),
                prof.get("current_industry", "N/A"),
                prof.get("location", "N/A"),
                prof.get("country", "N/A"),
                float(prof.get("years_of_experience", 0.0) or 0.0),
                prof.get("headline", ""),
                prof.get("summary", ""),
                json.dumps(c.get("skills", [])),
                json.dumps(c.get("career_history", [])),
                json.dumps(c.get("education", [])),
                json.dumps(c.get("redrob_signals", {})),
                json.dumps(c)
            ))

        self.execute_many(sql, params_list)
        return len(params_list)

    def get_candidate_count(self):
        """Return total number of candidates in database."""
        row = self.fetch_one("SELECT COUNT(*) as cnt FROM candidates")
        return row["cnt"] if row else 0

    def get_all_raw_candidates(self):
        """Fetch all candidates from database as list of original JSON dicts."""
        rows = self.fetch_all("SELECT raw_json FROM candidates")
        res = []
        for r in rows:
            try:
                res.append(json.loads(r["raw_json"]))
            except Exception:
                pass
        return res

    # =========================================================================
    # Scoring Run Operations
    # =========================================================================

    def save_scoring_run(self, run_id, stats, weights_config, scored_records, dataset_source="default"):
        """Save a complete scoring run and all candidate scores atomically."""
        # 1. Deactivate older runs
        self.execute_non_query("UPDATE scoring_runs SET is_active = 0")

        # 2. Insert new scoring run record
        run_sql = """
            INSERT INTO scoring_runs (
                run_id, created_at, dataset_source, total_candidates, valid_candidates,
                honeypots_count, top_score, cutoff_score_100, avg_top100_score,
                weights_json, top_titles_json, top_countries_json, execution_time_sec, is_active
            ) VALUES (?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
        """
        self.execute_non_query(run_sql, (
            run_id,
            dataset_source,
            stats.get("total_candidates", len(scored_records)),
            stats.get("valid_candidates", 0),
            stats.get("honeypots_count", 0),
            stats.get("top_score", 0.0),
            stats.get("cutoff_score_100", 0.0),
            stats.get("avg_top100_score", 0.0),
            json.dumps(weights_config),
            json.dumps(stats.get("top_titles", {})),
            json.dumps(stats.get("top_countries", {})),
            stats.get("execution_time_sec", 0.0)
        ))

        # 3. Batch insert candidate scores
        scores_sql = """
            INSERT INTO candidate_scores (
                run_id, candidate_id, rank, final_score, core_fit_score,
                text_relevance_score, behavioral_modifier, title_score, skills_score,
                career_score, experience_score, location_score, education_score,
                is_honeypot, reasoning, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """
        score_params = []
        for r in scored_records:
            sc = r.get("scores", {})
            score_params.append((
                run_id,
                r["candidate_id"],
                r.get("rank", -1),
                float(sc.get("final", 0.0)),
                float(sc.get("core_fit", 0.0)),
                float(sc.get("text_relevance", 0.0)),
                float(sc.get("behavioral", 1.0)),
                float(sc.get("title", 0.0)),
                float(sc.get("skills", 0.0)),
                float(sc.get("career", 0.0)),
                float(sc.get("experience", 0.0)),
                float(sc.get("location", 0.0)),
                float(sc.get("education", 0.0)),
                1 if r.get("is_honeypot") else 0,
                r.get("reasoning", "")
            ))

        self.execute_many(scores_sql, score_params)
        self.log_activity("scoring_run_created", f"Run {run_id} created with {len(scored_records)} candidates")
        return run_id

    def get_active_run(self):
        """Fetch active scoring run metadata."""
        row = self.fetch_one("SELECT * FROM scoring_runs WHERE is_active = 1 ORDER BY created_at DESC LIMIT 1")
        if not row:
            # Fallback to the latest run if none is explicitly marked active
            row = self.fetch_one("SELECT * FROM scoring_runs ORDER BY created_at DESC LIMIT 1")
        if row:
            for k in ("weights_json", "top_titles_json", "top_countries_json"):
                if row.get(k):
                    try:
                        row[k] = json.loads(row[k])
                    except Exception:
                        pass
        return row

    def get_all_runs(self):
        """Fetch list of all past scoring runs."""
        rows = self.fetch_all("SELECT run_id, created_at, dataset_source, total_candidates, valid_candidates, honeypots_count, top_score, cutoff_score_100, avg_top100_score, execution_time_sec, is_active FROM scoring_runs ORDER BY created_at DESC LIMIT 50")
        return rows

    def activate_run(self, run_id):
        """Set a specific scoring run as active."""
        self.execute_non_query("UPDATE scoring_runs SET is_active = 0")
        row_count, _ = self.execute_non_query("UPDATE scoring_runs SET is_active = 1 WHERE run_id = ?", (run_id,))
        self.log_activity("run_activated", f"Scoring run {run_id} activated")
        return row_count > 0

    # =========================================================================
    # Candidate Search, Filtering & Pagination
    # =========================================================================

    def query_candidates(self, run_id=None, page=1, page_size=20, search="",
                         title="", country="", min_exp=0, max_exp=100,
                         honeypot_only=False, top_only=False, include_honeypot=False,
                         starred_only=False):
        """
        High-performance indexed query joining candidates, scores, and shortlists.
        """
        if not run_id:
            active = self.get_active_run()
            run_id = active["run_id"] if active else ""

        conditions = ["s.run_id = ?"]
        params = [run_id]

        if honeypot_only:
            conditions.append("s.is_honeypot = 1")
        elif not include_honeypot:
            conditions.append("s.is_honeypot = 0")

        if top_only:
            conditions.append("s.rank >= 1 AND s.rank <= 100")

        if min_exp > 0:
            conditions.append("c.years_of_experience >= ?")
            params.append(min_exp)

        if max_exp < 100:
            conditions.append("c.years_of_experience <= ?")
            params.append(max_exp)

        if country:
            conditions.append("LOWER(c.country) LIKE ?")
            params.append(f"%{country.lower().strip()}%")

        if title:
            conditions.append("LOWER(c.title) LIKE ?")
            params.append(f"%{title.lower().strip()}%")

        if starred_only:
            conditions.append("COALESCE(sh.starred, 0) = 1")

        if search:
            s = f"%{search.lower().strip()}%"
            conditions.append("""(
                LOWER(c.name) LIKE ? OR
                LOWER(c.title) LIKE ? OR
                LOWER(c.company) LIKE ? OR
                LOWER(c.location) LIKE ? OR
                LOWER(c.skills_json) LIKE ? OR
                LOWER(s.reasoning) LIKE ?
            )""")
            params.extend([s, s, s, s, s, s])

        where_clause = " WHERE " + " AND ".join(conditions)

        # 1. Count total matching
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM candidate_scores s
            JOIN candidates c ON c.candidate_id = s.candidate_id
            LEFT JOIN shortlists sh ON sh.candidate_id = c.candidate_id
            {where_clause}
        """
        count_row = self.fetch_one(count_sql, tuple(params))
        total_items = count_row["total"] if count_row else 0

        # 2. Fetch page items
        offset = (page - 1) * page_size
        items_sql = f"""
            SELECT 
                c.candidate_id,
                c.name,
                c.title,
                c.company,
                c.industry,
                c.location,
                c.country,
                c.years_of_experience,
                c.headline,
                c.summary,
                c.skills_json,
                c.redrob_signals_json,
                s.rank,
                s.final_score,
                s.core_fit_score,
                s.text_relevance_score,
                s.behavioral_modifier,
                s.title_score,
                s.skills_score,
                s.career_score,
                s.experience_score,
                s.location_score,
                s.education_score,
                s.is_honeypot,
                s.reasoning,
                COALESCE(sh.starred, 0) as is_starred,
                sh.status as shortlist_status,
                sh.recruiter_notes
            FROM candidate_scores s
            JOIN candidates c ON c.candidate_id = s.candidate_id
            LEFT JOIN shortlists sh ON sh.candidate_id = c.candidate_id
            {where_clause}
            ORDER BY 
                CASE WHEN s.is_honeypot = 1 THEN 1 ELSE 0 END ASC,
                s.final_score DESC,
                c.candidate_id ASC
            LIMIT ? OFFSET ?
        """
        page_params = list(params) + [page_size, offset]
        rows = self.fetch_all(items_sql, tuple(page_params))

        # Format items for frontend
        candidates = []
        for r in rows:
            skills = []
            try:
                skills_data = json.loads(r.get("skills_json", "[]"))
                skills = [sk.get("name") if isinstance(sk, dict) else str(sk) for sk in skills_data]
            except Exception:
                pass

            signals = {}
            try:
                signals = json.loads(r.get("redrob_signals_json", "{}"))
            except Exception:
                pass

            candidates.append({
                "candidate_id": r["candidate_id"],
                "name": r["name"],
                "title": r["title"],
                "company": r["company"],
                "industry": r["industry"],
                "location": r["location"],
                "country": r["country"],
                "years_of_experience": r["years_of_experience"],
                "headline": r["headline"],
                "summary": r["summary"],
                "skills": skills,
                "rank": r["rank"],
                "is_honeypot": bool(r["is_honeypot"]),
                "reasoning": r["reasoning"],
                "is_starred": bool(r["is_starred"]),
                "shortlist_status": r["shortlist_status"] or "none",
                "recruiter_notes": r["recruiter_notes"] or "",
                "scores": {
                    "final": round(r["final_score"], 4),
                    "core_fit": round(r["core_fit_score"], 4),
                    "text_relevance": round(r["text_relevance_score"], 4),
                    "behavioral": round(r["behavioral_modifier"], 4),
                    "title": round(r["title_score"], 4),
                    "skills": round(r["skills_score"], 4),
                    "career": round(r["career_score"], 4),
                    "experience": round(r["experience_score"], 4),
                    "location": round(r["location_score"], 4),
                    "education": round(r["education_score"], 4),
                    "is_honeypot": bool(r["is_honeypot"])
                },
                "redrob_signals": {
                    "open_to_work": signals.get("open_to_work_flag", False),
                    "notice_period_days": signals.get("notice_period_days", 0),
                    "recruiter_response_rate": signals.get("recruiter_response_rate", 0),
                    "last_active_date": signals.get("last_active_date", "N/A"),
                    "willing_to_relocate": signals.get("willing_to_relocate", False)
                }
            })

        total_pages = max((total_items + page_size - 1) // page_size, 1)
        return {
            "total": total_items,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "candidates": candidates
        }

    def get_candidate_detail(self, candidate_id, run_id=None):
        """Fetch candidate deep-dive record including raw JSON, scores, and recruiter notes."""
        if not run_id:
            active = self.get_active_run()
            run_id = active["run_id"] if active else ""

        sql = """
            SELECT 
                c.*,
                s.rank,
                s.final_score,
                s.core_fit_score,
                s.text_relevance_score,
                s.behavioral_modifier,
                s.title_score,
                s.skills_score,
                s.career_score,
                s.experience_score,
                s.location_score,
                s.education_score,
                s.is_honeypot,
                s.reasoning,
                COALESCE(sh.starred, 0) as is_starred,
                sh.status as shortlist_status,
                sh.recruiter_notes
            FROM candidates c
            LEFT JOIN candidate_scores s ON s.candidate_id = c.candidate_id AND s.run_id = ?
            LEFT JOIN shortlists sh ON sh.candidate_id = c.candidate_id
            WHERE c.candidate_id = ?
        """
        r = self.fetch_one(sql, (run_id, candidate_id))
        if not r:
            return None

        raw = {}
        try:
            raw = json.loads(r.get("raw_json", "{}"))
        except Exception:
            pass

        skills = []
        try:
            skills_data = json.loads(r.get("skills_json", "[]"))
            skills = [sk.get("name") if isinstance(sk, dict) else str(sk) for sk in skills_data]
        except Exception:
            pass

        signals = {}
        try:
            signals = json.loads(r.get("redrob_signals_json", "{}"))
        except Exception:
            pass

        return {
            "candidate_id": r["candidate_id"],
            "name": r["name"],
            "title": r["title"],
            "company": r["company"],
            "industry": r["industry"],
            "location": r["location"],
            "country": r["country"],
            "years_of_experience": r["years_of_experience"],
            "headline": r["headline"],
            "summary": r["summary"],
            "skills": skills,
            "rank": r.get("rank", -1),
            "is_honeypot": bool(r.get("is_honeypot", 0)),
            "reasoning": r.get("reasoning", ""),
            "is_starred": bool(r.get("is_starred", 0)),
            "shortlist_status": r.get("shortlist_status") or "none",
            "recruiter_notes": r.get("recruiter_notes") or "",
            "scores": {
                "final": round(r.get("final_score") or 0.0, 4),
                "core_fit": round(r.get("core_fit_score") or 0.0, 4),
                "text_relevance": round(r.get("text_relevance_score") or 0.0, 4),
                "behavioral": round(r.get("behavioral_modifier") or 1.0, 4),
                "title": round(r.get("title_score") or 0.0, 4),
                "skills": round(r.get("skills_score") or 0.0, 4),
                "career": round(r.get("career_score") or 0.0, 4),
                "experience": round(r.get("experience_score") or 0.0, 4),
                "location": round(r.get("location_score") or 0.0, 4),
                "education": round(r.get("education_score") or 0.0, 4),
                "is_honeypot": bool(r.get("is_honeypot", 0))
            },
            "redrob_signals": {
                "open_to_work": signals.get("open_to_work_flag", False),
                "notice_period_days": signals.get("notice_period_days", 0),
                "recruiter_response_rate": signals.get("recruiter_response_rate", 0),
                "last_active_date": signals.get("last_active_date", "N/A"),
                "willing_to_relocate": signals.get("willing_to_relocate", False)
            },
            "raw": raw
        }

    def get_honeypots(self, run_id=None):
        """Fetch all honeypots for a run."""
        res = self.query_candidates(run_id=run_id, page=1, page_size=200, honeypot_only=True)
        return res.get("candidates", [])

    # =========================================================================
    # Recruiter Shortlisting & Bookmarks
    # =========================================================================

    def update_shortlist(self, candidate_id, status=None, starred=None, recruiter_notes=None):
        """Add or update candidate in recruiter shortlist/bookmarks."""
        current = self.fetch_one("SELECT * FROM shortlists WHERE candidate_id = ?", (candidate_id,))
        if not current:
            sql = """
                INSERT INTO shortlists (candidate_id, status, starred, recruiter_notes, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """
            self.execute_non_query(sql, (
                candidate_id,
                status or "shortlisted",
                1 if starred is True or starred is None else 0,
                recruiter_notes or ""
            ))
        else:
            new_status = status if status is not None else current["status"]
            new_starred = 1 if starred is True else (0 if starred is False else current["starred"])
            new_notes = recruiter_notes if recruiter_notes is not None else current["recruiter_notes"]

            sql = """
                UPDATE shortlists
                SET status = ?, starred = ?, recruiter_notes = ?, updated_at = CURRENT_TIMESTAMP
                WHERE candidate_id = ?
            """
            self.execute_non_query(sql, (new_status, new_starred, new_notes, candidate_id))

        self.log_activity("shortlist_updated", f"Candidate {candidate_id} updated: status={status}, starred={starred}")
        return self.fetch_one("SELECT * FROM shortlists WHERE candidate_id = ?", (candidate_id,))

    def get_all_shortlists(self):
        """Fetch all shortlisted candidates with notes."""
        sql = """
            SELECT 
                sh.*,
                c.name,
                c.title,
                c.company,
                c.location,
                c.country,
                c.years_of_experience
            FROM shortlists sh
            JOIN candidates c ON c.candidate_id = sh.candidate_id
            ORDER BY sh.updated_at DESC
        """
        return self.fetch_all(sql)

    # =========================================================================
    # Activity & Diagnostics
    # =========================================================================

    def log_activity(self, action, details):
        """Record an action in the audit logs."""
        try:
            self.execute_non_query(
                "INSERT INTO activity_logs (action, details, timestamp) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (action, str(details))
            )
        except Exception:
            pass

    def get_recent_activity(self, limit=20):
        """Fetch recent activity logs."""
        return self.fetch_all("SELECT * FROM activity_logs ORDER BY timestamp DESC LIMIT ?", (limit,))

    def get_db_status(self):
        """Return diagnostic dictionary of database status."""
        cand_count = self.get_candidate_count()
        run_count_row = self.fetch_one("SELECT COUNT(*) as cnt FROM scoring_runs")
        run_count = run_count_row["cnt"] if run_count_row else 0
        shortlist_count_row = self.fetch_one("SELECT COUNT(*) as cnt FROM shortlists")
        shortlist_count = shortlist_count_row["cnt"] if shortlist_count_row else 0
        active_run = self.get_active_run()

        return {
            "status": "connected",
            "engine": self.engine_type,
            "engine_display": "PostgreSQL" if self.engine_type == "postgresql" else "SQLite (Local File)",
            "database_url_configured": bool(self.raw_url),
            "db_target": str(self.db_path) if self.engine_type == "sqlite" else "PostgreSQL Server",
            "total_candidates": cand_count,
            "total_runs": run_count,
            "active_run_id": active_run["run_id"] if active_run else None,
            "shortlisted_count": shortlist_count
        }


# Global singleton database instance
_db_instance = None


def get_db(db_url=None):
    """Get or create singleton DatabaseManager instance."""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager(db_url)
    return _db_instance
