#!/usr/bin/env python3
import json, os, shutil, socket, subprocess, time, sys
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
START = time.time()

def tcp_check(host, port, timeout=2.0):
    s = socket.socket(); s.settimeout(timeout)
    try: s.connect((host, port)); return True, None
    except Exception as e: return False, str(e)
    finally: s.close()

def http_check(url, timeout=5.0):
    try:
        req = Request(url, headers={"Accept":"application/json"})
        with urlopen(req, timeout=timeout) as r:
            return (200 <= r.status < 400), f"status={r.status}"
    except HTTPError as e: return False, f"http_error={e.code}"
    except URLError as e: return False, f"url_error={e.reason}"
    except Exception as e: return False, repr(e)

def nvme_free_ok(path="/mnt/nvme", min_bytes=50*1024**3):
    try:
        usage = shutil.disk_usage(path)
        return usage.free >= min_bytes, {"total":usage.total,"free":usage.free}
    except FileNotFoundError: return False, {"error":"path_not_found"}
    except Exception as e: return False, {"error":repr(e)}

def gpu_vram_ok(max_used_bytes=20*1024**3):
    cap = int(os.getenv("SMOKE_MAX_VRAM_USED", str(max_used_bytes)))
    try:
        out = subprocess.check_output(
            ["nvidia-smi","--query-gpu=memory.used","--format=csv,noheader,nounits"],
            timeout=5
        ).decode().strip().splitlines()
        used_mb = sum(int(x) for x in out); used_bytes = used_mb*1024**2
        return used_bytes <= cap, {"used_bytes":used_bytes,"cap_bytes":cap}
    except FileNotFoundError: return True, {"skipped":True}
    except Exception as e: return False, {"error":repr(e)}

def main():
    fail = False; result = {"checks": {}, "meta": {"timeout_s":60}}
    ok, meta = nvme_free_ok(); result["checks"]["nvme_free"]={"ok":ok,"meta":meta}; fail |= not ok
    ok, err = tcp_check("127.0.0.1", 8001); result["checks"]["fastapi_tcp_8001"]={"ok":ok,"meta":{"err":err}}; fail |= not ok
    ok, detail = http_check(os.getenv("SMOKE_HEALTH_URL","http://127.0.0.1:8001/health"))
    result["checks"]["fastapi_http_health"]={"ok":ok,"meta":{"detail":detail}}; fail |= not ok
    ok, err = tcp_check("127.0.0.1", 8010); result["checks"]["llamacpp_tcp_8010"]={"ok":ok,"meta":{"err":err}}; fail |= not ok
    ok, err = tcp_check("127.0.0.1", 8080); result["checks"]["webui_tcp_8080"]={"ok":ok,"meta":{"err":err}}
    ok, meta = gpu_vram_ok(); result["checks"]["gpu_vram"]={"ok":ok,"meta":meta}; fail |= not ok
    result["duration_s"] = round(time.time()-START,3)
    print(json.dumps(result, separators=(",",":"))); sys.exit(1 if fail else 0)

if __name__ == "__main__": main()