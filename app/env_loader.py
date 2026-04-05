import os
from pathlib import Path


def load_local_env(env_path: str | Path | None = None) -> Path | None:
    """
    Carga variables desde un archivo .env local si existe.
    No sobreescribe variables que ya vengan definidas en el entorno.
    """
    candidates: list[Path] = []

    if env_path:
        candidates.append(Path(env_path))

    here = Path(__file__).resolve()
    candidates.extend([
        here.parents[1] / ".env",
        Path.cwd() / ".env",
    ])

    seen: set[str] = set()
    for candidate in candidates:
        resolved = str(candidate.resolve(strict=False))
        if resolved in seen:
            continue
        seen.add(resolved)

        if candidate.is_file():
            _load_env_file(candidate)
            return candidate

    return None


def _load_env_file(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("export "):
            line = line[7:].lstrip()

        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)
