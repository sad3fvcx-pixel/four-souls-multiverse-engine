# packaging/fsme.spec
#
# A single executable for people without Python.
#
# Two things have to travel with the code: the card content, which is the whole
# game, and the page the browser is served. Both are data the engine reads at
# run time, so PyInstaller has to be told about them — nothing imports them.
#
#     pyinstaller packaging/fsme.spec
#
# The result is dist/fsme (dist/fsme.exe on Windows). It is built for the
# platform it is built on: an executable cannot be cross-compiled, so Windows
# and macOS builds come from the workflow in .github/workflows/build.yml.

from pathlib import Path

ROOT = Path(SPECPATH).resolve().parent

analysis = Analysis(
    [str(ROOT / "src" / "fsme" / "__main__.py")],
    pathex=[str(ROOT / "src")],
    datas=[
        (str(ROOT / "content"), "content"),
        (str(ROOT / "src" / "fsme" / "web" / "static"), "fsme/web/static"),
        (
            str(ROOT / "src" / "fsme" / "lab" / "desk" / "static"),
            "fsme/lab/desk/static",
        ),
    ],
    # The lab is imported inside the functions that need it, so nothing static
    # points at it and PyInstaller would not follow it in. A build without the
    # desk is a build whose front door 500s, which is what running it with no
    # arguments does.
    hiddenimports=[
        "fsme.cli",
        "fsme.web",
        "fsme.api",
        "fsme.lab",
        "fsme.lab.desk",
        "fsme.lab.analysis",
        "fsme.lab.simulation",
        "fsme.lab.bot",
    ],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest", "mypy"],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    [],
    name="fsme",
    console=True,
    strip=False,
    upx=False,
)
