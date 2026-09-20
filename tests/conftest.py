import sys
from pathlib import Path

# Add the project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Add each canonical source package so legacy test imports remain valid.
for source_dir in (
    root_dir / "src" / "ingestion",
    root_dir / "src" / "detection",
    root_dir / "src" / "diagnosis",
    root_dir / "src" / "orchestration",
    root_dir / "src" / "remediation",
    root_dir / "src" / "storage",
    root_dir / "src" / "api",
    root_dir / "src" / "common",
    root_dir / "infra",
):
    if source_dir.exists():
        sys.path.insert(0, str(source_dir))
