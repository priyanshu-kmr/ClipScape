import logging
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
import datetime

logger = logging.getLogger(__name__)


class FileManager:

    def __init__(self, base_dir: Optional[Path] = None):
        if base_dir is None:
            base_dir = Path.home() / ".clipscape" / "files"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_file(self, payload: bytes, metadata: Dict[str, Any]) -> Optional[Path]:
        try:
            file_name = metadata.get("file_name", "unknown_file")
            file_path = self.base_dir / file_name

            counter = 1
            original_stem = file_path.stem
            original_suffix = file_path.suffix
            while file_path.exists():
                file_path = self.base_dir / \
                    f"{original_stem}_{counter}{original_suffix}"
                counter += 1

            file_path.write_bytes(payload)
            logger.info(f"Saved file to {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return None

    def cleanup_old_files(self, max_age_hours: int = 24):
        try:
            now = datetime.datetime.now()
            for file_path in self.base_dir.iterdir():
                if file_path.is_file():
                    file_age = now - \
                        datetime.datetime.fromtimestamp(
                            file_path.stat().st_mtime)
                    if file_age.total_seconds() > max_age_hours * 3600:
                        file_path.unlink()
                        logger.info(f"Cleaned up old file: {file_path}")
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def cleanup_all_files(self):
        import tempfile
        try:
            if self.base_dir.exists():
                shutil.rmtree(self.base_dir)
                logger.info(f"Cleaned up all files in {self.base_dir}")

            temp_clip_dir = Path(tempfile.gettempdir()) / ".clipscape_temp"
            if temp_clip_dir.exists():
                shutil.rmtree(temp_clip_dir)
                logger.info(f"Cleaned up temp folder {temp_clip_dir}")
        except Exception as e:
            logger.error(f"Cleanup all error: {e}")

    def get_file_uri(self, file_path: Path) -> str:
        return file_path.as_uri()
