"""下载 Sensitive-lexicon 词库文件到 data/sensitive_lexicon/Vocabulary/。"""

from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("请先安装 requests: pip install requests")
    sys.exit(1)

BASE_URL = "https://raw.githubusercontent.com/konsheng/Sensitive-lexicon/main/Vocabulary"
FILES = [
    "广告类型.txt",
    "色情类型.txt",
    "色情词库.txt",
    "政治类型.txt",
    "反动词库.txt",
    "补充词库.txt",
    "其他词库.txt",
]


def main() -> int:
    project_root = Path(__file__).resolve().parent.parent
    vocab_dir = project_root / "data" / "sensitive_lexicon" / "Vocabulary"
    vocab_dir.mkdir(parents=True, exist_ok=True)
    ok = 0
    for fname in FILES:
        url = f"{BASE_URL}/{quote(fname)}"
        out_path = vocab_dir / fname
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            out_path.write_text(r.text, encoding="utf-8")
            print(f"已下载: {fname}")
            ok += 1
        except Exception as e:
            print(f"下载失败 {fname}: {e}")
    print(f"完成: {ok}/{len(FILES)} 个文件")
    return 0 if ok == len(FILES) else 1


if __name__ == "__main__":
    sys.exit(main())
