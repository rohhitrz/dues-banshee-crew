// Shapes of the Dues Banshee crew summary. Only the fields the page reads are typed.
// Every money, date and legal value is API text; nothing here is computed.

export interface Money {
  text: string;
}

// Values from the web app's engine: "armed" | "exploded" | "defused". Only "armed" shows the box.
export interface TaxBomb {
  status: string;
  daysLeft: number;
  deductionAtRiskText: string;
}

export interface Tombstone {
  id: string;
  buyerName: string; // untrusted
  invoiceNumber: string; // untrusted
  stateText: string;
  principal: Money;
  dueDateText: string | null;
  daysOverdue: number;
  interest: Money | null;
  taxBomb: TaxBomb | null;
  nextLabel: string;
}

export interface Totals {
  outstanding: Money;
  interestAccrued: Money | null;
  deductionsAtRisk: Money | null;
  explodedCount: number;
  paidCount: number;
}

export interface CrewSummary {
  supplierName: string; // untrusted
  today: string;
  disclaimer: string;
  totals: Totals;
  tombstones: Tombstone[];
}
