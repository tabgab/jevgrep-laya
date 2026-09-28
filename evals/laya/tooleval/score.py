"""Score tool-selection results. Ties are scored by their expected value under random tie-breaking."""
import json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
tasks = {t["id"]: t for t in json.load(open(os.path.join(HERE, "tasks.json")))}
schemas = {}
for line in open(os.path.join(HERE, "multiple.jsonl")):
    for f in json.loads(line)["function"]:
        schemas.setdefault(f["name"], len(json.dumps(f)))


def hit(scores, correct, k, names=None):
    names = names or list(scores)
    p = scores.get(correct, float("-inf"))
    greater = sum(1 for n in names if scores.get(n, float("-inf")) > p)
    ties = sum(1 for n in names if scores.get(n, float("-inf")) == p)  # includes the correct tool
    return 0.0 if greater >= k else min(1.0, (k - greater) / ties)


def score(model):
    path = os.path.join(HERE, f"results.{model}.json")
    if not os.path.exists(path):
        return None
    res = json.load(open(path))
    out: dict = {"n": len(res)}
    for k in (1, 3, 5):
        out[f"top{k}"] = statistics.mean(hit(r["probabilities"], tasks[i]["correct"], k) for i, r in res.items())
    out["own_top1"] = statistics.mean(
        hit(r["probabilities"], tasks[i]["correct"], 1, tasks[i]["own"]) for i, r in res.items())
    secs = [r["seconds"] for r in res.values() if "seconds" in r]
    out["seconds_median"] = statistics.median(secs) if secs else None
    routes = [((r.get("routing") or {}).get("model")) for r in res.values()]
    out["routing"] = {m: routes.count(m) for m in set(routes) if m}
    # Prompt cost of handing the LLM the top 3 tools instead of all 20 (full JSON schemas).
    full = statistics.mean(sum(schemas[t["name"]] for t in tasks[i]["tools"]) for i in res)
    top3 = statistics.mean(
        sum(schemas[n] for n in sorted(r["probabilities"], key=lambda n: -r["probabilities"][n])[:3]) for r in res.values())
    out["schema_bytes_all20"], out["schema_bytes_top3"] = round(full), round(top3)
    return out


summary: dict = {m: score(m) for m in ["laya", "laya-multilingual", "openjev", "bm25"]}
summary["random"] = {"top1": 1 / 20, "top3": 3 / 20, "top5": 5 / 20,
                     "own_top1": statistics.mean(1 / len(t["own"]) for t in tasks.values())}
json.dump(summary, open(os.path.join(HERE, "summary.json"), "w"), indent=1)
for m, s in summary.items():
    if s:
        print(f"{m:18}", {k: (round(v, 3) if isinstance(v, float) else v) for k, v in s.items()})
