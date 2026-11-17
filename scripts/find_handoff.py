#!/usr/bin/env python3
"""在项目里查找交接文档，按可信度排序。

用法：
  python3 find_handoff.py                 # 扫描当前目录
  python3 find_handoff.py /path/to/project
  python3 find_handoff.py . --max-depth 4 --json

判定依据：
  - 文件名含 work_handoff / handoff / 交接
  - 内容含“当前状态 / 下一步 / 已核实 / 禁区 / P0”
  - 位于 docs/ 下、最近修改过的优先

只读，不修改任何文件。找不到时返回退出码 1。
"""

import argparse
import json
import os
import re
import sys
import time

NAME_PATTERNS = [
    re.compile(r"work[_-]?handoff", re.IGNORECASE),
    re.compile(r"handoff", re.IGNORECASE),
    re.compile(r"交接"),
]
EXTENSIONS = {".md", ".markdown", ".txt"}
SKIP_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules", "vendor",
    "build", "dist", "target", ".build", "DerivedData", "Pods",
    "__pycache__", ".next", ".cache", ".idea", ".vscode",
}
CONTENT_MARKERS = ("当前状态", "下一步", "已核实", "禁区", "P0")
MAX_SCAN_BYTES = 2 * 1024 * 1024
SKILL_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(SKILL_ROOT, "references", "handoff-template.md")


def walk_candidates(root, max_depth):
    root = os.path.abspath(root)
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
        dirnames[:] = [
            name for name in dirnames
            if name not in SKIP_DIRS and not name.startswith(".")
        ]
        if depth >= max_depth:
            dirnames[:] = []
        for name in filenames:
            if os.path.splitext(name)[1].lower() not in EXTENSIONS:
                continue
            if not any(pattern.search(name) for pattern in NAME_PATTERNS):
                continue
            yield os.path.join(dirpath, name)


def score_candidate(path, root):
    name = os.path.basename(path)
    score = 0
    if re.search(r"work[_-]?handoff", name, re.IGNORECASE):
        score += 4
    elif re.search(r"handoff|交接", name, re.IGNORECASE):
        score += 2
    if name.upper().startswith("WORK_HANDOFF"):
        score += 2

    relative = os.path.relpath(path, root)
    if relative.startswith("docs" + os.sep) or os.sep + "docs" + os.sep in relative:
        score += 1

    markers = []
    try:
        if os.path.getsize(path) <= MAX_SCAN_BYTES:
            with open(path, encoding="utf-8-sig", errors="ignore") as handle:
                text = handle.read()
            markers = [marker for marker in CONTENT_MARKERS if marker in text]
            score += len(markers)
    except OSError:
        pass

    return score, markers


def main():
    parser = argparse.ArgumentParser(description="查找项目里的交接文档")
    parser.add_argument("root", nargs="?", default=".", help="项目根目录")
    parser.add_argument("--max-depth", type=int, default=4, help="最大扫描深度")
    parser.add_argument("--limit", type=int, default=10, help="最多列出几个")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    root = os.path.abspath(os.path.expanduser(args.root))
    if not os.path.isdir(root):
        print(f"目录不存在：{root}", file=sys.stderr)
        sys.exit(2)

    candidates = []
    for path in walk_candidates(root, args.max_depth):
        try:
            stat = os.stat(path)
        except OSError:
            continue
        score, markers = score_candidate(path, root)
        candidates.append({
            "path": path,
            "relative": os.path.relpath(path, root),
            "score": score,
            "markers": markers,
            "mtime": stat.st_mtime,
            "mtime_text": time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime)),
            "size": stat.st_size,
        })

    candidates.sort(key=lambda item: (item["score"], item["mtime"]), reverse=True)
    candidates = candidates[:args.limit]

    if args.json:
        print(json.dumps(candidates, ensure_ascii=False, indent=2))
    else:
        if not candidates:
            print(f"在 {root} 下没有找到交接文档。")
            print("可以按模板新建：docs/WORK_HANDOFF.md")
            print(f"模板：{TEMPLATE_PATH}")
        else:
            print(f"在 {root} 下找到 {len(candidates)} 个候选（按可信度排序）：\n")
            for index, item in enumerate(candidates, 1):
                markers = "、".join(item["markers"]) or "无内容标记"
                print(f"{index}. {item['relative']}")
                print(f"   分数 {item['score']} ｜ 修改 {item['mtime_text']} ｜ "
                      f"{item['size']} 字节 ｜ {markers}")

    sys.exit(0 if candidates else 1)


if __name__ == "__main__":
    main()
