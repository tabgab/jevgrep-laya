"""Tool selection test: can a decision model pick the right tool out of 20 for a user request?

Data: BFCL v3 "multiple" (200 requests, each with 2-4 candidate functions and one correct one).
Each request gets its own candidates plus distractors from other requests, 20 tools in all,
shuffled. The model answers one `choice` question over the tool names and descriptions.

Usage: python3 tooleval.py build            -> tasks.json
       python3 tooleval.py run laya|laya-multilingual|openjev -> results.<model>.json
       python3 tooleval.py bm25             -> results.bm25.json
"""
import json, math, os, random, re, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
N_TOOLS = 20
SERVERS = {
    "laya": ("http://127.0.0.1:8000/v1/systemone", "local-laya-key", None),
    "laya-multilingual": ("http://127.0.0.1:8000/v1/systemone", "local-laya-key", "multilingual"),
    "openjev": ("http://127.0.0.1:3000/v1/systemone", "local-openjev-key", "openjev"),
}
INSTRUCTIONS = "Which tool should the assistant call to complete the user's request?"


def build():
    rows = [json.loads(l) for l in open(os.path.join(HERE, "multiple.jsonl"))]
    answers = {json.loads(l)["id"]: json.loads(l)["ground_truth"] for l in open(os.path.join(HERE, "answers.jsonl"))}
    pool = {}
    for r in rows:
        for f in r["function"]:
            pool.setdefault(f["name"], f["description"])
    rng = random.Random(7)
    tasks = []
    for r in rows:
        own = {f["name"]: f["description"] for f in r["function"]}
        correct = list(answers[r["id"]][0].keys())[0]
        others = [n for n in sorted(pool) if n not in own]
        tools = dict(own)
        for n in rng.sample(others, N_TOOLS - len(own)):
            tools[n] = pool[n]
        names = list(tools)
        rng.shuffle(names)
        tasks.append({"id": r["id"], "request": r["question"][0][0]["content"], "correct": correct,
                      "own": sorted(own), "tools": [{"name": n, "description": tools[n]} for n in names]})
    json.dump(tasks, open(os.path.join(HERE, "tasks.json"), "w"), indent=1)
    print(len(tasks), "tasks;", sum(len(t["own"]) for t in tasks) / len(tasks), "own candidates on average")


def ask(model, task):
    url, key, model_name = SERVERS[model]
    body = {"state": {"user_request": task["request"]},
            "questions": {"tool": {"type": "choice", "instructions": INSTRUCTIONS,
                                   "criteria": {t["name"]: t["description"] for t in task["tools"]}}}}
    if model_name:
        body["model"] = model_name
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json", "authorization": "Bearer " + key})
    start = time.time()
    with urllib.request.urlopen(req, timeout=600) as resp:
        out = json.load(resp)
    return out, time.time() - start


def run(model):
    tasks = json.load(open(os.path.join(HERE, "tasks.json")))
    path = os.path.join(HERE, f"results.{model}.json")
    results = json.load(open(path)) if os.path.exists(path) else {}
    for i, task in enumerate(tasks):
        if task["id"] in results:
            continue
        out, seconds = ask(model, task)
        answer = out["answers"]["tool"]
        results[task["id"]] = {"probabilities": answer["probabilities"], "choice": answer["choice"],
                               "seconds": round(seconds, 2), "routing": out.get("routing")}
        if i % 20 == 0:
            print(model, i, task["id"], answer["choice"], "correct:", task["correct"], f"{seconds:.1f}s", flush=True)
            json.dump(results, open(path, "w"))
    json.dump(results, open(path, "w"))


def tokens(text):
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z0-9]*", text.replace("_", " ").replace(".", " ")):
        out += [p.lower() for p in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", w) if len(p) > 2]
    return out


def bm25():
    tasks = json.load(open(os.path.join(HERE, "tasks.json")))
    results = {}
    for task in tasks:
        docs = {t["name"]: tokens(t["name"] + " " + t["description"]) for t in task["tools"]}
        avg = sum(len(d) for d in docs.values()) / len(docs)
        df = {}
        for d in docs.values():
            for w in set(d):
                df[w] = df.get(w, 0) + 1
        q = set(tokens(task["request"]))
        scores = {}
        for name, d in docs.items():
            s = 0.0
            for w in q:
                c = d.count(w)
                if c:
                    idf = math.log(1 + (len(docs) - df[w] + 0.5) / (df[w] + 0.5))
                    s += idf * c * 2.2 / (c + 1.2 * (0.25 + 0.75 * len(d) / avg))
            scores[name] = s
        results[task["id"]] = {"probabilities": scores}
    json.dump(results, open(os.path.join(HERE, "results.bm25.json"), "w"))


if __name__ == "__main__":
    {"build": build, "run": lambda: run(sys.argv[2]), "bm25": bm25}[sys.argv[1]]()
