from pathlib import Path
import shutil

class FileUtils:
    @staticmethod
    def ensure_dir(path: str):
        Path(path).mkdir(parents=True, exist_ok=True)
    
    @staticmethod
    def copy_file(src: str, dst: str):
        shutil.copy2(src, dst)
        return dst
