"""Create the SQLite turning-tool catalogue for the current auto model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.settings import tool_library_path  # noqa: E402  # pylint: disable=wrong-import-position
from app.tools.definitions import default_turning_library  # noqa: E402  # pylint: disable=wrong-import-position
from app.tools.library import KIND_TURNING, ToolLibrary  # noqa: E402  # pylint: disable=wrong-import-position


def generate_turning_tools(database: str | Path, *, force: bool = False) -> int:
    """Write every auto-supported turning tool into ``database``."""
    target = Path(database).resolve()
    tools = default_turning_library()
    with ToolLibrary(str(target)) as library:
        existing = library.tools_by_kind(KIND_TURNING)
        if existing and not force:
            raise RuntimeError(
                f"{target} already contains {len(existing)} turning tools; pass --force to replace them."
            )
        library.sync_kind(KIND_TURNING, tools)
    return len(tools)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "database",
        nargs="?",
        default=None,
        help="SQLite database path (default: the per-user database used by the application)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace all existing turning records; milling records are preserved.",
    )
    args = parser.parse_args(argv)
    database = Path(args.database).resolve() if args.database is not None else Path(tool_library_path())
    try:
        count = generate_turning_tools(database, force=args.force)
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"error: {exc}\n")
    print(f"Generated {count} turning tools in {database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
