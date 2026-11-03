const fmt = (min: number, max: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', minimumFractionDigits: min, maximumFractionDigits: max });
const two = fmt(2, 2);
const rate = fmt(2, 3);

export const money = (cents: number) => two.format(cents / 100);
export const moneyRate = (cents: number) => rate.format(cents / 100);
export const millions = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 3 });
