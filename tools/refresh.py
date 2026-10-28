#!/usr/bin/env python3
"""Rebuild reviews.json: every Trustpilot / AppSumo / Poppy Wall review that names Killian.

Sources
  1. tools/trustpilot_seed.json  Trustpilot reviews collected by hand (Trustpilot blocks
                                 servers, so new ones arrive through source 3).
  2. AppSumo reviews API         public, read in full every run.
  3. getpoppy.ai/api/proof       the Poppy Wall of Love feed (Senja), which imports new
                                 Trustpilot reviews on its own.

Reviews already in reviews.json are never dropped, so a source that is down only means
"nothing new this run". Ids listed in hidden.json are left off the page.

Usage: python3 tools/refresh.py   (stdlib only; exits 0 even when a source fails)
"""
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "reviews.json"
HIDDEN = ROOT / "hidden.json"
SEED = ROOT / "tools" / "trustpilot_seed.json"

APPSUMO_DEAL = 255707
APPSUMO_API = "https://appsumo.com/api/v2/deals/{deal}/reviews/?page={page}&sort=date&order=desc&from={start}&items_per_page=50"
WALL_API = "https://getpoppy.ai/api/proof"

NAME = re.compile(r"\b(killian|kilian|killan|kilan|killion|kilion|kyllian|kylian)\b", re.I)
# Poppy team clips on the Wall (Killian's own video, setters talking about the team).
TEAM = re.compile(r"\b(setter|closer|onboarder|sdr)\b", re.I)
HASHY = re.compile(r"^([0-9a-f]{20,}|\d{12,})$")


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "killian-wall-of-love/1.0", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def day(s):
    return dt.date.fromisoformat(s[:10])


def same_person_same_day(a, b):
    return norm(a["name"]) == norm(b["name"]) and abs((day(a["date"]) - day(b["date"])).days) <= 1


def appsumo():
    rows, page = [], 1
    while True:
        batch = get_json(APPSUMO_API.format(deal=APPSUMO_DEAL, page=page, start=(page - 1) * 50)).get("comments") or []
        rows += batch
        if len(batch) < 50 or page >= 40:
            break
        page += 1
    out = []
    for c in rows:
        if not NAME.search(f"{c.get('title') or ''} {c.get('comment') or ''}"):
            continue
        u = c.get("user") or {}
        full = f"{u.get('first_name') or ''} {u.get('last_name') or ''}".strip()
        handle = u.get("username") or ""
        out.append({
            "id": f"as:{c['id']}",
            "source": "appsumo",
            "date": c["created"][:10],
            "name": full or (None if HASHY.match(handle) else handle),
            "avatar": u.get("avatar") if u.get("has_uploaded_avatar") else None,
            "deals": u.get("deals_purchased"),
            "since": (u.get("date_joined") or "")[:4] or None,
            "rating": c.get("rating") or 5,
            "title": (c.get("title") or "").strip() or None,
            "text": (c.get("comment") or "").strip(),
            "url": "https://appsumo.com" + c["display_path"] if c.get("display_path") else None,
        })
    return out


def wall():
    out = []
    for t in get_json(WALL_API).get("testimonials") or []:
        text = (t.get("text") or "").strip()
        if t.get("type") != "text" or not text or not NAME.search(text):
            continue
        if NAME.search(t.get("name") or "") or TEAM.search(t.get("tagline") or ""):
            continue
        out.append({
            "id": f"wall:{t['id']}",
            "source": "wall",
            "date": (t.get("date") or "")[:10],
            "name": t.get("name"),
            "role": ", ".join(x for x in (t.get("tagline"), t.get("company")) if x) or None,
            "avatar": t.get("avatar"),
            "rating": t.get("rating") or 5,
            "title": None,
            "text": text,
            "url": None,
        })
    return out


def main():
    prev = json.loads(OUT.read_text()) if OUT.exists() else {"reviews": []}
    hidden = set(json.loads(HIDDEN.read_text())) if HIDDEN.exists() else set()
    by_id = {r["id"]: r for r in prev["reviews"]}
    warnings = []

    for s in json.loads(SEED.read_text()):
        rid = f"tp:{s['id']}"
        if rid in by_id:
            continue
        r = {"id": rid, "source": "trustpilot", "date": s["date"], "name": s["name"],
             "country": s.get("country"), "avatar": s.get("avatar"), "rating": s.get("rating", 5),
             "title": s.get("title"), "text": s.get("text"),
             "url": f"https://www.trustpilot.com/reviews/{s['id']}"}
        by_id[rid] = r

    try:
        for r in appsumo():
            old = by_id.get(r["id"])
            by_id[r["id"]] = {**(old or {}), **r}
    except Exception as e:  # noqa: BLE001 - keep the page alive, report and move on
        warnings.append(f"AppSumo: {e}")

    try:
        for w in wall():
            if w["id"] in by_id:
                by_id[w["id"]].update(text=w["text"])
                continue
            twin = next((r for r in by_id.values() if r["source"] != "wall" and same_person_same_day(r, w)), None)
            if twin is None:
                twin = next((r for r in by_id.values() if norm(r.get("text"))[:80] and norm(r.get("text"))[:80] == norm(w["text"])[:80]), None)
            if twin is not None:
                if not twin.get("text"):
                    twin["text"] = w["text"]  # Trustpilot seed rows get their body from the Wall copy
                continue
            by_id[w["id"]] = w
    except Exception as e:  # noqa: BLE001
        warnings.append(f"Wall: {e}")

    reviews = [r for r in by_id.values() if r.get("text") and r["id"] not in hidden]
    missing = [r["id"] for r in by_id.values() if not r.get("text")]
    if missing:
        warnings.append(f"no text yet for {missing}")
    reviews.sort(key=lambda r: (r["date"], r["id"]), reverse=True)

    data = {"count": len(reviews), "reviews": reviews}
    old_core = {"count": prev.get("count"), "reviews": prev.get("reviews")}
    if data != old_core:
        data["updated"] = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        added = len({r["id"] for r in reviews} - {r["id"] for r in prev["reviews"]})
        print(f"reviews.json: {len(reviews)} reviews ({added} new)")
    else:
        print(f"reviews.json: no change ({len(reviews)} reviews)")
    for w in warnings:
        print("warning:", w, file=sys.stderr)


if __name__ == "__main__":
    main()
