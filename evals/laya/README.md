# Laya as a Jev replacement: evaluation

**Verdict: the connection works, but Laya is not good enough to replace Jev.**
It gives almost every file a high relevance score, so `jg` returns most of the repository
instead of a short, focused packet. jevgrep exists to lower coding-agent cost with small
packets, and Laya reverses that goal.

## What was tested

- jevgrep at commit `76474fd` (branch `laya-provider`), with the `laya` provider preset.
- Laya 0.3.21, checkpoint `laya-multilingual` (revision `55cf4c4`), `max_len` 8,192 tokens,
  served by `laya.serve` on an Apple GPU (MPS).
- The ten SWE-bench tasks of jevgrep's own benchmark cohort. Ground truth: the files that
  the official fix (`patch`) and its tests (`test_patch`) change.
- Queries: one per task, written from the issue text only and following
  `skills/jevgrep/SKILL.md` (see `results/queries.json`). The writer had no access to the
  fixes. The requests-1142 query is the real agent query recorded in
  `specs/done/jevgrep/assets/cpython-confirmation.md`.

No Jev API key was used. The comparisons with Jev use results that are already recorded in this
repository.

## Results

### Stage A: can Laya separate relevant files from other files?

Each file was scored with jevgrep's own file-navigation question (`navigationRequest`), once
alone and once in batches like the patched `jg` sends (at most 16 items, 24,000 bytes).
Positives: 27 gold and test files. Negatives: 87 `.py` files from the same directories
(siblings) and 100 random `.py` files.

| Files | Count | Score > 0.25 (jg admits) | Score > 0.5 | Median score |
|---|---|---|---|---|
| Gold and test files | 27 | 27 | 27 | 0.90 |
| Sibling files | 87 | 87 | 82 | 0.87 |
| Random files | 100 | 99 | 94 | 0.88 |

The pooled ROC AUC is 0.59 for gold against siblings and 0.61 for gold against random files,
where 0.5 is chance. Batching changes the numbers only a little (0.57 and 0.60).
No threshold can fix this, because the scores of gold and other files overlap almost
completely. Per-task results are in `results/stageA.log` and `results/stageA.json`.

### Stage B: full `jg` runs

| Task | Repo files | Files returned | Gold found | Tests found | Output | Time | Laya requests |
|---|---|---|---|---|---|---|---|
| psf__requests-1142 | 113 | 76 | 1/1 | 1/1 | 391,452 bytes | 12 min | 286 |
| pytest-dev__pytest-6197 | 449 | 410 | 1/1 | 2/2 | 3,759,305 bytes | 46 min | 1,746 |

Both runs ended with exit code 0 and no provider errors. On pytest, `jg` scored the release
notes one by one (`doc/en/announce/release-*.rst`) and admitted them. The planned runs on the
other eight tasks were stopped: the two smallest repositories already show the result, and
the larger ones would take hours each at this rate.

For requests-1142, jevgrep with Jev returned **6 files in 6,880 bytes** on the same query
(`specs/done/jevgrep/assets/cpython-confirmation.md`). Laya returned **76 files in
391,452 bytes**, which is 57 times more output. The gold file is in the output, but so is
two thirds of the repository.

A keyword baseline (BM25 over all `.py` files with the same query, `bm25.py`) puts the
first gold file in its top 3 for 9 of the 10 tasks, and in its top 7 for all 10. Laya adds
no ranking signal that this baseline lacks.

## Why

1. **Domain.** Laya is trained on support tickets, email and intent classification. On source
   code it answers "yes, relevant" for nearly everything. The smoke test on
   `test/reference/tree` shows the same pattern: a typography note scored 0.67 on the file
   question, and the real telemetry files scored 0.63 and 0.64.
2. **Roles carry no information.** Laya gives each file nearly the same probability for all
   five roles (implementation, caller, test, fixture, helper).
3. **Later stages are better but cannot help.** On the smoke test, the source-excerpt question
   separated the files clearly (0.22 against 0.8). But the file list comes from the navigation
   stage, so the excerpt stage cannot shorten it.

## Patch notes

The provider patch itself is sound, and it is useful for testing any Jev-compatible server:

- `providers.ts`: a `laya` preset (`JG_LAYA_URL` overrides `http://localhost:8000/v1`).
- `evaluator.ts`: sends `max_len`, uses preset concurrency (4) and timeout (120 s), and
  writes raw traffic to `JG_TRACE_FILE` when set.
- `retrieve.ts`: navigation batch limits come from the preset (16 items, 24,000 bytes),
  inside laya-serve's limits of 64 questions and 50,000 state characters.

## Reproduce

```sh
python -m pip install "laya[serve]"
LAYA_MODELS=multilingual LAYA_API_KEY=local-laya-key python -m laya.serve &
bun install --frozen-lockfile && bun run build
python3 evals/laya/fetch_tasks.py && evals/laya/clone.sh   # tasks.json, repos/
python3 evals/laya/bm25.py
bun evals/laya/stageA.ts
echo local-laya-key | XDG_CONFIG_HOME=evals/laya/results/jg-config \
  node apps/cli/dist/bin/index.js auth --provider laya --stdin
python3 evals/laya/stageB.py psf__requests-1142
```

`results/queries.json` must exist before `bm25.py`, `stageA.ts` and `stageB.py` run.
