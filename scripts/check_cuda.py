"""Optional synthetic CUDA compatibility probe, separate from the CPU benchmark."""

import json
import hashlib
import platform
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import torch

from incentivescope.ml_data import FEATURE_NAMES, LOG_FEATURES
from incentivescope.ml_models import _predict, load_checkpoint, prepare_features, run_models


def main():
    if not torch.cuda.is_available():
        raise SystemExit("CUDA unavailable. Use the separate official CUDA-wheel environment.")
    rows = []
    for split, n in (("train", 64), ("validation", 16), ("test", 16)):
        for index in range(n):
            row = {name: float(index % 9 + 1) for name in FEATURE_NAMES}
            row.update(account=f"0x{index:040x}", as_of=split, split=split, label=index % 2,
                       pre_campaign_opening=index % 2, top_market_share_30d=(index % 4) / 4)
            rows.append(row)
    data = {"rows": rows, "feature_names": list(FEATURE_NAMES), "log_features": list(LOG_FEATURES)}
    with TemporaryDirectory(prefix="incentivescope-cuda-") as directory:
        output = Path(directory)
        result = run_models(data, output, device="cuda", _max_epochs=2, _patience=2, _permutation_repeats=1)
        parts, _ = prepare_features(data)
        checkpoint = output / "mlp-seed-42.pt"
        gpu = _predict(load_checkpoint(checkpoint, "cuda"), parts["test"]["x"], "cuda")
        cpu = _predict(load_checkpoint(checkpoint), parts["test"]["x"], "cpu")
        np.testing.assert_allclose(cpu, gpu, atol=1e-6, rtol=1e-6)
    print(json.dumps({
        "status": "passed", "scope": "Synthetic compatibility probe; not GMX training or performance evidence",
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(), "torch": torch.__version__, "cuda_runtime": torch.version.cuda,
        "gpu": torch.cuda.get_device_name(0), "compute_capability": list(torch.cuda.get_device_capability(0)),
        "compiled_architectures": torch.cuda.get_arch_list(), "device": result["device"],
        "seeds_tested": [row["seed"] for row in result["mlp_seed_results"]], "epochs_per_seed": 2,
        "checkpoint_cpu_gpu_max_abs_difference": float(np.max(np.abs(cpu - gpu))),
    }, indent=2))


if __name__ == "__main__":
    main()
