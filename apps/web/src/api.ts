import type { Model, Summary } from './types';

const BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, {
    ...init,
    headers: init?.body ? { 'Content-Type': 'application/json' } : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error((data as { error?: string }).error ?? `Request failed (${res.status})`);
  return data as T;
}

export const getModels = () =>
  request<{ models: Model[]; sstRate: number; batchDiscount: number }>('/api/models');

export const calculate = (batch: boolean, usage: { modelId: string; tokensMillions: number }[]) =>
  request<Summary>('/api/calculate', { method: 'POST', body: JSON.stringify({ batch, usage }) });
