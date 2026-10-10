#!/usr/bin/env python3
"""Enrich quote.json with routing: stop coordinates, per-segment drive distance
and time (OSRM), and a static map PNG (OpenStreetMap tiles) for the PDF.

Opt-in; best-effort. Uses free public services (Nominatim geocoding, the OSRM
demo router, OSM tiles) — fine for a few quotes a day, and every failure is
non-fatal: the quote still renders, just without the map/times.

Usage: route_map.py quote.json [--map out.png] [--no-map]
Writes into quote.json:
  legs[].stops[].lat/lon            (geocoded; skipped for as-directed stops)
  legs[].route = {"distance_mi": 3.7, "drive_min": 8, "segments": [...]}
  route_map = {"png": "<path>", "attribution": "© OpenStreetMap contributors"}
"""
import argparse
import io
import json
import math
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = {"User-Agent": "savoya-quote-document/0.6 (ops@savoya.com)"}
COPPER = (184, 115, 51)
USED_OFFLINE = False   # set when the basemap was unavailable and we drew the schematic


def get(url, timeout=15):
    r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
    return r.read()


def geocode(q, cache):
    """Nominatim is a free, rate-limited service. A transient failure here used to
    drop the stop from the route silently, which produced a confidently wrong drive
    time (see main()). Retry once before giving up; a miss is cached, an ERROR is not."""
    if q in cache:
        return cache[q]
    url = "https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": q, "format": "json", "limit": 1})
    for attempt in (1, 2):
        try:
            res = json.loads(get(url))
            cache[q] = (float(res[0]["lat"]), float(res[0]["lon"])) if res else None
            time.sleep(1.1)  # Nominatim usage policy: max 1 req/s
            return cache[q]
        except Exception as ex:
            if attempt == 1:
                time.sleep(2.0)
                continue
            print(f"WARNING: geocode failed for {q!r}: {ex}", file=sys.stderr)
    cache[q] = None
    time.sleep(1.1)
    return None


def osrm(coords):
    """coords: [(lat, lon), ...] → (distance_m, duration_s, [(lat, lon) polyline])

    The OSRM demo router is free and rate-limited exactly like Nominatim, but only
    the geocoder was ever hardened for it. A 16-leg World Cup quote fired 16 routing
    calls back to back with no retry and no delay; 8 came back refused, and those legs
    reached the client's PDF showing a drive time with an em dash where the distance
    should have been. Same retry-once-and-throttle treatment as geocode(), for the
    same reason."""
    path = ";".join(f"{lon},{lat}" for lat, lon in coords)
    url = f"https://router.project-osrm.org/route/v1/driving/{path}?overview=simplified&geometries=geojson"
    last = None
    for attempt in (1, 2):
        try:
            r = json.loads(get(url, 20))
            rt = r["routes"][0]
            line = [(lat, lon) for lon, lat in rt["geometry"]["coordinates"]]
            time.sleep(1.1)   # same courtesy rate as Nominatim; the demo router asks for it
            return rt["distance"], rt["duration"], line
        except Exception as ex:
            last = ex
            if attempt == 1:
                time.sleep(2.0)
    raise last


