import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { calculate, SST_RATE, type ModelRow } from './pricing';

type Bindings = { DB: D1Database; ALLOWED_ORIGIN?: string };

const MAX_MILLIONS = 1_000_000; // sanity cap per model
const MAX_ITEMS = 50;

const app = new Hono<{ Bindings: Bindings }>();

app.use('/api/*', (c, next) =>
  cors({
    origin: c.env.ALLOWED_ORIGIN && c.env.ALLOWED_ORIGIN !== '*' ? c.env.ALLOWED_ORIGIN : '*',
    allowMethods: ['GET', 'POST', 'OPTIONS'],
    allowHeaders: ['Content-Type'],
    maxAge: 86400,
  })(c, next),
);

app.get('/api/health', (c) => c.json({ ok: true }));

/** List active models with their (non-batch) price per 1M tokens. */
app.get('/api/models', async (c) => {
  const { results } = await c.env.DB.prepare(
    `SELECT id, name, provider, description, price_cents_per_million AS priceCents
       FROM models WHERE active = 1 ORDER BY sort_order, name`,
  ).all();
  return c.json({ models: results, sstRate: SST_RATE, batchDiscount: 0.5 });
});

/** Compute a summary for the given usage. */
app.post('/api/calculate', async (c) => {
  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'Request body must be valid JSON.' }, 400);
  }

  const { batch, usage } = (body ?? {}) as { batch?: unknown; usage?: unknown };
  if (typeof batch !== 'boolean') return c.json({ error: '"batch" must be a boolean.' }, 400);
  if (!Array.isArray(usage) || usage.length === 0 || usage.length > MAX_ITEMS) {
    return c.json({ error: '"usage" must be a non-empty array.' }, 400);
  }

  // Validate and merge duplicates.
  const wanted = new Map<string, number>();
  for (const entry of usage) {
    const { modelId, tokensMillions } = (entry ?? {}) as { modelId?: unknown; tokensMillions?: unknown };
    if (typeof modelId !== 'string' || !modelId) return c.json({ error: 'Each usage entry needs a "modelId".' }, 400);
    if (typeof tokensMillions !== 'number' || !Number.isFinite(tokensMillions) || tokensMillions < 0 || tokensMillions > MAX_MILLIONS) {
      return c.json({ error: `Invalid usage for ${modelId}.` }, 400);
    }
    if (tokensMillions > 0) wanted.set(modelId, (wanted.get(modelId) ?? 0) + tokensMillions);
  }
  if (wanted.size === 0) return c.json({ error: 'Enter usage for at least one model.' }, 400);

  const ids = [...wanted.keys()];
  const { results } = await c.env.DB.prepare(
    `SELECT id, name, provider, price_cents_per_million FROM models
      WHERE active = 1 AND id IN (${ids.map(() => '?').join(',')}) ORDER BY sort_order`,
  )
    .bind(...ids)
    .all<ModelRow>();

  if (results.length !== ids.length) {
    const known = new Set(results.map((m) => m.id));
    return c.json({ error: `Unknown model: ${ids.find((id) => !known.has(id))}` }, 400);
  }

  const totals = calculate(
    results.map((model) => ({ model, tokensMillions: wanted.get(model.id)! })),
    batch,
  );

  return c.json({ batch, sstRate: SST_RATE, ...totals });
});

app.notFound((c) => c.json({ error: 'Not found.' }, 404));
app.onError((err, c) => {
  console.error(err);
  return c.json({ error: 'Internal server error.' }, 500);
});

export default app;
