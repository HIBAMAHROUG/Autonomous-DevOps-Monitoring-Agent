"""
Exécuté par pytest avant la collecte de tout fichier de test.

Nécessaire pour isoler les tests de la vraie base d'audit SQLite
(storage/audit_store.py fige AUDIT_DB_PATH au moment de son import).
"""

import os
import sys
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).parent
for source_dir in (
    ROOT_DIR / "src" / "ingestion",
    ROOT_DIR / "src" / "detection",
    ROOT_DIR / "src" / "diagnosis",
    ROOT_DIR / "src" / "orchestration",
    ROOT_DIR / "src" / "remediation",
    ROOT_DIR / "src" / "storage",
    ROOT_DIR / "src" / "api",
    ROOT_DIR / "src" / "common",
    ROOT_DIR / "infra",
):
    sys.path.insert(0, str(source_dir))


os.environ.setdefault(
    "AUDIT_DB_PATH",
    os.path.join(
        tempfile.mkdtemp(),
        "test_audit.sqlite3",
    ),
)

os.environ.setdefault("API_KEY", "test-key")
