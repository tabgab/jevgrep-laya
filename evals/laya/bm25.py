"""Lexical baseline: rank every .py file in a task repo by BM25 against the jg query.

Usage: python3 bm25.py  -> writes bm25.json {task_id: [path, ...] ranked best first}
"""
import json, math, os, re
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
EVAL = os.environ.get("LAYA_EVAL_DATA", os.path.join(HERE, "results"))
tasks = json.load(open(os.path.join(EVAL, "tasks.json")))
queries = json.load(open(os.path.join(EVAL, "queries.json")))
STOP = set("the a an of to and or in on for is are be with that this by as it not from at when while".split())


def tokens(text):
    out = []
    for word in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text):
        parts = [word] + re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+", word) + word.split("_")
        out += [p.lower() for p in parts if len(p) > 2 and p.lower() not in STOP]
    return out


result = {}
for task in tasks:
    root = os.path.join(EVAL, "repos", task["id"])
    docs = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        for name in filenames:
            if name.endswith(".py"):
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, root)
                with open(path, encoding="utf8", errors="replace") as f:
                    docs[rel] = Counter(tokens(rel + "\n" + f.read()))
    n = len(docs)
    avg = sum(sum(c.values()) for c in docs.values()) / n
    df = Counter(t for c in docs.values() for t in c)
    q = set(tokens(queries[task["id"]]))
    scores = {}
    for rel, c in docs.items():
        length = sum(c.values())
        s = 0.0
        for t in q:
            if t in c:
                idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
                s += idf * c[t] * 2.2 / (c[t] + 1.2 * (0.25 + 0.75 * length / avg))
        scores[rel] = s
    result[task["id"]] = sorted(scores, key=lambda rel: scores[rel], reverse=True)
    ranks = [result[task["id"]].index(g) + 1 for g in task["gold_files"] if g in scores]
    print(f"{task['id']:34} files={n:5} gold ranks={ranks}")
json.dump(result, open(os.path.join(EVAL, "bm25.json"), "w"))
