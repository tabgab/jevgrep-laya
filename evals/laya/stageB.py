"""Stage B: run the patched jg (Laya provider) on each task and score its file list.

Usage: python3 stageB.py [task_id ...]  -> writes out/<id>.stdout, out/<id>.trace.jsonl, stageB.json
"""
import json, os, re, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.environ.get("LAYA_EVAL_DATA", os.path.join(HERE, "results"))
REPO = os.path.dirname(os.path.dirname(HERE))
BASE = EVAL
CLI = os.path.join(REPO, "apps", "cli", "dist", "bin", "index.js")
tasks = json.load(open(os.path.join(EVAL, "tasks.json")))
queries = json.load(open(os.path.join(EVAL, "queries.json")))
bm25 = json.load(open(os.path.join(EVAL, "bm25.json")))
# EVAL_TAG names a provider run: its outputs and jg config get the tag as a suffix.
TAG = "." + os.environ["EVAL_TAG"] if os.environ.get("EVAL_TAG") else ""
wanted = set(sys.argv[1:])
os.makedirs(os.path.join(EVAL, "out"), exist_ok=True)
out_path = os.path.join(EVAL, f"stageB{TAG}.json")
results = json.load(open(out_path)) if os.path.exists(out_path) else {}

for task in tasks:
    tid = task["id"]
    if wanted and tid not in wanted:
        continue
    trace = os.path.join(EVAL, "out", f"{tid}{TAG}.trace.jsonl")
    if os.path.exists(trace):
        os.remove(trace)
    env = dict(os.environ, XDG_CONFIG_HOME=os.path.join(BASE, f"jg-config{TAG}"),
               XDG_CACHE_HOME=os.path.join(BASE, f"jg-cache{TAG}"), JG_TRACE_FILE=trace)
    start = time.time()
    try:
        proc = subprocess.run(["node", CLI, queries[tid], os.path.join(EVAL, "repos", tid), "--no-cache"],
                              capture_output=True, text=True, env=env, timeout=int(os.environ.get("EVAL_TIMEOUT", "3600")))
        stdout, stderr, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as e:
        raw = e.stdout or ""
        stdout = raw.decode() if isinstance(raw, bytes) else str(raw)
        stderr, code = "timeout", "timeout"
    elapsed = time.time() - start
    open(os.path.join(EVAL, "out", f"{tid}{TAG}.stdout"), "w").write(stdout + "\n--- stderr ---\n" + stderr)
    files = re.findall(r'^- "([^"]+)"', stdout.split("End file list.")[0], re.M)
    gold, tests = task["gold_files"], task["test_files"]
    requests = sum(1 for _ in open(trace)) if os.path.exists(trace) else 0
    n = len(files)
    results[tid] = {
        "exit": code, "seconds": round(elapsed), "requests": requests,
        "returned": n, "files": files, "summary": stdout.splitlines()[:2],
        "gold_found": [g for g in gold if g in files], "gold_total": len(gold),
        "test_found": [t for t in tests if t in files], "test_total": len(tests),
        # Keyword baseline at the same budget: how many gold files BM25 puts in its top n (at least 10).
        "bm25_gold_at_n": sum(1 for g in gold if g in bm25[tid][:max(n, 10)]),
        "bm25_n": max(n, 10),
    }
    r = results[tid]
    print(f"{tid:34} exit={code} {r['seconds']:5}s req={requests:5} returned={n:3} "
          f"gold {len(r['gold_found'])}/{len(gold)} tests {len(r['test_found'])}/{len(tests)} "
          f"| bm25@{r['bm25_n']} gold {r['bm25_gold_at_n']}/{len(gold)}", flush=True)
    json.dump(results, open(out_path, "w"), indent=1)
