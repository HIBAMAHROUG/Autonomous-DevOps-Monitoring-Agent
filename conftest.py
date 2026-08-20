"""
Exécuté par pytest avant la collecte de tout fichier de test.

Nécessaire pour isoler les tests de la vraie base d'audit SQLite
(storage/audit_store.py fige AUDIT_DB_PATH au moment de son import).
"""

import os
import tempfile


os.environ.setdefault(
    "AUDIT_DB_PATH",
    os.path.join(
        tempfile.mkdtemp(),
        "test_audit.sqlite3",
    ),
)

os.environ.setdefault("API_KEY", "test-key")
