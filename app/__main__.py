"""Allow running the application with ``python -m app``."""

from app.application import run

if __name__ == "__main__":
    raise SystemExit(run())
