CREATE TABLE models (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  provider TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  price_cents_per_million INTEGER NOT NULL CHECK (price_cents_per_million >= 0),
  active INTEGER NOT NULL DEFAULT 1,
  sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE calculations (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
  batch INTEGER NOT NULL,
  list_cents INTEGER NOT NULL,
  discount_cents INTEGER NOT NULL,
  subtotal_cents INTEGER NOT NULL,
  sst_cents INTEGER NOT NULL,
  total_cents INTEGER NOT NULL
);
CREATE INDEX idx_calculations_created ON calculations (created_at DESC);

CREATE TABLE calculation_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  calculation_id TEXT NOT NULL REFERENCES calculations(id) ON DELETE CASCADE,
  model_id TEXT NOT NULL,
  model_name TEXT NOT NULL,
  provider TEXT NOT NULL,
  tokens_millions REAL NOT NULL,
  unit_price_cents REAL NOT NULL,
  cost_cents INTEGER NOT NULL
);
CREATE INDEX idx_items_calc ON calculation_items (calculation_id);
