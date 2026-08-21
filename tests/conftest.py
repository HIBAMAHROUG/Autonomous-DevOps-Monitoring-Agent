import sys
from pathlib import Path

# Add the project root to Python path
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

# Also add the remediation directory
remediation_dir = root_dir / "remediation"
if remediation_dir.exists():
    sys.path.insert(0, str(remediation_dir))
