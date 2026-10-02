"""Execute and validate the committed companion using optional notebook tools."""

from pathlib import Path
import os
from tempfile import TemporaryDirectory

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "notebooks/research.ipynb"
notebook = nbformat.read(path, as_version=4)
nbformat.validate(notebook)
with TemporaryDirectory(prefix="incentivescope-notebook-") as runtime:
    NotebookClient(notebook, timeout=90, kernel_name="python3",
                   resources={"metadata": {"path": str(ROOT)}}).execute(
        env={**os.environ, "IPYTHONDIR": runtime, "JUPYTER_RUNTIME_DIR": runtime})
nbformat.validate(notebook)
nbformat.write(notebook, path)
print("Validated and executed notebooks/research.ipynb")
