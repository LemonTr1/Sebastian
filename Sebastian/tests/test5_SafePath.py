from src.Interfaces.SafePath import resolve_safe_path
from pathlib import Path
import os

def main():
    path = Path().home() / "桌面" / "exec.sh"
    path = resolve_safe_path(str(path), "real")
    print(os.path.isdir(path))

if __name__ == "__main__":
    main()