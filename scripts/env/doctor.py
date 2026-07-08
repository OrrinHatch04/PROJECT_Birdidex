"""Environment diagnostics for the BirdIDEX uv workspace."""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROJECT_VENV = PROJECT_ROOT / ".venv"
REQUIRE_PROJECT_VENV = os.environ.get("BIRDIDEX_DOCTOR_REQUIRE_PROJECT_VENV") == "1"
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")


def _print(label: str, value: object) -> None:
    print(f"{label}: {value}")


def _warn(message: str) -> None:
    print(f"WARNING: {message}")


def _in_project_venv() -> bool:
    project_venv = PROJECT_VENV.resolve()
    prefixes = [Path(sys.prefix), Path(os.environ.get("VIRTUAL_ENV", ""))]
    return any(prefix and prefix.resolve() == project_venv for prefix in prefixes)


def _distribution_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _module_version(module_name: str, distribution_name: str | None = None) -> str:
    package_name = distribution_name or module_name
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:  # noqa: BLE001 - diagnostics should report import failures.
        installed = _distribution_version(package_name)
        if installed is None:
            return "not installed"
        return f"installed {installed}; import failed: {exc.__class__.__name__}: {exc}"

    version = getattr(module, "__version__", None) or _distribution_version(package_name)
    return str(version or "installed; version unknown")


def _uv_version() -> str:
    uv = shutil.which("uv")
    if uv is None:
        return "not found on PATH"
    try:
        result = subprocess.run(
            [uv, "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception as exc:  # noqa: BLE001 - diagnostics should report command failures.
        return f"{uv}; version check failed: {exc.__class__.__name__}: {exc}"
    output = (result.stdout or result.stderr).strip()
    return output or uv


def _has_amd_gpu() -> bool:
    for vendor_path in Path("/sys/class/drm").glob("card*/device/vendor"):
        try:
            if vendor_path.read_text(encoding="utf-8").strip().lower() == "0x1002":
                return True
        except OSError:
            continue

    lspci = shutil.which("lspci")
    if lspci is None:
        return False
    try:
        result = subprocess.run(
            [lspci],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except Exception:
        return False
    lines = result.stdout.lower().splitlines()
    return any(
        ("vga" in line or "3d" in line or "display" in line) and "amd" in line for line in lines
    )


def _torch_backend() -> None:
    try:
        torch = importlib.import_module("torch")
    except Exception as exc:  # noqa: BLE001 - diagnostics should report import failures.
        installed = _distribution_version("torch")
        if installed is None:
            _print("torch", "not installed")
        else:
            _print(
                "torch",
                f"installed {installed}; import failed: {exc.__class__.__name__}: {exc}",
            )
        return

    version = str(getattr(torch, "__version__", "unknown"))
    cuda_version = getattr(getattr(torch, "version", object()), "cuda", None)
    hip_version = getattr(getattr(torch, "version", object()), "hip", None)
    cuda_available = bool(torch.cuda.is_available())

    _print("torch.__version__", version)
    _print("torch.version.cuda", cuda_version)
    _print("torch.version.hip", hip_version)
    _print("torch.cuda.is_available()", cuda_available)

    if cuda_available:
        try:
            _print("torch.cuda.get_device_name(0)", torch.cuda.get_device_name(0))
        except Exception as exc:  # noqa: BLE001 - diagnostics should not hide backend details.
            _warn(f"torch reports CUDA available but device query failed: {exc}")

    if "+cu" in version.lower() and platform.system() == "Linux":
        qualifier = "AMD GPU detected" if _has_amd_gpu() else "Linux workstation"
        _warn(f"CUDA PyTorch build detected on {qualifier}; use the ROCm training lock/source.")


def main() -> int:
    failures: list[str] = []

    _print("python executable", sys.executable)
    _print("python version", sys.version.replace("\n", " "))
    _print("platform", platform.platform())
    _print("machine", platform.machine())
    _print("cwd", Path.cwd())
    _print("project root", PROJECT_ROOT)
    _print("inside project .venv", _in_project_venv())
    _print("uv", _uv_version())

    if sys.version_info[:2] != (3, 11):
        failures.append("Python must be 3.11.x")
    if REQUIRE_PROJECT_VENV and not _in_project_venv():
        failures.append(f"make doctor must run from {PROJECT_VENV / 'bin' / 'python'}")

    for module_name, distribution_name in [
        ("numpy", None),
        ("pandas", None),
        ("cv2", "opencv-python-headless"),
        ("torchvision", None),
        ("tensorflow", None),
        ("onnxruntime", None),
        ("openvino", None),
    ]:
        _print(module_name, _module_version(module_name, distribution_name))

    _torch_backend()

    opencv_gui = _distribution_version("opencv-python")
    opencv_headless = _distribution_version("opencv-python-headless")
    _print("opencv-python distribution", opencv_gui or "not installed")
    _print("opencv-python-headless distribution", opencv_headless or "not installed")
    if opencv_gui and opencv_headless:
        _warn("both opencv-python and opencv-python-headless are installed; keep only headless.")

    if os.environ.get("CONDA_DEFAULT_ENV"):
        _warn(f"CONDA_DEFAULT_ENV is set to {os.environ['CONDA_DEFAULT_ENV']}; use the uv .venv.")

    if failures:
        print()
        print("Hard failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print()
    print("Doctor completed without hard failures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
