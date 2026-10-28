export type SelectableSeat = {
  key: string;
  price: string | null;
  isOperational: boolean;
};

/** Toggle one seat locally; only operational seats with a configured price can be selected. */
export function toggleSeatSelection(
  selectedKeys: readonly string[],
  seat: SelectableSeat,
): string[] {
  if (!seat.isOperational || seat.price === null) return [...selectedKeys];
  if (selectedKeys.includes(seat.key)) {
    return selectedKeys.filter((selectedKey) => selectedKey !== seat.key);
  }
  return [...selectedKeys, seat.key];
}

/** Sum decimal-string prices exactly in cents, ignoring keys absent from the map. */
export function sumSelectedSeatPricesCents(
  seats: readonly SelectableSeat[],
  selectedKeys: readonly string[],
): bigint {
  const selected = new Set(selectedKeys);
  return seats.reduce((totalCents, seat) => {
    if (!selected.has(seat.key) || !seat.isOperational || seat.price === null) {
      return totalCents;
    }
    const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(seat.price);
    if (!match) return totalCents;
    const pesos = BigInt(match[1]);
    const centavos = BigInt((match[2] ?? "").padEnd(2, "0") || "0");
    return totalCents + pesos * BigInt(100) + centavos;
  }, BigInt(0));
}

export function formatCentsAsDecimal(amountCents: bigint): string {
  const pesos = amountCents / BigInt(100);
  const centavos = (amountCents % BigInt(100)).toString().padStart(2, "0");
  return `${pesos}.${centavos}`;
}
