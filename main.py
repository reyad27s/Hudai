#!/usr/bin/env python3
# Toffee BD Cookie Auto-Ingest
# Bangladesh theke chalan (Android Termux / PC / BD VPS / Ubuntu).
# Eta protibar Toffee theke fresh cookie + special edge-cache-token niye
# apnar website e pathay.

import json, time, sys, urllib.request, urllib.error, urllib.parse, base64

INGEST_URL = "https://toffee-stream-keeper.lovable.app/api/public/ingest-cookies"
ADMIN_PASSWORD = "shanto@#27"
INTERVAL_SECONDS = 20  # 20 second


DEFAULT_CID = "xi6xX5UBv9knK3AH9aMk"
SPECIAL_CID = "zUGrjZ4BuUSiBsg_1BeE"
# Bearer token — admin panel theke auto-sync hoy. Panel a token change korle
# "Copy Script" abar tap kore notun script niye nin.
BEARER = "Bearer eyJhbGciOiJFUzI1NiIsInR5cCI6IkpXVCJ9.eyJhdWQiOiJodHRwczovL3RvZmZlZWxpdmUuY29tIiwiY291bnRyeSI6IkJEIiwiZF9pZCI6IjZhYTA2NDFmLWY5ZjYtNGZjOC04NzdiLWM4YjFiYTc5MDlkMCIsImV4cCI6MTc4Nzc0MTY5MywiaWF0IjoxNzgzODUzNjkzLCJpc3MiOiJ0b2ZmZWVsaXZlLmNvbSIsImp0aSI6Ijg4NTNhNzc0LTY2ZDctNDNiMy1iOWJmLWViMzE1ZTQ4NjQ5YV8xNzgzODUzNjkzIiwicHJvdmlkZXIiOiJ0b2ZmZWUiLCJyX2lkIjoiY2Q5YmUwNjEtMDUyNS00OWIwLTkxMjAtMGFmOGI4NGQ4NTk2Iiwic19pZCI6ImRkODJmZTQ0LThkNmItNDMzMC1hZDM4LWE2YTU1MDA2NzQwYiIsInRva2VuIjoiYWNjZXNzIiwidHlwZSI6InN1YnNjcmliZXIifQ.UQdzZfVTCl2XVhJjyNaes_xjxK4XZtIbfCBnpSDN9QzMdjiZjXnE-o7HEfDi-DSU42DyuW2_bAtyh9DbAyjh8g"

UA_APP = "okhttp/4.11.0"
UA_PLAYER = "Toffee/8.10.1 (Linux;Android 14) ExoPlayerLib/2.18.6"

def clean_cookie(raw):
    # Handles new multi-cookie format. 'raw' can be one header or several joined
    # with newlines. Splits into name=value pairs and drops attributes
    # (Domain/Path/Expires/Max-Age/Secure/HttpOnly/SameSite/Priority/Partitioned).
    import re
    if not raw:
        return ""
    ATTRS = {"domain","path","expires","max-age","secure","httponly","samesite","priority","partitioned"}
    pairs = []
    for header in [h for h in raw.split("\n") if h]:
        # split on ", " only when followed by 'name=' (avoid splitting Expires dates)
        for part in re.split(r",(?=\s*[A-Za-z0-9_\-]+=)", header):
            for seg in [s.strip() for s in part.split(";") if s.strip()]:
                name = seg.split("=", 1)[0]
                if name.lower() in ATTRS:
                    continue
                pairs.append(seg)
    seen = {}
    order = []
    for kv in pairs:
        n = kv.split("=", 1)[0]
        if n not in seen:
            order.append(n)
        seen[n] = kv
    return "; ".join(seen[n] for n in order)

def collect_set_cookie(headers):
    # Get every Set-Cookie header, joined with newline for clean_cookie.
    try:
        vals = headers.get_all("Set-Cookie") or []
    except Exception:
        v = headers.get("set-cookie", "")
        vals = [v] if v else []
    return "\n".join(vals)

def fetch_default():
    req = urllib.request.Request(
        f"https://entitlement-prod.services.toffeelive.com/toffee/BD/DK/android-mobile/playback/{DEFAULT_CID}",
        data=b"{}", method="POST",
        headers={"Authorization": BEARER, "Content-Type": "application/json; charset=utf-8", "User-Agent": UA_APP},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        sc = collect_set_cookie(r.headers)
        r.read()
    return clean_cookie(sc)

def fetch_special():
    req = urllib.request.Request(
        f"https://entitlement-prod.services.toffeelive.com/toffee/BD/DK/android-mobile/playback/{SPECIAL_CID}",
        data=b"{}", method="POST",
        headers={"Authorization": BEARER, "Content-Type": "application/json; charset=utf-8", "User-Agent": UA_APP},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8"))
    url = data.get("playbackDetails", {}).get("data", [{}])[0].get("url", "")
    if not url:
        raise RuntimeError("special playback url missing")
    # Extract the edge-cache-token query string from the playback url
    token = ""
    q = url.split("?", 1)[1] if "?" in url else ""
    if "edge-cache-token=" in q.lower():
        token = q
    # Manual redirect chase to capture Set-Cookie on 302 (cookie optional)
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    opener = urllib.request.build_opener(NoRedirect)
    cookie = ""
    for _ in range(5):
        req2 = urllib.request.Request(url, headers={"User-Agent": UA_PLAYER})
        try:
            r2 = opener.open(req2, timeout=20)
            sc = collect_set_cookie(r2.headers)
            if sc: cookie = clean_cookie(sc)
            break
        except urllib.error.HTTPError as e:
            sc = collect_set_cookie(e.headers)
            if sc: cookie = clean_cookie(sc)
            if 300 <= e.code < 400:
                loc = e.headers.get("location")
                if not loc: break
                url = urllib.parse.urljoin(url, loc)
                q = url.split("?", 1)[1] if "?" in url else ""
                if "edge-cache-token=" in q.lower():
                    token = q
                if cookie: break
                continue
            break
        except Exception:
            break
    # Return whatever we have; empty cookie is fine — ingest endpoint preserves stored cookie
    return cookie, token


def push(default_cookie, special_cookie, special_token):
    params = urllib.parse.urlencode({
        "password": ADMIN_PASSWORD,
        "default_cookie": default_cookie,
        "special_cookie": special_cookie,
        "special_token": special_token,
    })
    req = urllib.request.Request(
        f"{INGEST_URL}?{params}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try: body = e.read().decode("utf-8", "ignore")
        except Exception: pass
        raise RuntimeError(f"ingest {e.code} {e.reason} url={INGEST_URL} body={body[:300]}")

_last = {"d": "", "s": "", "t": ""}

def once():
    d = ""
    s = ""
    t = ""
    try: d = fetch_default()
    except Exception as e: print("default error:", e, file=sys.stderr)
    try:
        s, t = fetch_special()
    except Exception as e: print("special error:", e, file=sys.stderr)
    if not d and not s and not t:
        print("nothing fetched"); return
    if d == _last["d"] and s == _last["s"] and t == _last["t"]:
        print("no change, skip push"); return
    print("push:", push(d, s, t))
    _last["d"] = d
    _last["s"] = s
    _last["t"] = t

if __name__ == "__main__":
    while True:
        try: once()
        except Exception as e: print("loop error:", e, file=sys.stderr)
        time.sleep(INTERVAL_SECONDS)
