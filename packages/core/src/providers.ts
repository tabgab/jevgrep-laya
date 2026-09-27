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
} as const;

export type ProviderId = keyof typeof providers;

// A self-hosted Laya server can run anywhere, so its endpoint alone may be overridden.
export function providerBaseURL(provider: ProviderId): string {
  if (provider === "laya" && process.env.JG_LAYA_URL) return process.env.JG_LAYA_URL.replace(/\/+$/, "");
  return providers[provider].baseURL;
}

export function isProviderId(value: unknown): value is ProviderId {
  return typeof value === "string" && Object.hasOwn(providers, value);
}
