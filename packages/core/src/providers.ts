export const providers = {
  vercel: {
    label: "Vercel AI Gateway",
    baseURL: "https://ai-gateway.vercel.sh/typesafe/v1",
    model: "typesafe-ai/jev",
  },
  typesafe: {
    label: "TypeSafe",
    baseURL: "https://api.typesafe.ai/v1",
    model: "jev-1.13.0",
  },
  openrouter: {
    label: "OpenRouter",
    baseURL: "https://openrouter.ai/api/v1",
    model: "jev-1.13",
  },
  opencode: {
    label: "OpenCode Zen",
    baseURL: "https://opencode.ai/zen/v1",
    model: "jev-1.13",
  },
  laya: {
    label: "Laya (self-hosted laya-serve)",
    baseURL: "http://localhost:8000/v1",
    // Laya picks a checkpoint by language for unknown names; source code would route to the
    // 512-token English checkpoint. The multilingual checkpoint reads up to 8,192 tokens.
    model: "multilingual",
    maxLen: 8192,
    // laya-serve rejects more than 64 questions and returns 503 above 16 concurrent requests.
    // Smaller navigation batches keep every item inside the model's token window.
    navigationBatch: { items: 16, bytes: 24_000 },
    concurrency: 4,
    timeoutMs: 120_000,
  },
  openjev: {
    label: "OpenJev (self-hosted helper)",
    baseURL: "http://localhost:3000/v1",
    model: "openjev",
    // Same batch limits as laya, so both self-hosted models see identical requests. OpenJev
    // reads 16,384 tokens, so no token budget is sent. The Mac (MLX) helper answers one
    // question at a time, so a 16-question batch can take minutes.
    navigationBatch: { items: 16, bytes: 24_000 },
    // Node's fetch waits at most 300 s for response headers; four questions stay well inside.
    questionsPerCall: 4,
    concurrency: 2,
    timeoutMs: 1_800_000,
  },
} as const;

export type ProviderId = keyof typeof providers;

// Self-hosted servers can run anywhere, so their endpoints alone may be overridden.
const endpointOverrides: Partial<Record<ProviderId, string>> = {
  laya: "JG_LAYA_URL",
  openjev: "JG_OPENJEV_URL",
};
export function providerBaseURL(provider: ProviderId): string {
  const variable = endpointOverrides[provider];
  const override = variable ? process.env[variable] : undefined;
  return override ? override.replace(/\/+$/, "") : providers[provider].baseURL;
}

export function isProviderId(value: unknown): value is ProviderId {
  return typeof value === "string" && Object.hasOwn(providers, value);
}
