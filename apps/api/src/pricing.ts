export const SST_RATE = 0.06;
export const BATCH_DISCOUNT = 0.5;

export interface ModelRow {
  id: string;
  name: string;
  provider: string;
  price_cents_per_million: number;
}

export interface LineItem {
  modelId: string;
  name: string;
  provider: string;
  tokensMillions: number;
  unitPriceCents: number; // price actually charged per 1M tokens (batch-adjusted)
  costCents: number;
}

export interface Totals {
  items: LineItem[];
  listCents: number;
  discountCents: number;
  subtotalCents: number;
  sstCents: number;
  totalCents: number;
}

/** All money is integer cents; each line is rounded to the cent before summing. */
export function calculate(
  usage: { model: ModelRow; tokensMillions: number }[],
  batch: boolean,
): Totals {
  const factor = batch ? 1 - BATCH_DISCOUNT : 1;
  let listCents = 0;
  let subtotalCents = 0;

  const items = usage.map(({ model, tokensMillions }): LineItem => {
    const unit = model.price_cents_per_million * factor;
    const costCents = Math.round(tokensMillions * unit);
    listCents += Math.round(tokensMillions * model.price_cents_per_million);
    subtotalCents += costCents;
    return {
      modelId: model.id,
      name: model.name,
      provider: model.provider,
      tokensMillions,
      unitPriceCents: unit,
      costCents,
    };
  });

  const sstCents = Math.round(subtotalCents * SST_RATE);
  return {
    items,
    listCents,
    discountCents: listCents - subtotalCents,
    subtotalCents,
    sstCents,
    totalCents: subtotalCents + sstCents,
  };
}
