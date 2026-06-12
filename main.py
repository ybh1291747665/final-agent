"""Entry point — delegates to final_agent.main:app."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from final_agent.main import app

if __name__ == "__main__":
    app()
