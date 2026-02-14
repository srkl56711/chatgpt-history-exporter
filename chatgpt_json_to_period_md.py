#!/usr/bin/env python3
"""
Convert ChatGPT exported conversations.json into Markdown files split by period,
optionally placed into month folders.

Output buckets (--split):
  monthly  : YYYY-MM
  weekly   : YYYY-MM-DD_to_YYYY-MM-DD  (week range)
  biweekly : YYYY-MM-DD_to_YYYY-MM-DD  (14-day range)
  daily    : YYYY-MM-DD

Optional folder grouping:
  --group-by-month
    out_dir/YYYY-MM/<bucket>.md

Examples:
  # daily files, grouped into month folders
  python chatgpt_json_to_period_md.py conversations.json out_md --split daily --group-by-month --tz Asia/Tokyo

  # weekly files, grouped by month folders, week starts Monday
  python chatgpt_json_to_period_md.py conversations.json out_md --split weekly --group-by-month --week-start mon --tz Asia/Tokyo
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, Iterator, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # py3.9+
except ImportError:
    ZoneInfo = None  # type: ignore


# ----------------------------
# Utilities
# ----------------------------

def safe_text(x: Any) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return str(x)

def sanitize_heading(s: str) -> str:
    s = safe_text(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s if s else "Untitled"

def to_dt(ts: Any, tz) -> Optional[datetime]:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=tz)
    except Exception:
        return None

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def md_escape_fence(s: str) -> str:
    # Avoid breaking markdown code fences if message contains ```
    return s.replace("```", "`\u200b``")

def pick_best_leaf_node_id(mapping: Dict[str, Any]) -> Optional[str]:
    best_id = None
    best_time = float("-inf")
    for node_id, node in mapping.items():
        msg = (node or {}).get("message")
        if not msg:
            continue
        ct = msg.get("create_time")
        if ct is None:
            continue
        try:
            t = float(ct)
        except Exception:
            continue
        if t > best_time:
            best_time = t
            best_id = node_id
    return best_id

def path_from_leaf_to_root(mapping: Dict[str, Any], leaf_id: str) -> List[str]:
    path = []
    seen = set()
    cur = leaf_id
    while cur and cur not in seen and cur in mapping:
        seen.add(cur)
        path.append(cur)
        parent = (mapping[cur] or {}).get("parent")
        if parent is None:
            break
        cur = parent
    path.reverse()
    return path

def message_is_hidden(msg: Dict[str, Any]) -> bool:
    md = msg.get("metadata") or {}
    return md.get("is_visually_hidden_from_conversation") is True

def extract_message_text(msg: Dict[str, Any]) -> str:
    content = msg.get("content") or {}
    parts = content.get("parts")
    if isinstance(parts, list):
        return "\n".join(safe_text(p) for p in parts).strip()
    if "text" in content:
        return safe_text(content.get("text")).strip()
    return safe_text(content).strip()


# ----------------------------
# Bucketing logic
# ----------------------------

def month_folder(dt: datetime) -> str:
    return dt.strftime("%Y-%m")

def start_of_week(d: date, week_start: str) -> date:
    """
    Return start date of week containing d.
    week_start: 'mon' or 'sun'
    """
    wd = d.weekday()  # Mon=0..Sun=6
    if week_start == "mon":
        return d - timedelta(days=wd)

    # Sunday start: convert so Sun=0..Sat=6
    sun_based = (wd + 1) % 7
    return d - timedelta(days=sun_based)

def bucket_key(dt: datetime, split: str, week_start: str) -> str:
    d = dt.date()

    if split == "daily":
        return d.strftime("%Y-%m-%d")

    if split == "monthly":
        return d.strftime("%Y-%m")

    if split == "weekly":
        s = start_of_week(d, week_start)
        e = s + timedelta(days=6)
        return f"{s.strftime('%Y-%m-%d')}_to_{e.strftime('%Y-%m-%d')}"

    if split == "biweekly":
        # Anchor biweekly periods to a fixed reference aligned to week_start.
        ref = start_of_week(date(1970, 1, 1), week_start)
        days = (d - ref).days
        period_index = days // 14
        s = ref + timedelta(days=period_index * 14)
        e = s + timedelta(days=13)
        return f"{s.strftime('%Y-%m-%d')}_to_{e.strftime('%Y-%m-%d')}"

    raise ValueError(f"Unknown split: {split}")


# ----------------------------
# Markdown formatting
# ----------------------------

@dataclass
class RenderedMessage:
    role: str
    when: Optional[datetime]
    text: str

def render_conversation_to_md(
    convo: Dict[str, Any],
    tz,
    split: str,
    week_start: str
) -> Tuple[str, str, str]:
    """
    Returns: (bucket_key, month_folder_key, markdown_chunk_for_this_conversation)

    month_folder_key is "YYYY-MM" derived from conversation create_time/update_time.
    """
    title = sanitize_heading(convo.get("title"))

    ct = to_dt(convo.get("create_time"), tz) or to_dt(convo.get("update_time"), tz)
    if ct is None:
        bucket = "unknown"
        mon = "unknown"
        header_time = ""
    else:
        bucket = bucket_key(ct, split=split, week_start=week_start)
        mon = month_folder(ct)
        header_time = ct.strftime("%Y-%m-%d %H:%M:%S %Z")

    mapping = convo.get("mapping") or {}
    if not isinstance(mapping, dict) or not mapping:
        body = f"## {title}\n\n*(No mapping/messages found)*\n\n---\n\n"
        return bucket, mon, body

    current_node = convo.get("current_node")
    if not current_node or current_node not in mapping:
        current_node = pick_best_leaf_node_id(mapping)

    if not current_node:
        body = f"## {title}\n\n*(No usable messages found)*\n\n---\n\n"
        return bucket, mon, body

    node_path = path_from_leaf_to_root(mapping, current_node)

    rendered: List[RenderedMessage] = []
    for node_id in node_path:
        node = mapping.get(node_id) or {}
        msg = node.get("message")
        if not isinstance(msg, dict) or not msg:
            continue
        if message_is_hidden(msg):
            continue

        author = msg.get("author") or {}
        role = safe_text(author.get("role") or "unknown").strip()

        text = extract_message_text(msg)
        if role == "system" and text.strip() == "":
            continue
        if text.strip() == "":
            continue

        when = to_dt(msg.get("create_time"), tz)
        rendered.append(RenderedMessage(role=role, when=when, text=text))

    lines: List[str] = []
    lines.append(f"## {title}")
    if header_time:
        lines.append(f"*Created:* {header_time}")
    lines.append("")

    for m in rendered:
        who = m.role.capitalize()
        stamp = f" ({m.when.strftime('%Y-%m-%d %H:%M:%S %Z')})" if m.when else ""
        lines.append(f"### {who}{stamp}")
        lines.append("")
        lines.append(md_escape_fence(m.text))
        lines.append("")

    lines.append("---")
    lines.append("")
    return bucket, mon, "\n".join(lines)


# ----------------------------
# Reading JSON (streaming if possible)
# ----------------------------

def iter_conversations(path: str) -> Iterator[Dict[str, Any]]:
    """
    Yield each conversation dict from a top-level JSON array.

    If `ijson` is available, stream items to avoid loading huge files:
      pip install ijson
    """
    try:
        import ijson  # type: ignore
    except Exception:
        ijson = None  # type: ignore

    if ijson is not None:
        with open(path, "rb") as f:
            for item in ijson.items(f, "item"):
                if isinstance(item, dict):
                    yield item
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                yield item


# ----------------------------
# Writing
# ----------------------------

def write_bucket_files(
    chunks: Dict[Tuple[str, str], List[str]],
    out_dir: str,
    group_by_month: bool
) -> None:
    """
    chunks key is (bucket_key, month_folder_key).
    If group_by_month is False, month_folder_key may be ignored.
    """
    ensure_dir(out_dir)

    # Determine output paths
    file_map: Dict[str, List[str]] = {}
    for (bucket, mon), parts in chunks.items():
        if group_by_month:
            out_path = os.path.join(out_dir, mon, f"{bucket}.md")
        else:
            out_path = os.path.join(out_dir, f"{bucket}.md")
        file_map.setdefault(out_path, []).extend(parts)

    for out_path, parts in sorted(file_map.items()):
        ensure_dir(os.path.dirname(out_path))
        key_title = os.path.splitext(os.path.basename(out_path))[0]
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(f"# {key_title}\n\n")
            for p in parts:
                f.write(p)


# ----------------------------
# Main
# ----------------------------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("input_json", help="Path to conversations.json")
    ap.add_argument("out_dir", help="Output directory")
    ap.add_argument(
        "--split",
        choices=["daily", "weekly", "biweekly", "monthly"],
        default="monthly",
        help="How to split output files"
    )
    ap.add_argument(
        "--group-by-month",
        action="store_true",
        help="Place output files into out_dir/YYYY-MM/ folders"
    )
    ap.add_argument(
        "--week-start",
        choices=["mon", "sun"],
        default="mon",
        help="Week start day for weekly/biweekly buckets"
    )
    ap.add_argument(
        "--tz",
        default="UTC",
        help="Timezone name, e.g. 'UTC' or 'Asia/Tokyo'"
    )
    args = ap.parse_args()

    # Timezone handling
    if args.tz.upper() == "UTC":
        tz = timezone.utc
    else:
        if ZoneInfo is None:
            raise SystemExit("zoneinfo not available (need Python 3.9+). Use --tz UTC.")
        try:
            tz = ZoneInfo(args.tz)
        except Exception as e:
            raise SystemExit(
                f"Could not load timezone '{args.tz}' ({e}). "
                f"On Windows, install tzdata: python -m pip install tzdata"
            )

    # Gather chunks by (bucket, month_folder)
    chunks: Dict[Tuple[str, str], List[str]] = {}

    for convo in iter_conversations(args.input_json):
        bucket, mon, md = render_conversation_to_md(convo, tz, split=args.split, week_start=args.week_start)
        chunks.setdefault((bucket, mon), []).append(md)

    write_bucket_files(chunks, args.out_dir, group_by_month=args.group_by_month)

    # Count distinct output files
    out_files = set()
    for (bucket, mon) in chunks.keys():
        if args.group_by_month:
            out_files.add(os.path.join(args.out_dir, mon, f"{bucket}.md"))
        else:
            out_files.add(os.path.join(args.out_dir, f"{bucket}.md"))

    print(f"Done. Wrote {len(out_files)} file(s) to: {args.out_dir}")


if __name__ == "__main__":
    main()
