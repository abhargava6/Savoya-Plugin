#!/usr/bin/env python3
"""OS-aware install commands and hints, shared by preflight.py and render_print.py."""
import platform
import shutil

SYS = platform.system()          # Darwin | Linux | Windows
MAC, WIN = SYS == "Darwin", SYS == "Windows"
PY_CMD = "python" if WIN else ("python3" if shutil.which("python3") else "python")
PIP_CMD = "pip" if WIN else ("pip3" if shutil.which("pip3") else f"{PY_CMD} -m pip")


def os_label():
    if MAC:
        return f"macOS {platform.mac_ver()[0]}".strip()
    if WIN:
        return f"Windows {platform.release()}"
    return f"{SYS} {platform.release()}"


def cmd_pdf_engine():
    return f"{PIP_CMD} install playwright && {PY_CMD} -m playwright install chromium"


def cmd_poppler():
    if MAC:
        return ("brew install poppler" if shutil.which("brew")
                else 'install Homebrew first:  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"\n  then:  brew install poppler')
    if WIN:
        return ("choco install poppler" if shutil.which("choco")
                else "scoop install poppler   (or download from github.com/oschwartz10612/poppler-windows/releases)")
    if shutil.which("apt") or shutil.which("apt-get"):
        return "sudo apt install poppler-utils"
    if shutil.which("dnf"):
        return "sudo dnf install poppler-utils"
    return "install the poppler-utils package for your distribution"


def cmd_pillow():
    return f"{PIP_CMD} install pillow"


def print_to_pdf_hint():
    if MAC:
        return "open it in Safari or Chrome, then File → Print → the PDF dropdown at the bottom left → Save as PDF"
    if WIN:
        return "open it in Edge or Chrome, then Ctrl+P → Destination: Microsoft Print to PDF → Print"
    return "open it in your browser, then Print → Save as PDF"


def shell_name():
    return "PowerShell" if WIN else "Terminal"
