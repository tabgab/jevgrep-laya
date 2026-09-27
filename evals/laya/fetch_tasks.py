import json, os, re, urllib.parse, urllib.request
EVAL = os.environ.get("LAYA_EVAL_DATA", os.path.join(os.path.dirname(os.path.abspath(__file__)), "results"))
IDS = ["psf__requests-1142", "matplotlib__matplotlib-26466", "django__django-15629",
       "scikit-learn__scikit-learn-13124", "astropy__astropy-13579", "sympy__sympy-16792",
       "sphinx-doc__sphinx-8638", "pytest-dev__pytest-6197", "pylint-dev__pylint-4604",
       "pydata__xarray-3305"]
tasks = []
for iid in IDS:
    where = urllib.parse.quote(f"\"instance_id\"='{iid}'")
    url = f"https://datasets-server.huggingface.co/filter?dataset=princeton-nlp/SWE-bench&config=default&split=test&where={where}&length=1"
    import time
    for attempt in range(6):
        try:
            row = json.load(urllib.request.urlopen(url))["rows"][0]["row"]; break
        except Exception as e:
            print("retry", iid, e); time.sleep(5 * (attempt + 1))
    else:
        raise SystemExit("failed " + iid)
    files = lambda p: sorted(set(re.findall(r"^diff --git a/(\S+)", p, re.M)))
    tasks.append({"id": iid, "repo": row["repo"], "base_commit": row["base_commit"],
                  "problem_statement": row["problem_statement"],
                  "gold_files": files(row["patch"]), "test_files": files(row["test_patch"])})
    print(iid, tasks[-1]["gold_files"], tasks[-1]["test_files"])
json.dump(tasks, open(os.path.join(EVAL, "tasks.json"), "w"), indent=1)
