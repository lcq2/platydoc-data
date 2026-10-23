"""Standalone producer paths; source checkouts are read-only inputs."""
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_ROOT = PROJECT_ROOT / "xnu"
# Historical proof scripts use DOCS only as an output-protection boundary.
DOCS = PROJECT_ROOT / "bindings"
def require_source():
    for name in ("osfmk", "bsd", "iokit", "APPLE_LICENSE"):
        if not (SOURCE_ROOT / name).exists():
            raise RuntimeError("Initialize source submodules with git submodule update --init")
