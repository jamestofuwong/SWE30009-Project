export interface Model { id: string; name: string; provider: string; description: string; priceCents: number }
export interface LineItem { modelId: string; name: string; provider: string; tokensMillions: number; unitPriceCents: number; costCents: number }
export interface Summary {
  id: string; createdAt: string; batch: boolean; sstRate: number; items: LineItem[];
  listCents: number; discountCents: number; subtotalCents: number; sstCents: number; totalCents: number;
}
export interface HistoryEntry { id: string; createdAt: string; batch: boolean; totalCents: number; itemCount: number }
