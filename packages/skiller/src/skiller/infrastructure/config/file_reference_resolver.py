import os
from pathlib import Path

from skiller.domain.shared.file_reference import resolve_file_reference


def resolve_runtime_file_reference(reference: str, *, base_dir: Path) -> Path:
    return resolve_file_reference(
        reference, environment=os.environ, base_dir=base_dir, home_dir=Path.home()
    )
