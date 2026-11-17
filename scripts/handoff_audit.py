#!/usr/bin/env python3
"""审计一份交接文档：结构是否完整、是否过期、有没有占位符或敏感信息。

用法：
  python3 handoff_audit.py docs/WORK_HANDOFF.md
  python3 handoff_audit.py docs/WORK_HANDOFF.md --max-age-days 30 --strict
  python3 handoff_audit.py docs/WORK_HANDOFF.md --json

退出码：
  0  通过（允许 warning）
  1  有 error，或 --strict 下有 warning
  2  文件无法读取

只读，不修改任何文件。
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

# 交接文档必须覆盖的概念；命中任意一个关键词即可。
REQUIRED = [
    ("项目 / 目标", ("项目一句话", "项目概述", "目标")),
    ("约束 / 边界", ("约束", "边界")),
    ("已核实事实", ("已核实",)),
    ("实测数据", ("实测",)),
    ("待办优先级", ("P0", "待办")),
    ("文档地图", ("文档地图", "配套文档")),
    ("接手清单", ("接手第一件事", "自检清单")),
    ("禁区", ("禁区", "不要做", "禁止")),
    ("当前状态", ("当前状态",)),
    ("下一步", ("下一步",)),
]

# 只报告，不打印完整密钥。
SECRET_PATTERNS = [
    ("API key（sk- 开头）", re.compile(r"\bsk-[A-Za-z0-9_-]{16,}")),
    ("Bearer token", re.compile(r"Bearer\s+[A-Za-z0-9._-]{20,}")),
    ("阿里云 AccessKey", re.compile(r"\bLTAI[A-Za-z0-9]{12,}")),
    ("腾讯云 AKID", re.compile(r"\bAKID[A-Za-z0-9]{13,}")),
    ("私钥", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]

RELATIVE_DATES = ("今天", "昨天", "明天", "上周", "下周", "本周")
PLACEHOLDERS = ("TODO", "TBD", "待填", "XXX", "<待")
DATE_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})-(\d{2})-(\d{2})(?!\d)")

MAX_REPORTED = 10


def heading_level(line):
    match = re.match(r"^(#{1,6})\s+", line)
    return len(match.group(1)) if match else 0


def section_text(lines, keyword):
    """返回第一个标题含 keyword 的小节正文，以及标题所在行号（1 起）。"""
    for index, line in enumerate(lines):
        level = heading_level(line)
        if level and keyword in line:
            body = []
            for later in lines[index + 1:]:
                later_level = heading_level(later)
                if later_level and later_level <= level:
                    break
                body.append(later)
            return "\n".join(body), index + 1
    return None, None


def audit(path, max_age_days):
    errors = []
    warnings = []

    try:
        with open(path, encoding="utf-8-sig") as handle:
            text = handle.read()
    except OSError as exc:
        return None, [f"无法读取文件：{exc}"], []

    lines = text.splitlines()

    # 1. 必需内容
    for name, keywords in REQUIRED:
        if not any(keyword in text for keyword in keywords):
            errors.append(
                f"缺少必需内容：{name}（应包含关键词之一：{'、'.join(keywords)}）"
            )

    # 2. 当前状态小节必须写下一步，且不能是空壳
    status, status_line = section_text(lines, "当前状态")
    if status is not None:
        body_lines = [line.strip() for line in status.splitlines() if line.strip()]
        if len(body_lines) < 2:
            warnings.append(f"第 {status_line} 行“当前状态”内容过少，可能没更新")
        if "下一步" not in status:
            warnings.append(f"第 {status_line} 行“当前状态”没有写“下一步”")

    # 3. 敏感信息（只报类型、行号和掩码）
    for label, pattern in SECRET_PATTERNS:
        for match in pattern.finditer(text):
            line_no = text.count("\n", 0, match.start()) + 1
            value = match.group(0)
            masked = (value[:4] + "***") if len(value) > 4 else "***"
            errors.append(f"疑似{label}：第 {line_no} 行（{masked}），请改为占位符")

    # 4. 相对日期
    for word in RELATIVE_DATES:
        hits = [i + 1 for i, line in enumerate(lines) if word in line]
        if hits:
            shown = "、".join(str(n) for n in hits[:5])
            warnings.append(f"出现相对日期“{word}”（第 {shown} 行），请改成绝对日期")

    # 5. 占位符
    placeholder_hits = []
    for number, line in enumerate(lines, 1):
        for word in PLACEHOLDERS:
            if word in line:
                placeholder_hits.append((number, word))
                break
    for number, word in placeholder_hits[:MAX_REPORTED]:
        warnings.append(f"第 {number} 行有未完成占位符“{word}”")
    if len(placeholder_hits) > MAX_REPORTED:
        warnings.append(f"另有 {len(placeholder_hits) - MAX_REPORTED} 处占位符未列出")

    # 6. 日期新鲜度
    dates = []
    for match in DATE_RE.finditer(text):
        try:
            dates.append(dt.date(int(match.group(1)), int(match.group(2)),
                                 int(match.group(3))))
        except ValueError:
            warnings.append(f"无法解析的日期：{match.group(0)}")
    if not dates:
        warnings.append("文档里没有 YYYY-MM-DD 绝对日期，无法判断新鲜度")
    else:
        newest = max(dates)
        today = dt.date.today()
        age = (today - newest).days
        if age > max_age_days:
            warnings.append(
                f"最新日期是 {newest.isoformat()}，已 {age} 天；"
                "交接文档可能过期，先核对“当前状态”"
            )
        if (newest - today).days > 1:
            warnings.append(f"最新日期 {newest.isoformat()} 在未来，请核对")

    # 7. 是否标注了编写 / 更新日期
    if not any(marker in text for marker in ("编写日期", "更新日期", "编写 / 更新日期")):
        warnings.append("头部没有“编写日期 / 更新日期”，下一个模型无法判断时效")

    stats = {
        "lines": len(lines),
        "headings": sum(1 for line in lines if heading_level(line)),
        "newest_date": max(dates).isoformat() if dates else None,
    }
    return stats, errors, warnings


def main():
    parser = argparse.ArgumentParser(description="审计交接文档")
    parser.add_argument("path", help="交接文档路径")
    parser.add_argument("--max-age-days", type=int, default=14,
                        help="最新日期超过多少天算过期（默认 14）")
    parser.add_argument("--strict", action="store_true",
                        help="有 warning 也返回非零")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()

    path = os.path.expanduser(args.path)
    if not os.path.exists(path):
        print(f"文件不存在：{path}", file=sys.stderr)
        sys.exit(2)

    stats, errors, warnings = audit(path, args.max_age_days)
    if stats is None:
        for error in errors:
            print(error, file=sys.stderr)
        sys.exit(2)

    if args.json:
        print(json.dumps(
            {"path": path, "stats": stats, "errors": errors, "warnings": warnings},
            ensure_ascii=False, indent=2,
        ))
    else:
        print(f"== 交接文档审计: {path} ==")
        print(f"行数 {stats['lines']}，标题 {stats['headings']} 个，"
              f"最新日期 {stats['newest_date'] or '（无）'}")
        for error in errors:
            print(f"[ERROR] {error}")
        for warning in warnings:
            print(f"[WARN]  {warning}")
        print(f"\n结论：{len(errors)} 个错误，{len(warnings)} 个警告")

    failed = bool(errors) or (args.strict and bool(warnings))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
