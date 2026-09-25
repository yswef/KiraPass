"""Full user-journey check through the web API: scan -> format -> calibrate -> run.

Start the pieces first:

    python3 tools/practice_portal.py --port 8898 --card 020124042 \
        --pass-mode empty --ban-after 5000

    KIRAPASS_INTERNET_CHECKS="http://127.0.0.1:8898/generate_204|204" \
        python3 KiraPass.py --host 0.0.0.0 --port 8770 --token kirapass --no-browser

    python3 tools/checks/web_e2e.py
"""
import json
import sys
import time
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8770"
TOKEN = sys.argv[2] if len(sys.argv) > 2 else "kirapass"
PORTAL = sys.argv[3] if len(sys.argv) > 3 else "http://127.0.0.1:8898/login"


def call(path, data=None):
    url = BASE + path + ("&" if "?" in path else "?") + "token=" + TOKEN
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method="POST" if body else "GET",
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


def wait_job(job_id, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        job = call("/api/job?id=" + job_id)["job"]
        if job["state"] != "running":
            return job
        time.sleep(0.2)
    return {"state": "timeout", "result": {}, "error": "timeout"}


# ---- step 1: read the login page (the UI's first panel) -------------------
scan = call("/api/scan", {"url": PORTAL})
f = scan["portal"]["form"]
print("scan         : ok=%s HTTP %s in %s ms | method=%s user=%s pass=%s chap=%s" % (
    scan["ok"], scan["portal"]["status"], scan["ms"], f["method"], f["user_field"],
    f["pass_field"], bool(f.get("chap"))))
print("             : internet %s / %s" % (scan["internet"]["state"],
                                          scan["internet"]["detail"]))

# ---- step 2: the profile the wizard builds, plus the format preview -------
profile = {
    "name": "practice-small", "login_url": f["action"] or scan["portal"]["url"],
    "method": f["method"], "user_field": f["user_field"], "pass_field": f["pass_field"],
    "pass_mode": "empty", "charset": "0123456789", "length": 9,
    "prefix": "020124", "suffix": "", "dst_value": "", "send_dst": True,
    "send_popup": True, "extra_fields": f.get("extra_fields") or {},
    "success_words": [], "chap": f.get("chap"),
}
pv = call("/api/format/preview", {"profile": profile})
print("preview      : space=%s samples=%s problems=%s" % (pv.get("space"),
                                                          pv.get("samples"),
                                                          pv.get("problems")))
saved = call("/api/profiles/save", {"profile": profile})
print("save         : ok=%s problems=%s" % (saved.get("ok"), saved.get("problems")))

# ---- step 3: calibrate (background job) ----------------------------------
job = wait_job(call("/api/calibrate", {"profile": profile, "known_card": ""})["job"]["id"])
cal = job.get("result") or {}
print("calibrate    : state=%s ok=%s error=%s" % (job["state"], cal.get("ok"), cal.get("error")))
for s in cal.get("steps", []):
    print("             : %-18s %-4s %-22s %s" % (s["id"], "ok" if s["ok"] else "FAIL",
                                                 s["reason"], str(s.get("detail") or "")[:52]))
fp = cal.get("fingerprint") or {}
print("             : exact=%s dynamic_tokens=%s masked=%s patterns=%s samples=%s" % (
    fp.get("exact"), fp.get("dynamic_tokens"), fp.get("masked_values"),
    fp.get("learned_patterns"), fp.get("samples")))

# ---- step 4: run the whole space - the missing digits are in there -------
start = call("/api/run/start", {"profile": profile, "attempts": 1000, "threads": 8,
                                "delay_ms": 0, "verify": True, "auto_stop": True})
print("run          : ok=%s %s" % (start.get("ok"), start.get("error", "")))
t0, since, hits, events, st = time.time(), 0, [], 0, {}
while time.time() - t0 < 180:
    res = call("/api/run/status?since=%d" % since)
    st, since = res["status"], res["status"]["seq"]
    for e in res["events"]:
        events += 1
        if e["kind"] == "hit":
            hits.append(e["data"])
    if st["state"] in ("done", "idle") and not res["events"]:
        break
    time.sleep(0.3)

print("\n=== RESULT ===")
print("state=%s stop_reason=%s elapsed=%.1fs speed=%s req/s" % (
    st["state"], st.get("stop_reason"), time.time() - t0, st.get("speed")))
print("counters     :", json.dumps(st["counters"], ensure_ascii=False))
print("reason_counts:", json.dumps(st.get("reason_counts", {}), ensure_ascii=False))
print("progress     :", json.dumps(st["progress"], ensure_ascii=False))
print("net_kinds    :", json.dumps(st.get("net_kinds", {})))
print("latency      :", json.dumps(st.get("latency", {})))
print("hits         :", json.dumps(hits, ensure_ascii=False))
print("events seen  :", events)

# ---- step 5: "continue where you stopped" ---------------------------------
# The page sends the saved walk position back with the profile.  A second run
# must start there instead of guessing the same cards again.
resume = dict(profile, name="practice-resume", prefix="030124")
call("/api/profiles/save", {"profile": resume})
print()


def run_some(n):
    # exactly what the page does: send the profile back with the position the
    # engine saved after the previous run
    saved = call("/api/profiles/get?name=practice-resume")["profile"]
    payload = dict(resume, space_pos=saved.get("space_pos", 0),
                   walk_a=saved.get("walk_a", 0), walk_b=saved.get("walk_b", 0))
    call("/api/run/start", {"profile": payload, "attempts": n, "threads": 6,
                            "delay_ms": 0, "verify": True, "auto_stop": True,
                            "resume": True})
    t0, st = time.time(), {}
    while time.time() - t0 < 120:
        st = call("/api/run/status?since=0")["status"]
        if st["state"] == "done":
            break
        time.sleep(0.3)
    saved = call("/api/profiles/get?name=practice-resume")["profile"]
    return st, saved


first_st, first_prof = run_some(150)
second_st, second_prof = run_some(150)
first_pos = first_prof.get("space_pos", 0)
second_pos = second_prof.get("space_pos", 0)
same_walk = (first_prof.get("walk_a") == second_prof.get("walk_a")
             and first_prof.get("walk_b") == second_prof.get("walk_b"))
ok = first_pos == 150 and second_pos == 300 and same_walk
print("resume       : ok=%s first run ended at %s, second at %s, same walk=%s"
      % (ok, first_pos, second_pos, same_walk))
if not ok:
    print("  FAILED: the second run did not continue where the first stopped")
    raise SystemExit(1)
