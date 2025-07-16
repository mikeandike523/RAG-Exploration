import os
from pathlib import Path

def is_filesystem_or_drive_root(path: str) -> bool:
    p = Path(path).resolve(strict=False)
    return p.parent == p

def get_project_root(starting_path=None):
    if starting_path is None:
        starting_path = os.getcwd()
    else:
        if not os.path.isabs(starting_path):
            raise ValueError("Argument `starting_path` must be an absolute path.")
    full_path = starting_path = os.path.abspath(starting_path)
    if not os.path.exists(full_path):
        raise ValueError(f"Invalid path: {full_path}")
    if not os.path.isdir(full_path):
        if os.path.isfile(full_path):
            full_path = os.path.dirname(full_path)
        else:
            raise ValueError(f"{full_path} is not a directory or file within a directory.")
    while not os.path.isdir(os.path.join(full_path, ".git")):
        if is_filesystem_or_drive_root(full_path):
            raise ValueError("Hit filesystem or drive root before finding a .git directory.")
        full_path = os.path.dirname(full_path)
    return full_path
