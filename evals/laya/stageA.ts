// Stage A: does Laya separate gold files from non-gold files on jevgrep's file question?
// Run: bun evals/laya/stageA.ts
import { navigationRequest, type NavigationItem } from "../../packages/core/src/requests";
import { readFileSync, writeFileSync, readdirSync, statSync, existsSync } from "node:fs";
import { join, dirname, extname } from "node:path";

const EVAL = process.env.LAYA_EVAL_DATA ?? join(import.meta.dir, "results");
// The endpoint defaults to laya-serve. Set EVAL_URL, EVAL_MODEL, EVAL_KEY and EVAL_MAX_LEN
// ("" sends none) for another Jev-compatible server, and EVAL_TAG to name the output file.
const URL = process.env.EVAL_URL ?? "http://127.0.0.1:8000/v1/systemone";
const MODEL = process.env.EVAL_MODEL ?? "multilingual";
const KEY = process.env.EVAL_KEY ?? "local-laya-key";
const MAX_LEN = process.env.EVAL_MAX_LEN ?? "8192";
const TAG = process.env.EVAL_TAG ? `.${process.env.EVAL_TAG}` : "";
// EVAL_MODES=single skips the batched pass, which doubles the run time on slow servers.
const MODES = (process.env.EVAL_MODES ?? "single,batched").split(",") as Array<"single" | "batched">;
const tasks = JSON.parse(readFileSync(join(EVAL, "tasks.json"), "utf8"));
const queries: Record<string, string> = JSON.parse(readFileSync(join(EVAL, "queries.json"), "utf8"));

let seed = 12345;
const rand = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
const shuffle = <T>(a: T[]) => a.map((x) => [rand(), x] as const).sort((p, q) => p[0] - q[0]).map((p) => p[1]);

function pyFiles(root: string, dir = ""): string[] {
  const out: string[] = [];
  for (const name of readdirSync(join(root, dir))) {
    if (name.startsWith(".")) continue;
    const rel = dir ? `${dir}/${name}` : name;
    const st = statSync(join(root, rel));
    if (st.isDirectory()) out.push(...pyFiles(root, rel));
    else if (name.endsWith(".py") && st.size > 200) out.push(rel);
  }
  return out;
}

function item(root: string, path: string): NavigationItem {
  const bytes = readFileSync(join(root, path));
  const text = new TextDecoder().decode(bytes.subarray(0, 16384));
  return {
    path,
    kind: "file",
    filePreview: {
      sizeBytes: bytes.length,
      extension: extname(path),
      text,
      previewBytes: Math.min(bytes.length, 16384),
      truncated: bytes.length > 16384,
      range: "opening bytes",
    },
  };
}

async function score(query: string, items: NavigationItem[]): Promise<number[]> {
  const request = navigationRequest(query, items);
  const questions = Object.fromEntries(
    Object.entries(request.questions).map(([k, q]) => [k, { ...q, type: "noul" }]),
  );
  const response = await fetch(URL, {
    method: "POST",
    headers: { "content-type": "application/json", authorization: `Bearer ${KEY}` },
    body: JSON.stringify({
      model: MODEL,
      ...(MAX_LEN ? { max_len: Number(MAX_LEN) } : {}),
      state: request.state,
      questions,
    }),
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  const body = (await response.json()) as { answers: Record<string, { noul: number }> };
  return items.map((_, i) => body.answers[`q${i}`]!.noul);
}

function auc(pos: number[], neg: number[]) {
  let s = 0;
  for (const p of pos) for (const n of neg) s += p > n ? 1 : p === n ? 0.5 : 0;
  return s / (pos.length * neg.length);
}

const rows: any[] = [];
for (const task of tasks) {
  const root = join(EVAL, "repos", task.id);
  const query = queries[task.id]!;
  const positives: string[] = [...task.gold_files, ...task.test_files].filter((p) => existsSync(join(root, p)));
  const all = pyFiles(root).filter((p) => !positives.includes(p));
  const dirs = new Set(positives.map(dirname));
  const siblings = shuffle(all.filter((p) => dirs.has(dirname(p)))).slice(0, 10);
  const random = shuffle(all.filter((p) => !siblings.includes(p))).slice(0, 10);
  const labelled = [
    ...positives.map((p) => ({ path: p, label: "gold" })),
    ...siblings.map((p) => ({ path: p, label: "sibling" })),
    ...random.map((p) => ({ path: p, label: "random" })),
  ];
  const single: Record<string, number> = {};
  if (MODES.includes("single"))
    for (const x of labelled) single[x.path] = (await score(query, [item(root, x.path)]))[0]!;
  const batched: Record<string, number> = {};
  const order = shuffle(labelled);
  // Group exactly as the patched jg does: at most 16 items and 24 000 request bytes.
  const groups: typeof order[] = [];
  let group: typeof order = [];
  for (const x of order) {
    const next = [...group, x];
    const size = Buffer.byteLength(JSON.stringify(navigationRequest(query, next.map((y) => item(root, y.path)))));
    if (group.length && (group.length >= 16 || size > 24_000)) {
      groups.push(group);
      group = [];
    }
    group.push(x);
  }
  if (group.length) groups.push(group);
  if (MODES.includes("batched")) for (const g of groups) {
    const s = await score(query, g.map((x) => item(root, x.path)));
    g.forEach((x, j) => (batched[x.path] = s[j]!));
  }
  for (const x of labelled) rows.push({ task: task.id, ...x, single: single[x.path], batched: batched[x.path] });
  const pick = (label: string, mode: "single" | "batched") =>
    labelled.filter((x) => x.label === label).map((x) => (mode === "single" ? single : batched)[x.path]!);
  for (const mode of MODES) {
    const g = pick("gold", mode), s = pick("sibling", mode), r = pick("random", mode);
    console.log(
      `${task.id.padEnd(34)} ${mode.padEnd(7)} AUC gold-vs-sibling=${auc(g, s).toFixed(2)} gold-vs-random=${auc(g, r).toFixed(2)}` +
        `  pass>0.25: gold ${g.filter((v) => v > 0.25).length}/${g.length} sib ${s.filter((v) => v > 0.25).length}/${s.length} rnd ${r.filter((v) => v > 0.25).length}/${r.length}` +
        `  mean g/s/r ${[g, s, r].map((a) => (a.reduce((p, q) => p + q, 0) / a.length).toFixed(2)).join("/")}`,
    );
  }
}
writeFileSync(join(EVAL, `stageA${TAG}.json`), JSON.stringify(rows, null, 1));
for (const mode of MODES) {
  const v = (label: string) => rows.filter((r) => r.label === label).map((r) => r[mode] as number);
  console.log(`POOLED ${mode}: AUC gold-vs-sibling=${auc(v("gold"), v("sibling")).toFixed(3)} gold-vs-random=${auc(v("gold"), v("random")).toFixed(3)}`);
}
