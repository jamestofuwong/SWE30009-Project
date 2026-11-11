export interface Model {
  id: string;
  name: string;
  provider: string;
  description: string;
  priceCents: number; // price per 1M tokens, in integer cents (non-batch)
}

/** The 8 models offered by the gateway, in display order. */
export const MODELS: Model[] = [
  { id: 'claude-opus-5-5',   name: 'Claude Opus 5.5',   provider: 'Anthropic', description: 'Deep reasoning & agents', priceCents: 3000 },
  { id: 'claude-sonnet-5-5', name: 'Claude Sonnet 5.5', provider: 'Anthropic', description: 'Balanced all-rounder',     priceCents: 900 },
  { id: 'claude-haiku-5-5',  name: 'Claude Haiku 5.5',  provider: 'Anthropic', description: 'Fast & lightweight',       priceCents: 200 },
  { id: 'gpt-5',             name: 'GPT-5',             provider: 'OpenAI',    description: 'General flagship',         priceCents: 1125 },
  { id: 'gpt-5-mini',        name: 'GPT-5 mini',        provider: 'OpenAI',    description: 'Low-cost chat',            priceCents: 125 },
  { id: 'gemini-2-5-pro',    name: 'Gemini 2.5 Pro',    provider: 'Google',    description: 'Long-context analysis',    priceCents: 875 },
  { id: 'llama-4-maverick',  name: 'Llama 4 Maverick',  provider: 'Meta',      description: 'Open-weight workhorse',    priceCents: 80 },
  { id: 'mistral-large-3',   name: 'Mistral Large 3',   provider: 'Mistral',   description: 'Multilingual & code',      priceCents: 400 },
];
