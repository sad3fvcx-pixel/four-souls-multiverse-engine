"""
Four Souls Multiverse Engine.

A deterministic rules simulator for The Binding of Isaac: Four Souls. The
engine knows mechanics; cards describe themselves as data.
"""

from __future__ import annotations

__version__ = "0.5.0"
"""
The version of FSME, and the only place it is written down.

``pyproject.toml`` reads this attribute rather than carrying its own number,
the command line prints it, and every journal is stamped with it. That
arrangement exists because the alternative was tried and failed quietly: the
number here said 0.1.0 while the packaging said 0.1.3, so every journal FSME
had ever written claimed to come from a version three releases old — and the
field nobody looks at until something is incompatible was the one that was
wrong.

A constant rather than ``importlib.metadata``: the release is a single file
built by PyInstaller, which carries no package metadata, and a version that
worked from a checkout and returned "unknown" from the binary would be worse
than no single source at all.
"""

__all__ = ["__version__"]
