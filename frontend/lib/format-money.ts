const integerFormatter = new Intl.NumberFormat("es-AR", {
  maximumFractionDigits: 0,
});

/** Format a decimal string exactly, without converting monetary values to float. */
export function formatArsAmount(amount: string): string {
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(amount);
  if (!match) {
    throw new TypeError("El importe debe ser un decimal válido.");
  }

  const [, sign, integerPart, rawFractionalPart = ""] = match;
  const significantFractionalPart = rawFractionalPart.replace(/0+$/, "");
  const fractionalPart = significantFractionalPart
    ? significantFractionalPart.padEnd(2, "0")
    : "";
  const formattedInteger = integerFormatter.format(BigInt(integerPart));
  const formattedAmount = fractionalPart
    ? `${formattedInteger},${fractionalPart}`
    : formattedInteger;

  return `${sign ? "-" : ""}$ ${formattedAmount}`;
}
