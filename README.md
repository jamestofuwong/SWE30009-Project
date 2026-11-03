# AI Gateway – Usage Calculator

Vue 3 (Cloudflare Pages) → Hono API (Cloudflare Worker) → Cloudflare D1.

```
apps/api   Hono worker + D1 migrations (schema + 8 seeded models)
apps/web   Vue 3 + Vite frontend (dark "developer" design)
markups/   Original static design explorations
```

## API
| Method | Path | Purpose |
|---|---|---|
| GET  | `/api/models` | Model list, price per 1M tokens (cents), SST rate |
| POST | `/api/calculate` | `{ batch: boolean, usage: [{ modelId, tokensMillions }] }` → itemised summary (batch = 50% off, +6% SST); stored in D1 |
| GET  | `/api/calculations?limit=10` | Recent calculations |
| GET  | `/api/calculations/:id` | One stored calculation |

All money is integer cents; each line is rounded to the cent, then SST is applied to the subtotal.

## Local development
```bash
npm install
npm run db:migrate:local   # creates the local D1 db and seeds models
npm run dev:api            # worker on http://localhost:8787
npm run dev:web            # Vite on http://localhost:5173 (proxies /api to the worker)
```

## Deploy
1. **Database + API**
   ```bash
   cd apps/api
   npx wrangler login
   npx wrangler d1 create ai-gateway          # copy the database_id into wrangler.toml
   npm run db:migrate:remote
   # set ALLOWED_ORIGIN in wrangler.toml to your Pages URL, then:
   npm run deploy                              # prints https://ai-gateway-api.<sub>.workers.dev
   ```
2. **Frontend** (Pages)
   ```bash
   cd apps/web
   VITE_API_URL=https://ai-gateway-api.<sub>.workers.dev npm run deploy
   ```
   Or connect the repo in the Pages dashboard: root `apps/web`, build command `npm run build`,
   output `dist`, environment variable `VITE_API_URL`.
