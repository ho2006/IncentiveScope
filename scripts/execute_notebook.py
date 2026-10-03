"""Execute and validate the committed companion using optional notebook tools."""

import argparse
from pathlib import Path
import os
from tempfile import TemporaryDirectory

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("notebook", nargs="?", type=Path, default=ROOT / "notebooks/research.ipynb")
path = parser.parse_args().notebook.resolve()
notebook = nbformat.read(path, as_version=4)
nbformat.validate(notebook)
with TemporaryDirectory(prefix="incentivescope-notebook-") as runtime:
    NotebookClient(notebook, timeout=180, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT)}}).execute(
        env={**os.environ, "IPYTHONDIR": runtime, "JUPYTER_RUNTIME_DIR": runtime})
nbformat.validate(notebook)
nbformat.write(notebook, path)
print(f"Validated and executed {path}")
