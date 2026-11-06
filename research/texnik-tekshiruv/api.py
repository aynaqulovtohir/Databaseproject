import json, urllib.request, urllib.error, time
BASE = "http://127.0.0.1:8000/api/"
def call(method, path, token=None, data=None):
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
    try:
        with urllib.request.urlopen(req) as r:
            body = r.read(); return r.status, (json.loads(body) if body else None)
    except urllib.error.HTTPError as e:
        body = e.read()
        try: return e.code, json.loads(body)
        except Exception: return e.code, body[:300]
def login(u, p):
    for _ in range(12):
        s, d = call("POST", "auth/login/", data={"username": u, "password": p})
        if s == 200: return d["access"]
        if s == 429: time.sleep(13); continue
        raise SystemExit(f"login {u}: {s} {d}")
    raise SystemExit("login throttled")
