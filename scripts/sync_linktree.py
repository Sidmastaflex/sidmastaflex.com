"""Sync Upcoming Events from Linktree -> assets/events.json (+ flyer thumbnails).

Runs in GitHub Actions on a schedule. Only ticketing/RSVP links count as events;
socials, music links, and the site's own link are ignored.
"""
import os, re, json, hashlib, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS_JSON = os.path.join(ROOT, "assets", "events.json")
FLYER_DIR = os.path.join(ROOT, "assets", "events")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36"}

EVENT_DOMAINS = (
    "posh.vip", "eventbrite.", "partiful.com", "ticketfairy.com", "dice.fm",
    "ra.co", "residentadvisor.", "shotgun.live", "tixr.com", "seetickets.",
    "ticketweb.", "universe.com", "withfriends.co", "eventvesta.com", "tickettailor.com",
)

def fetch(url):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read()

def main():
    html = fetch("https://linktr.ee/sidmastaflex").decode("utf-8", "ignore")
    m = re.search(r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise SystemExit("Linktree page structure changed: no __NEXT_DATA__")
    links = json.loads(m.group(1))["props"]["pageProps"]["account"]["links"]

    events = []
    for l in links:
        url = (l.get("url") or "").strip()
        if not url or not any(d in url.lower() for d in EVENT_DOMAINS):
            continue
        eid = hashlib.sha1(url.encode()).hexdigest()[:12]
        ev = {"id": eid, "title": (l.get("title") or "").strip(), "url": url, "image": ""}
        img_path = os.path.join(FLYER_DIR, eid + ".jpg")
        if os.path.exists(img_path):
            ev["image"] = f"assets/events/{eid}.jpg"
        else:
            try:
                page = fetch(url).decode("utf-8", "ignore")
                im = (re.search(r'property="og:image"\s+content="([^"]+)"', page)
                      or re.search(r'content="([^"]+)"\s+property="og:image"', page)
                      or re.search(r'name="twitter:image"\s+content="([^"]+)"', page))
                if im:
                    img_url = im.group(1).replace("&amp;", "&")
                    if "_next/image" in img_url:  # eventbrite proxy
                        from urllib.parse import parse_qs, urlparse, urljoin
                        img_url = parse_qs(urlparse(img_url).query).get("url", [img_url])[0]
                    if img_url.startswith("/"):
                        from urllib.parse import urljoin
                        img_url = urljoin(url, img_url)
                    data = fetch(img_url)
                    if len(data) > 5000:
                        os.makedirs(FLYER_DIR, exist_ok=True)
                        with open(img_path, "wb") as f:
                            f.write(data)
                        ev["image"] = f"assets/events/{eid}.jpg"
                ot = re.search(r'property="og:title"\s+content="([^"]+)"', page)
                if ot and not ev["title"]:
                    ev["title"] = ot.group(1)
            except Exception:
                pass
        events.append(ev)

    old = ""
    if os.path.exists(EVENTS_JSON):
        with open(EVENTS_JSON, encoding="utf-8") as f:
            old = f.read()
    new = json.dumps({"events": events}, indent=1)
    if new != old:
        with open(EVENTS_JSON, "w", encoding="utf-8") as f:
            f.write(new)
        print(f"CHANGED: {len(events)} event(s)")
    else:
        print(f"UNCHANGED: {len(events)} event(s)")

if __name__ == "__main__":
    main()
