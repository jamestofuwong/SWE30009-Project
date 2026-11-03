# AI Gateway – Usage Calculator

[![Test Ubuntu](https://github.com/jamestofuwong/SWE30009-Project/actions/workflows/test-ubuntu.yml/badge.svg)](https://github.com/jamestofuwong/SWE30009-Project/actions/workflows/test-ubuntu.yml)
[![Test Windows](https://github.com/jamestofuwong/SWE30009-Project/actions/workflows/test-windows.yml/badge.svg)](https://github.com/jamestofuwong/SWE30009-Project/actions/workflows/test-windows.yml)

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
| POST | `/api/calculate` | `{ batch: boolean, usage: [{ modelId, tokensMillions }] }` → itemised summary (batch = 50% off, +6% SST) |

All money is integer cents; each line is rounded to the cent, then SST is applied to the subtotal.

## Local development
```bash
npm install
npm run dev   # applies local D1 migrations, then starts the worker (:8787) and Vite (:5173) together
```
Individual pieces: `npm run db:migrate:local`, `npm run dev:api`, `npm run dev:web`.

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

## Tests
Selenium functional tests (10 cases in `tests/test_cases.csv`). With the app running (`npm run dev`):
```bash
npm run test:selenium -- --headless
```
The **Test Ubuntu** and **Test Windows** GitHub Actions workflows run them on `ubuntu-latest` and `windows-latest`; trigger them manually from the Actions tab.

Each run writes `tests/report/results.json` and screenshots. `python tests/generate_report.py` turns them into `tests/report/test-report.pdf` (summary, pass/fail charts, failures with reasons, execution times, expected vs actual, environment, screenshots). In CI, the report is uploaded as the `test-report-ubuntu` / `test-report-windows` build artifact on every run, including failed ones.
