import os
import re


def normalize_track_name(track_name: str) -> str:
    """
    Normalize a track name for case-insensitive and separator-insensitive matching.
    """
    normalized = re.sub(r'[^a-z0-9]+', ' ', track_name.lower()).strip()
    return re.sub(r'\s+', ' ', normalized)


def get_track_assets_dirs(*, app_root_path: str) -> list[str]:
    """
    Return potential track assets directories.
    Supports both `src/f1Tracks` and project-root `f1Tracks`.
    """
    project_root = os.path.abspath(os.path.join(app_root_path, '..'))
    return [
        os.path.join(app_root_path, 'f1Tracks'),
        os.path.join(project_root, 'f1Tracks')
    ]
