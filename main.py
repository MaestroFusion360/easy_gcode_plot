"""Easy G-code Plot entry point."""

import argparse
import sys
from pathlib import Path

from app.application import run

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--simulate":
        parser = argparse.ArgumentParser(description="Launch GUI stock-removal simulation")
        parser.add_argument("--simulate", required=True, type=Path, metavar="FILE")
        parser.add_argument("--bundle", type=Path, default=None)
        parser.add_argument("--lang", choices=("fanuc_turn", "fanuc_mill"), required=True)
        options = parser.parse_args()
        bundle = None
        if options.bundle is not None:
            from app.integration.minicad_bundle import read_bundle

            bundle = read_bundle(options.bundle)
            if bundle.nc.resolve() != options.simulate.resolve():
                parser.error("NC file must match bundle manifest")
        raise SystemExit(run(startup_file=options.simulate, simulate=True, language=options.lang, bundle=bundle))
    raise SystemExit(run())
