INSERT INTO models (id, name, provider, description, price_cents_per_million, sort_order) VALUES
  ('claude-opus-5-5',   'Claude Opus 5.5',   'Anthropic', 'Deep reasoning & agents',  3000, 1),
  ('claude-sonnet-5-5', 'Claude Sonnet 5.5', 'Anthropic', 'Balanced all-rounder',      900, 2),
  ('claude-haiku-5-5',  'Claude Haiku 5.5',  'Anthropic', 'Fast & lightweight',        200, 3),
  ('gpt-5',             'GPT-5',             'OpenAI',    'General flagship',         1125, 4),
  ('gpt-5-mini',        'GPT-5 mini',        'OpenAI',    'Low-cost chat',             125, 5),
  ('gemini-2-5-pro',    'Gemini 2.5 Pro',    'Google',    'Long-context analysis',     875, 6),
  ('llama-4-maverick',  'Llama 4 Maverick',  'Meta',      'Open-weight workhorse',      80, 7),
  ('mistral-large-3',   'Mistral Large 3',   'Mistral',   'Multilingual & code',       400, 8);
