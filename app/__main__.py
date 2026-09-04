"""Run the GUI without arguments, or the CNC CLI when a command is supplied."""

import sys

if __name__ == "__main__":
    if len(sys.argv) > 1:
        from app.cli import main

        raise SystemExit(main(sys.argv[1:]))

    from app.application import run

    raise SystemExit(run())
