"""
Vercel Serverless Function entry point for TrueFit-AI REST API.
"""

import sys
from pathlib import Path

# Add project root directory to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server import APIHandler, run_pipeline
from database import get_db

# Initialize database on cold start
try:
    db = get_db()
    if db.get_candidate_count() == 0:
        run_pipeline()
except Exception as e:
    print(f"[Vercel Init Warning] Database init: {e}")

# Vercel looks for 'handler' or 'app' at the module level
handler = APIHandler
app = APIHandler
