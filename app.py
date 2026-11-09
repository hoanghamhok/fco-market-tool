"""FCO Market desktop entry point."""

import multiprocessing
import os
from pathlib import Path
import sys

if __name__ == "__main__":
    multiprocessing.freeze_support()
    # Windowed bundles have no console streams. The JS bridge must still be
    # able to log validation exceptions before rejecting its Promise.
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")
    if "--apply-update" in sys.argv:
        from fco.updater import run_helper

        sys.exit(run_helper())
    if "--update-probe" in sys.argv:
        from fco.updater import run_probe

        index = sys.argv.index("--update-probe")
        if len(sys.argv) != index + 2:
            sys.exit(1)
        sys.exit(run_probe(Path(sys.argv[index + 1])))
    from fco.desktop import enable_dpi_awareness

    enable_dpi_awareness()
    if "--self-test" in sys.argv:
        from fco.diagnostics.self_test import run_self_test

        index = sys.argv.index("--self-test")
        report = (
            Path(sys.argv[index + 1])
            if len(sys.argv) > index + 1
            else Path.cwd() / "reports/self-test.json"
        )
        sys.exit(run_self_test(report))
    from fco.web_app import run

    run()
