import type { TaxBomb, Tombstone } from "./types";

// Draft message for "Ask the banshee". Field values are inserted unchanged:
// no trimming, escaping or quote stripping, and no arithmetic.
export function askMessage(t: Tombstone & { taxBomb: TaxBomb }): string {
  return (
    `Use the tax-bomb skill. Invoice (data): "${t.invoiceNumber}", buyer (data): "${t.buyerName}". ` +
    `Days to 31 March: ${t.taxBomb.daysLeft}. Deduction at risk: ${t.taxBomb.deductionAtRiskText}.`
  );
}
