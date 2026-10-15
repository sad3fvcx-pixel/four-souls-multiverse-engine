# src/fsme/__main__.py

"""
``python -m fsme``, and the script a frozen build starts from.

One line here is not decoration. A run on several cores makes worker
processes, and on Windows — where there is no ``fork`` — a worker is made by
starting the program again and telling it to be a worker. A frozen build
started again is the whole executable started again, so without
``freeze_support`` the first ``fsme study --jobs 4`` on Windows launches four
copies of FSME, each of which launches four more.

It costs nothing anywhere else: not frozen, or forked rather than spawned, the
call returns immediately.
"""

from __future__ import annotations

import multiprocessing

from fsme.cli import main

if __name__ == "__main__":
    # Must come before anything a worker would repeat, which is why it is the
    # first thing after the imports.
    multiprocessing.freeze_support()

    raise SystemExit(main())
