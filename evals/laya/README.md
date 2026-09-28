# Self-hosted Jev replacements: Laya and OpenJev

**Verdict**

- **Laya: not good enough.** It gives almost every file a high relevance score, so `jg`
  returns most of the repository instead of a short, focused packet.
- **OpenJev: good enough in quality, too slow on a Mac.** It separates relevant files from other
  files almost as a trained judge should. On the one full task tested, its packet was the same
  size and shape as a recorded Jev packet. On an M3 Max the run took 3 hours 12 minutes, so
  practical use needs a GPU server (see [Speed](#speed)).

Both models plug into jevgrep through the same `/v1/systemone` protocol as Jev. No Jev API key
was used. The comparisons with Jev use results that are already recorded in this repository.

## What was tested

- jevgrep branch `laya-provider`, with the `laya` and `openjev` provider presets.
- **Laya** 0.3.21, checkpoint `laya-multilingual` (revision `55cf4c4`), `max_len` 8,192 tokens,
  served by `laya.serve` on an Apple GPU (MPS). This is the only Laya checkpoint tested. It is
  the only one that reads 8,192 tokens. The `laya` (512) and `laya-typed-decisions` (1,024)
  checkpoints would cut jevgrep's states even shorter.
- **OpenJev**, build `openjev/openjev-MLX-4bit` (4-bit, text only), served by the model's own
  helper (`helper/shim_mlx.py` over `helper/shim.py`, sha256 `81a22f1b…`) with the calibration
  settings from the model card, on an Apple M3 Max with 36 GB. The model card reports this
  build at 84.3% against 84.9% for the 16-bit model on 4,692 held-out questions. OpenJev reads
  16,384 tokens, so jevgrep's requests reach it without truncation.
- The ten SWE-bench tasks of jevgrep's own benchmark cohort. Ground truth: the files that
  the official fix (`patch`) and its tests (`test_patch`) change.
- Queries: one per task, written from the issue text only and following
  `skills/jevgrep/SKILL.md` (see `results/queries.json`). The writer had no access to the
  fixes. The requests-1142 query is the real agent query recorded in
  `specs/done/jevgrep/assets/cpython-confirmation.md`.

OpenJev weights are licensed CC BY-NC 4.0: free for research and other non-commercial use.
Commercial use needs permission from the OpenJev authors.

## Stage A: can the model separate relevant files from other files?

Each file was scored with jevgrep's own file-navigation question (`navigationRequest`), one
file per request. Positives: 27 gold and test files. Negatives: 87 `.py` files from the same
directories (siblings) and 100 random `.py` files. Both models scored exactly the same 214
files with the same queries (same seed and file listing), so the two tables are paired.

| Files | Count | Laya: score > 0.25 (jg admits) | Laya: median | OpenJev: score > 0.25 | OpenJev: median |
|---|---|---|---|---|---|
| Gold and test files | 27 | 27 | 0.90 | 23 | 0.81 |
| Sibling files | 87 | 87 | 0.87 | 11 | 0.02 |
| Random files | 100 | 99 | 0.88 | 2 | 0.01 |

| Pooled ROC AUC (0.5 is chance) | Laya | OpenJev |
|---|---|---|
| Gold against siblings | 0.59 | **0.92** |
| Gold against random files | 0.61 | **0.97** |

Laya's scores for gold and other files overlap almost completely, so no threshold can fix
it. Laya was also scored in batches like the patched `jg` sends (at most 16 items, 24,000
bytes); batching changed its AUC only a little (0.57 and 0.60). OpenJev was scored one file
per request only, to halve the run time.

OpenJev missed 4 gold files at the 0.25 threshold: `django/db/backends/oracle/features.py`
(0.09), `django/db/backends/sqlite3/schema.py` (0.12), `testing/test_skipping.py` in pytest
(0.02) and `pylint/constants.py` (0.01). Per-task results are in `results/stageA.log`,
`results/stageA.openjev.log` and the matching `.json` files.

## Stage B: full `jg` runs

| Model | Task | Repo files | Files returned | Gold found | Tests found | Output | Time | Calls |
|---|---|---|---|---|---|---|---|---|
| Laya | requests-1142 | 113 | 76 | 1/1 | 1/1 | 391,452 bytes | 12 min | 286 |
| Laya | pytest-6197 | 449 | 410 | 1/1 | 2/2 | 3,759,305 bytes | 46 min | 1,746 |
| OpenJev | requests-1142 | 113 | **5** | 1/1 | 1/1 | **9,413 bytes** | 3 h 12 min | 135 |
| Jev (recorded run) | requests-1142 | 113 | 6 | 1/1 | – | 6,880 bytes | – | – |

All runs ended with exit code 0 and no provider errors, and none reported incomplete
discovery. The Jev row comes from `specs/done/jevgrep/assets/cpython-confirmation.md`. That run
used an earlier jevgrep build and is not a paired live run.

**Laya** returned two thirds of the requests repository and 91% of the pytest repository. On
pytest, `jg` scored the release notes one by one (`doc/en/announce/release-*.rst`) and admitted
them.

**OpenJev** returned `requests/models.py`, `sessions.py`, `adapters.py`, `utils.py` and
`test_requests.py`. Its source excerpts include `models.py` lines 318-432, which hold
`prepare_body` and `prepare_content_length`, the code that the official fix changes. The
recorded Jev packet also centred on `models.py` source blocks, and it added `api.py`. Neither
packet includes an actual regression-test method.

Only requests-1142 was run with OpenJev. At the Mac's speed, each larger repository would take
many hours.

A keyword baseline (BM25 over all `.py` files with the same query, `bm25.py`) puts the first
gold file in its top 3 for 9 of the 10 tasks, and in its top 7 for all 10. Laya adds no ranking
signal that this baseline lacks. OpenJev does more than rank: it decides which files and
excerpts to leave out, which BM25 cannot do.

## Speed

The OpenJev Mac helper runs one forward pass per question, one question at a time, with no
prefix caching. It processed about 115 to 150 prompt tokens per second, or 25 to 40 s for one
file question. The model card reports 227 ms for a 1,100-token prompt on one H100 with vLLM and
prefix caching. Wall time on the Mac therefore says nothing about a served deployment. Do not
compare the Laya and OpenJev times as evidence about the models: the hardware paths and the
question counts differ.

## Why Laya fails

1. **Domain.** Laya is trained on support tickets, email and intent classification. On source
   code it answers "yes, relevant" for nearly everything. The smoke test on
   `test/reference/tree` shows the same pattern: a typography note scored 0.67 on the file
   question, and the real telemetry files scored 0.63 and 0.64.
2. **Roles carry no information.** Laya gives each file nearly the same probability for all
   five roles (implementation, caller, test, fixture, helper).
3. **Later stages are better but cannot help.** On the smoke test, the source-excerpt question
   separated the files clearly (0.22 against 0.8). But the file list comes from the navigation
   stage, so the excerpt stage cannot shorten it.
4. **Ruled out: instruction truncation.** Laya fits each question's text into `head_max_len`
   (256 tokens on this checkpoint). jevgrep's longest instruction is 105 tokens (measured with
   Laya's tokenizer over all 1,328 questions of the requests-1142 run), so no instruction is cut.

## Patch notes

- `providers.ts`: a `laya` preset (`JG_LAYA_URL` overrides `http://localhost:8000/v1`) and an
  `openjev` preset (`JG_OPENJEV_URL` overrides `http://localhost:3000/v1`). Both use navigation
  batches of at most 16 items and 24,000 bytes, inside laya-serve's limits of 64 questions and
  50,000 state characters.
- `evaluator.ts`:
  - Sends `max_len` for Laya.
  - Uses preset concurrency and timeout: Laya 4 and 120 s, OpenJev 1 and 30 min.
  - Splits OpenJev requests into calls of at most 4 questions. The Mac helper sends response
    headers only after it answers every question, and Node's `fetch` waits at most 300 s for
    them. OpenJev scores each question in its own forward pass, so splitting does not change
    the answers.
  - Writes raw traffic to `JG_TRACE_FILE` when set.
- `retrieve.ts`: navigation batch limits come from the preset (default unchanged: 128 items,
  38,000 bytes).

## Reproduce

Common steps:

```sh
bun install --frozen-lockfile && bun run build
python3 evals/laya/fetch_tasks.py && evals/laya/clone.sh   # tasks.json, repos/
python3 evals/laya/bm25.py
```

`results/queries.json` must exist before `bm25.py`, `stageA.ts` and `stageB.py` run.

Laya:

```sh
python -m pip install "laya[serve]"
LAYA_MODELS=multilingual LAYA_API_KEY=local-laya-key python -m laya.serve &
bun evals/laya/stageA.ts
echo local-laya-key | XDG_CONFIG_HOME=evals/laya/results/jg-config \
  node apps/cli/dist/bin/index.js auth --provider laya --stdin
python3 evals/laya/stageB.py psf__requests-1142
```

OpenJev on Apple silicon (`helper/` comes from the `openjev/openjev` repository):

```sh
python -m pip install mlx-lm transformers "openai==3.16.2" "httpx==0.28.1"
hf download openjev/openjev-MLX-4bit --local-dir models/openjev-MLX-4bit
M=models/openjev-MLX-4bit
READOUT_T=0.85 READOUT_NOUL_T=1.829074 READOUT_NOUL_BIAS=0 READOUT_TARGETED=1 \
READOUT_INSTR_STYLE=pyrepr SHIM_STAGGER=1 TOKENIZER=$M SHIM_MODEL=$M SHIM_TOKEN=local-openjev-key \
  python helper/shim_mlx.py --helper helper/shim.py --model $M --port 3000 &
EVAL_URL=http://127.0.0.1:3000/v1/systemone EVAL_MODEL=openjev EVAL_KEY=local-openjev-key \
  EVAL_MAX_LEN= EVAL_TAG=openjev EVAL_MODES=single bun evals/laya/stageA.ts
echo local-openjev-key | XDG_CONFIG_HOME=evals/laya/results/jg-config.openjev \
  node apps/cli/dist/bin/index.js auth --provider openjev --stdin
EVAL_TAG=openjev EVAL_TIMEOUT=28800 python3 evals/laya/stageB.py psf__requests-1142
```
