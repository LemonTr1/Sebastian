from src.tools.toolkits.glob import glob
from pathlib import Path

if __name__ == "__main__":
    result = glob("*.md", str(Path.home() / "桌面"))
    print(result)