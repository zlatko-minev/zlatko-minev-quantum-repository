#!/usr/bin/env python3
"""
Convert all .pptx files in the current folder to PDFs using Microsoft PowerPoint on macOS.

Example:
    .. code-block:: shell

        python3 convert_pptx_to_pdf.py
"""

import subprocess
from pathlib import Path

def escape_path(path: Path) -> str:
    """Escape a path for AppleScript (double quotes inside paths)."""
    return str(path).replace('"', '\\"')

def convert_with_powerpoint():
    pptx_files = Path(".").glob("*.pptx")

    for pptx in pptx_files:
        pptx_path = pptx.resolve()
        pdf_path = pptx.with_suffix(".pdf").resolve()

        script = f'''
        set pptPath to POSIX file "{escape_path(pptx_path)}"
        set pdfPath to POSIX file "{escape_path(pdf_path)}"

        tell application "Microsoft PowerPoint"
            activate
            open pptPath
            delay 1
            set thePres to active presentation
            save active presentation in pdfPath as save as PDF
            delay 1
        end tell
        '''
        # close thePres saving no

        print("\n",script,"\n")

        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)

        if result.returncode != 0:
            print(f"❌ Failed to convert {pptx.name}: {result.stderr.strip()}")
        else:
            print(f"✅ Converted {pptx.name} -> {pdf_path.name}")

if __name__ == "__main__":
    convert_with_powerpoint()
