import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { calculate, SST_RATE, type ModelRow, type Totals } from './pricing';

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

/** Compute a summary for the given usage, store it, and return it. */
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

  const id = crypto.randomUUID();
  const createdAt = new Date().toISOString();
  await c.env.DB.batch([
    c.env.DB.prepare(
      `INSERT INTO calculations (id, created_at, batch, list_cents, discount_cents, subtotal_cents, sst_cents, total_cents)
       VALUES (?, ?, ?, ?, ?, ?, ?, ?)`,
    ).bind(id, createdAt, batch ? 1 : 0, totals.listCents, totals.discountCents, totals.subtotalCents, totals.sstCents, totals.totalCents),
    ...totals.items.map((it) =>
      c.env.DB.prepare(
        `INSERT INTO calculation_items (calculation_id, model_id, model_name, provider, tokens_millions, unit_price_cents, cost_cents)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
      ).bind(id, it.modelId, it.name, it.provider, it.tokensMillions, it.unitPriceCents, it.costCents),
    ),
  ]);

  return c.json(present(id, createdAt, batch, totals), 201);
});

/** Recent calculations (newest first). */
app.get('/api/calculations', async (c) => {
  const limit = Math.min(Math.max(parseInt(c.req.query('limit') ?? '10', 10) || 10, 1), 50);
  const { results } = await c.env.DB.prepare(
    `SELECT c.id, c.created_at AS createdAt, c.batch, c.total_cents AS totalCents,
            (SELECT COUNT(*) FROM calculation_items i WHERE i.calculation_id = c.id) AS itemCount
       FROM calculations c ORDER BY c.created_at DESC LIMIT ?`,
  )
    .bind(limit)
    .all<{ batch: number }>();
  return c.json({ calculations: results.map((r) => ({ ...r, batch: !!r.batch })) });
});

/** One stored calculation, in the same shape /api/calculate returns. */
app.get('/api/calculations/:id', async (c) => {
  const id = c.req.param('id');
  const calc = await c.env.DB.prepare('SELECT * FROM calculations WHERE id = ?').bind(id).first<Record<string, number | string>>();
  if (!calc) return c.json({ error: 'Not found.' }, 404);
  const { results } = await c.env.DB.prepare(
    `SELECT model_id AS modelId, model_name AS name, provider, tokens_millions AS tokensMillions,
            unit_price_cents AS unitPriceCents, cost_cents AS costCents
       FROM calculation_items WHERE calculation_id = ? ORDER BY id`,
  )
    .bind(id)
    .all();
  return c.json(
    present(id, calc.created_at as string, !!calc.batch, {
      items: results as unknown as Totals['items'],
      listCents: calc.list_cents as number,
      discountCents: calc.discount_cents as number,
      subtotalCents: calc.subtotal_cents as number,
      sstCents: calc.sst_cents as number,
      totalCents: calc.total_cents as number,
    }),
  );
});

app.notFound((c) => c.json({ error: 'Not found.' }, 404));
app.onError((err, c) => {
  console.error(err);
  return c.json({ error: 'Internal server error.' }, 500);
});

function present(id: string, createdAt: string, batch: boolean, t: Totals) {
  return { id, createdAt, batch, sstRate: SST_RATE, ...t };
}

export default app;
