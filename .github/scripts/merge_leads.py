#!/usr/bin/env python3
"""
Merge all per-run lead files from inbox/ into the canonical leads.json.

Design goals:
- Grok only ever CREATES files in inbox/ (create-only -> it can never overwrite
  or wipe the canonical feed). This script is the single writer of leads.json.
- Deterministic, idempotent merge: de-duplicate by post_id, sort newest-first.
- Normalizes every record to the exact schema the Scout iOS app decodes, so
  schema drift in Grok's output (legacy keys, bad quality strings, fractional
  seconds, nulls) is auto-corrected instead of breaking the app's strict decoder.

Run from the repo root: python3 .github/scripts/merge_leads.py
"""

from __future__ import annotations

import glob
import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlsplit

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LEADS_PATH = os.path.join(REPO_ROOT, "leads.json")
INBOX_GLOB = os.path.join(REPO_ROOT, "inbox", "*.json")

MAX_LEADS = 500
VALID_QUALITY = {"High Quality", "Medium", "Low"}

# Required keys in the exact order the app expects.
REQUIRED_KEYS = [
    "post_id", "platform", "source", "author", "title",
    "content", "url", "quality", "budget", "created_at",
]


def _first(d: dict, *keys: str) -> str:
    """Return the first present, non-null value among keys, as a string."""
    for k in keys:
        if k in d and d[k] is not None:
            return str(d[k])
    return ""


def _normalize_quality(value: str) -> str:
    v = (value or "").strip().lower()
    if v in {"high quality", "high", "high-quality", "highquality"}:
        return "High Quality"
    if v in {"medium", "med", "mid"}:
        return "Medium"
    if v in {"low"}:
        return "Low"
    # Unknown / empty -> safe default that always decodes.
    return "Medium"


def _normalize_date(value: str) -> str:
    """Return ISO-8601 UTC with no fractional seconds (e.g. 2026-06-09T05:34:12Z)."""
    raw = (value or "").strip()
    if not raw:
        return ""
    candidate = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(candidate)
    except ValueError:
        # Last resort: strip an obvious fractional-seconds + Z pattern.
        return raw.split(".")[0].rstrip("Z") + "Z" if "." in raw else raw
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def normalize_lead(raw: dict) -> dict | None:
    """Coerce one record to the exact Scout schema. Returns None if unusable."""
    if not isinstance(raw, dict):
        return None

    post_id = _first(raw, "post_id", "id")
    url = _first(raw, "url", "postLink", "post_link", "link")
    if not post_id:
        # Derive a stable id from the url so we never drop a real lead.
        post_id = "auto-" + str(abs(hash(url)) % (10 ** 16)) if url else ""
    if not post_id and not url and not _first(raw, "title"):
        return None  # genuinely empty record

    return {
        "post_id": post_id,
        "platform": _first(raw, "platform"),
        "source": _first(raw, "source"),
        "author": _first(raw, "author"),
        "title": _first(raw, "title"),
        "content": _first(raw, "content", "description"),
        "url": url,
        "quality": _normalize_quality(_first(raw, "quality", "priority")),
        "budget": _first(raw, "budget"),
        "created_at": _normalize_date(_first(raw, "created_at", "datePosted", "date_posted")),
    }


def dedupe_key(lead: dict) -> str:
    """A stable key identifying the same real post across runs.

    Grok formats post_id inconsistently (e.g. "x-123" vs "twitter-123"), so we key
    on the post URL instead. For Twitter/X we extract the numeric status id, which is
    identical regardless of x.com vs twitter.com, www, tracking query params, or handle.
    Falls back to a normalized URL, then to post_id.
    """
    url = (lead.get("url") or "").strip()
    if url:
        m = re.search(r"(?:twitter\.com|x\.com)/[^/]+/status(?:es)?/(\d+)", url, re.I)
        if m:
            return "x:" + m.group(1)
        parts = urlsplit(url if "://" in url else "https://" + url)
        host = parts.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host + parts.path.rstrip("/").lower()
    return "id:" + (lead.get("post_id") or "").strip().lower()


def load_array(path: str) -> list[dict]:
    """Load a JSON file that may be a bare array, a wrapper object, or a single object."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"  ! skipping {os.path.relpath(path, REPO_ROOT)}: {exc}", file=sys.stderr)
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        if isinstance(data.get("leads"), list):
            return [x for x in data["leads"] if isinstance(x, dict)]
        return [data]
    return []


def main() -> int:
    records: list[dict] = []

    # Existing canonical feed first (lowest priority on ties).
    if os.path.exists(LEADS_PATH):
        records.extend(load_array(LEADS_PATH))

    # All inbox files (each run Grok wrote).
    inbox_files = sorted(glob.glob(INBOX_GLOB))
    for path in inbox_files:
        records.extend(load_array(path))

    # Normalize, drop empties.
    normalized = [n for n in (normalize_lead(r) for r in records) if n]

    # De-duplicate by canonical post key (URL-based), keeping the newest occurrence.
    normalized.sort(key=lambda r: r["created_at"], reverse=True)
    seen: set[str] = set()
    merged: list[dict] = []
    for rec in normalized:
        key = dedupe_key(rec)
        if key in seen:
            continue
        seen.add(key)
        merged.append(rec)

    merged = merged[:MAX_LEADS]

    with open(LEADS_PATH, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    # Clear processed inbox files (the Action commit uses GITHUB_TOKEN, which does
    # not re-trigger the workflow, so there is no risk of a loop).
    for path in inbox_files:
        os.remove(path)

    print(f"Merged {len(merged)} unique leads from {len(inbox_files)} inbox file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
