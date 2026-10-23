#!/usr/bin/env python3
"""Build the iPXE EFI image for the ITL Talos USB stick.

The image embeds the boot menu script and the background picture, so the USB
only needs ipxe.efi, copied to EFI/BOOT/BOOTX64.EFI. The picture is shown from
the embedded copy, so no network or extra file is needed for it. The menu script
still chains to the Talos factory image.

Requirements (Ubuntu/WSL): git, make, gcc, binutils, liblzma-dev (for iPXE)

Usage:
    python3 scripts/pxe/build_ipxe.py
    WORKDIR=~/ipxe-build OUT_DIR=~/usb python3 scripts/pxe/build_ipxe.py

Environment overrides:
    WORKDIR       build folder                   (default ~/talos-usb)
    IPXE_REPO     iPXE git repository            (default https://github.com/ipxe/ipxe.git)
    IPXE_REF      iPXE branch or tag             (default master)
    MENU_SRC      menu script                    (default scripts/pxe/menu.ipxe)
    PICTURE_SRC   background PNG (1024x768)      (default docs/images/talos-pxe-itlusions.png)
    OUT_DIR       where to put the result        (default WORKDIR/out)
"""
from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

WORKDIR = Path(os.environ.get("WORKDIR", Path.home() / "talos-usb")).expanduser()
IPXE_REPO = os.environ.get("IPXE_REPO", "https://github.com/ipxe/ipxe.git")
IPXE_REF = os.environ.get("IPXE_REF", "master")
MENU_SRC = Path(os.environ.get("MENU_SRC", HERE / "menu.ipxe")).expanduser()
PICTURE_SRC = Path(os.environ.get("PICTURE_SRC", REPO / "docs" / "images" / "talos-pxe-itlusions.png")).expanduser()
OUT_DIR = Path(os.environ.get("OUT_DIR", WORKDIR / "out")).expanduser()

PICTURE_LINE = "console --keep --picture {name} || echo text console only"
PICTURE_COMMENT = "# Background picture, embedded in the EFI image. Falls back to the text console without graphics."


def log(msg: str) -> None:
    print(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}", flush=True)


def die(msg: str) -> None:
    log(f"ERROR: {msg}")
    sys.exit(1)


def run(cmd: list[str], cwd: Path | None = None, log_file: Path | None = None) -> None:
    """Run a command, optionally sending its output to a log file."""
    if log_file is None:
        subprocess.run(cmd, cwd=cwd, check=True)
        return
    with log_file.open("w", encoding="utf-8") as f:
        result = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT)
    if result.returncode != 0:
        tail = log_file.read_text(encoding="utf-8", errors="replace").splitlines()[-20:]
        print("\n".join(tail))
        die(f"command failed: {' '.join(cmd)} (full log: {log_file})")


def check_tools() -> None:
    for tool in ("git", "make", "gcc", "ld"):
        if shutil.which(tool) is None:
            die(f"missing tool: {tool}")


def check_inputs() -> None:
    if not MENU_SRC.is_file():
        die(f"menu script not found: {MENU_SRC}")
    if not PICTURE_SRC.is_file():
        die(f"picture not found: {PICTURE_SRC} (convert the SVG to PNG first)")
    first = MENU_SRC.read_text(encoding="utf-8").split("\n", 1)[0]
    if not first.startswith("#!ipxe"):
        die("menu script must start with #!ipxe")


def clone_ipxe() -> Path:
    src = WORKDIR / "ipxe"
    if not (src / ".git").is_dir():
        log(f"cloning iPXE ({IPXE_REF})")
        run(["git", "clone", "--depth", "1", "--branch", IPXE_REF, IPXE_REPO, str(src)])
    return src


def prepare_menu(picture_name: str) -> Path:
    """Write the menu script with the picture line, unless it's already there."""
    lines = MENU_SRC.read_text(encoding="utf-8").split("\n")
    if not any(line.startswith("console --keep --picture") for line in lines):
        lines = [lines[0], "", PICTURE_COMMENT, PICTURE_LINE.format(name=picture_name)] + lines[1:]
    out = WORKDIR / "talos-menu.ipxe"
    out.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    return out


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    check_tools()
    check_inputs()
    WORKDIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    ipxe_src = clone_ipxe()

    picture_name = PICTURE_SRC.name
    menu_out = prepare_menu(picture_name)
    picture_copy = WORKDIR / picture_name
    shutil.copyfile(PICTURE_SRC, picture_copy)

    jobs = str(os.cpu_count() or 2)
    log(f"building ipxe.efi with {menu_out.name} and {picture_name} embedded")
    run(
        ["make", f"-j{jobs}", "bin-x86_64-efi/ipxe.efi", f"EMBED={menu_out},{picture_copy}"],
        cwd=ipxe_src / "src",
        log_file=WORKDIR / "build.log",
    )

    efi = ipxe_src / "src" / "bin-x86_64-efi" / "ipxe.efi"
    if picture_name.encode() not in efi.read_bytes():
        die("picture name not found in the binary; the embed did not work")

    out = OUT_DIR / "ipxe.efi"
    shutil.copyfile(efi, out)
    log(f"done: {out}")
    print(f"{sha256(out)}  {out}")
    log("copy it to the USB as EFI/BOOT/BOOTX64.EFI")


if __name__ == "__main__":
    main()
