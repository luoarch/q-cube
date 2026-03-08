import subprocess
import sys
from pathlib import Path


def upgrade_head() -> None:
    root = Path(__file__).resolve().parents[2]
    alembic_ini = root / "alembic.ini"
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
        check=True,
        cwd=root,
    )


def main() -> None:
    upgrade_head()


if __name__ == "__main__":
    main()