# ---------------------------------------------------------------- static map
def lonlat_to_px(lat, lon, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n * 256
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n * 256
    return x, y


# Every CSM is on macOS and this path is Linux-only, so `truetype` always raised and
# every label on every map fell back to Pillow's default bitmap face — at its own fixed
# size, ignoring the 16pt and 13pt asked for. The map still rendered, so nothing failed
# and nobody reported a font bug; it just looked worse on every machine but a Linux one.
_FONT_CANDIDATES = {
    "bold": ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",            # macOS
             "/System/Library/Fonts/Helvetica.ttc",                          # macOS, older
             "C:/Windows/Fonts/arialbd.ttf",                                 # Windows
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",         # Debian/Ubuntu
             "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),                 # Fedora/Arch
    "regular": ("/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/Helvetica.ttc",
                "C:/Windows/Fonts/arial.ttf",
                "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                "/usr/share/fonts/dejavu/DejaVuSans.ttf"),
}


def load_font(weight, size):
    """A real face at the requested size on macOS, Windows or Linux; Pillow's default
    only if the machine genuinely has none of them."""
    from PIL import ImageFont
    for path in _FONT_CANDIDATES[weight]:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size)      # Pillow >= 10.1 scales this
    except TypeError:
        return ImageFont.load_default()


def render_offline(points, lines, out_png, w=1100, h=620):
    """A basemap-free route overview: stops in their true relative positions, joined in
    order. Needs no network — the engine already resolved every stop's coordinates.
    Used when the tile service is unreachable (some corporate networks block it)."""
    global USED_OFFLINE
    from PIL import Image, ImageDraw, ImageFont
    lats = [p[0] for p in points]
    lons = [p[1] for p in points]
    if len(points) < 2:
        return None
    lat0, lat1, lon0, lon1 = min(lats), max(lats), min(lons), max(lons)
    dlat, dlon = max(lat1 - lat0, 1e-4), max(lon1 - lon0, 1e-4)
    pad = 90

    def place(lat, lon):
        # y inverted: north at the top
        x = pad + (lon - lon0) / dlon * (w - 2 * pad)
        y = pad + (lat1 - lat) / dlat * (h - 2 * pad)
        return x, y

    img = Image.new("RGB", (w, h), (247, 245, 242))
    d = ImageDraw.Draw(img)
    for gx in range(0, w, 55):
        d.line([(gx, 0), (gx, h)], fill=(237, 234, 229), width=1)
    for gy in range(0, h, 55):
        d.line([(0, gy), (w, gy)], fill=(237, 234, 229), width=1)
    font, small = load_font("bold", 16), load_font("regular", 13)
    ordered = sorted(points, key=lambda p: p[2])
    pts = [place(p[0], p[1]) for p in ordered]
    if len(pts) > 1:
        d.line(pts, fill=(255, 255, 255), width=9)
        d.line(pts, fill=COPPER, width=5)
    for (x, y), p in zip(pts, ordered):
        d.ellipse([x - 14, y - 14, x + 14, y + 14], fill=(20, 20, 20), outline=(255, 255, 255), width=3)
        d.text((x, y), str(p[2]), fill=(255, 255, 255), font=font, anchor="mm")
    d.text((22, 18), "Route overview", fill=(60, 56, 52), font=font)
    d.text((22, h - 30), "Stops shown in relative position; drive times from the Savoya quoting engine",
           fill=(120, 115, 108), font=small)
    USED_OFFLINE = True
    img.save(out_png, optimize=True)
    return out_png


def render_map(points, lines, out_png, w=1100, h=620):
    from PIL import Image, ImageDraw, ImageFont
    lats = [p[0] for p in points] + [q[0] for l in lines for q in l]
    lons = [p[1] for p in points] + [q[1] for l in lines for q in l]
    if not lats:
        return None
    lat0, lat1, lon0, lon1 = min(lats), max(lats), min(lons), max(lons)
    pad = 0.15
    dlat, dlon = max(lat1 - lat0, 0.005), max(lon1 - lon0, 0.005)
    lat0, lat1, lon0, lon1 = lat0 - dlat * pad, lat1 + dlat * pad, lon0 - dlon * pad, lon1 + dlon * pad
    z = 18
    while z > 2:
        x0, y0 = lonlat_to_px(lat1, lon0, z); x1, y1 = lonlat_to_px(lat0, lon1, z)
        if x1 - x0 <= w and y1 - y0 <= h:
            break
        z -= 1
    x0, y0 = lonlat_to_px(lat1, lon0, z); x1, y1 = lonlat_to_px(lat0, lon1, z)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    left, top = cx - w / 2, cy - h / 2
    img = Image.new("RGB", (w, h), (235, 232, 228))
    tx0, ty0 = int(left // 256), int(top // 256)
    tx1, ty1 = int((left + w) // 256), int((top + h) // 256)
    got = want = 0
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            want += 1
            try:
                tile = Image.open(io.BytesIO(get(f"https://tile.openstreetmap.org/{z}/{tx}/{ty}.png", 10))).convert("RGB")
                # soften the basemap so the route reads first
                tile = Image.blend(tile, Image.new("RGB", tile.size, (250, 248, 245)), 0.35)
                img.paste(tile, (int(tx * 256 - left), int(ty * 256 - top)))
                got += 1
            except Exception:
                pass
    # Every tile failure used to be swallowed, leaving a flat background that still
    # saved, still reported success, and still went into the client's PDF as a blank
    # rectangle. No basemap means no map.
    if want and got < want * 0.6:
        # No basemap. Rather than a blank panel — or nothing at all, on a network that
        # blocks the tile service outright — draw the overview from what the engine
        # already gave us: every stop's coordinates, in order.
        print(f"WARNING: only {got}/{want} map tiles loaded — drawing the offline route "
              f"overview from Savoya location data instead", file=sys.stderr)
        return render_offline(points, lines, out_png, w, h)
    d = ImageDraw.Draw(img)
    for line in lines:
        pts = [(lonlat_to_px(a, b, z)[0] - left, lonlat_to_px(a, b, z)[1] - top) for a, b in line]
        if len(pts) > 1:
            d.line(pts, fill=(255, 255, 255), width=9)
            d.line(pts, fill=COPPER, width=5)
    font = load_font("bold", 16)
    for i, (lat, lon, label) in enumerate(points):
        x, y = lonlat_to_px(lat, lon, z); x -= left; y -= top
        d.ellipse([x - 13, y - 13, x + 13, y + 13], fill=(20, 20, 20), outline=(255, 255, 255), width=3)
        d.text((x, y), str(label), fill=(255, 255, 255), font=font, anchor="mm")
    d.rectangle([w - 232, h - 22, w, h], fill=(255, 255, 255))
    d.text((w - 226, h - 18), "© OpenStreetMap contributors", fill=(90, 86, 80), font=ImageFont.load_default())
    img.save(out_png, optimize=True)
    return out_png


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("quote"); ap.add_argument("--map", default=None); ap.add_argument("--no-map", action="store_true")
    a = ap.parse_args()
    q = json.load(open(a.quote, encoding="utf-8"))
    cache, points, lines, marker = {}, [], [], 0
    seen_pts = {}
    # a market to qualify bare street addresses with; without it Nominatim matches
    # "16 Ferris Avenue" to Melbourne, Australia
    fallback_area = (q.get("meta") or {}).get("service_area")
    for leg in q["legs"]:
        coords = []
        wanted = 0          # stops this leg intends to route through
        for s in leg["stops"]:
            if s.get("as_directed"):
                continue
            wanted += 1
            if s.get("lat") is not None and s.get("lon") is not None:
                ll = (s["lat"], s["lon"])          # already resolved — never re-geocode
            else:
                area = leg.get("service_area") or fallback_area
                if not area:
                    print(f"WARNING: {leg.get('key')}: no service area to qualify '{s.get('address') or s.get('label')}' "
                          f"— skipping geocode rather than risk the wrong city", file=sys.stderr)
                    continue
                base = s.get("address") or s.get("label") or ""
                query = ", ".join(x for x in [base, area] if x)
                ll = geocode(query, cache)
                if not ll and s.get("label"):
                    ll = geocode(", ".join([s["label"], area]), cache)
                # `area` is Core's service-area name, and those are markets, not
                # places: no public geocoder resolves "Dallas/Fort Worth". Both
                # attempts above carry it, so a perfectly good street address can
                # fail purely because of the qualifier. Retry bare — but only when
                # the address has a street number in it. Qualifying exists so that
                # "Hilton" does not land in the wrong city, and a bare landmark
                # would reintroduce exactly that.
                if not ll and re.search(r"\d", base) and area:
                    ll = geocode(base, cache)
                    if ll:
                        print(f"WARNING: {base!r} only resolved without the market "
                              f"qualifier {area!r} — market names are not geocodable",
                              file=sys.stderr)
            if ll:
                s["lat"], s["lon"] = ll
                coords.append(ll)
                key = (round(ll[0], 4), round(ll[1], 4))
                if key not in seen_pts and not leg.get("alternative_of"):
                    marker += 1
                    seen_pts[key] = marker
                    points.append((ll[0], ll[1], marker))
                s["marker"] = seen_pts.get(key)
        # A stop that failed to resolve used to be dropped from `coords` while the
        # remaining points still routed fine — so an out-and-back whose midpoint was
        # lost came back as "0.0 mi · 0 min" and shipped to the client as fact.
        # A partial route is worse than no route: publish nothing rather than a lie.
        if len(coords) < wanted:
            print(f"WARNING: {leg['key']}: {wanted - len(coords)} of {wanted} stops did not resolve "
                  f"— no drive time for this leg (a partial route would understate it)", file=sys.stderr)
        elif len(coords) >= 2:
            try:
                dist, dur, line = osrm(coords)
                drive_min = int(round(dur / 60))
                # The polyline is all we need for the map; draw it either way.
                if not leg.get("alternative_of"):
                    lines.append(line)
                if dist < 1.0 or drive_min < 1:
                    # every stop resolved yet the route is ~zero: the stops collapsed to
                    # one point (duplicate geocode hit). Not a real 0-minute drive.
                    print(f"WARNING: {leg['key']}: route came back ~0 miles across {wanted} stops "
                          f"— ignoring, no drive time from routing", file=sys.stderr)
                elif (leg.get("route") or {}).get("source") == "engine":
                    # Savoya's engine already gave a drive time for this leg. It accounts
                    # for the real itinerary and is the number the web app shows; the public
                    # demo router does not. Keep the engine's minutes, borrow only distance.
                    leg["route"]["distance_mi"] = round(dist / 1609.344, 1)
                    leg["route"]["segments"] = len(coords) - 1
                else:
                    leg["route"] = {"distance_mi": round(dist / 1609.344, 1), "drive_min": drive_min,
                                    "segments": len(coords) - 1, "source": "routing"}
            except Exception as ex:
                print(f"WARNING: routing failed for {leg['key']}: {ex}", file=sys.stderr)
        else:
            print(f"WARNING: {leg['key']}: fewer than 2 geocodable stops; no route", file=sys.stderr)

    # A mixed distance column is the failure this file already forbids per leg, one
    # level up. Routing is per-leg and best-effort, so a partial outage leaves some
    # rows reading "~12.4 mi · ~25 min" and others "— · ~25 min": to a client that is
    # not a degraded estimate, it is a broken document, and nothing downstream could
    # see it because every check was per-leg and a leg without a distance is
    # individually valid. Distances are an approximate planning courtesy; the drive
    # times are the engine's and stay. So publish the column for every routable leg
    # or for none.
    routable = [l for l in q["legs"]
                if not l.get("alternative_of")
                and len([s for s in l.get("stops", []) if not s.get("as_directed")]) >= 2]
    with_dist = [l for l in routable if (l.get("route") or {}).get("distance_mi") is not None]
    if with_dist and len(with_dist) < len(routable):
        for l in with_dist:
            l["route"].pop("distance_mi", None)
            l["route"].pop("segments", None)
        print(f"WARNING: ROUTE DEGRADED — distance came back for only {len(with_dist)} of "
              f"{len(routable)} routable legs, so the distance column is dropped from all of "
              f"them rather than printed half-filled. Drive times are unaffected (they are "
              f"the engine's). Re-run the route map to try the public router again.",
              file=sys.stderr)

    if not a.no_map and points:
        out = a.map or os.path.splitext(a.quote)[0] + ".route-map.png"
        made = None
        try:
            made = render_map(points, lines, out)
        except Exception as ex:
            print(f"WARNING: map render failed: {ex}", file=sys.stderr)
        if made:
            q["route_map"] = {
                "png": os.path.abspath(out),
                "style": "offline" if USED_OFFLINE else "tiled",
                "attribution": ("Route overview drawn from Savoya location data; drive times from "
                                "the Savoya quoting engine") if USED_OFFLINE else "© OpenStreetMap contributors"}
        elif q.pop("route_map", None):
            # a map from an earlier run must not survive a failed one — it would be
            # embedded as if current, or point at a file that no longer exists
            print("WARNING: dropped the previous route map; this run did not produce one",
                  file=sys.stderr)
    json.dump(q, open(a.quote, "w", encoding="utf-8"), indent=2)
    for leg in q["legs"]:
        r = leg.get("route")
        if not r:
            print(f"  {leg.get('ref')}: no route")
            continue
        bits = []
        if r.get("distance_mi") is not None:
            bits.append(f"~{r['distance_mi']} mi")
        if r.get("drive_min") is not None:
            bits.append(f"~{r['drive_min']} min drive")
        print(f"  {leg.get('ref')}: " + (" · ".join(bits) or "no route")
              + (f"  [{r['source']}]" if r.get("source") else ""))
    if q.get("route_map"):
        print(f"Map: {q['route_map']['png']}")


if __name__ == "__main__":
    main()
