export type EscalationOptionId = "furnisher" | "reverify" | "cfpb";

export type EscalationOption = {
  id: EscalationOptionId;
  title: string;
  support: string;
  reason: string;
  recommended?: boolean;
};

export const DEFAULT_ESCALATION_ID: EscalationOptionId = "furnisher";

export const ESCALATION_OPTIONS: EscalationOption[] = [
  {
    id: "furnisher",
    title: "Contact the company reporting this",
    support:
      "We’ll prepare a dispute aimed at the company furnishing the account — a common follow-up after bureau mail.",
    reason:
      "Often the clearest path when a bureau has already replied and you need the furnisher in the loop.",
    recommended: true,
  },
  {
    id: "reverify",
    title: "Ask them to verify it again",
    support:
      "We’ll request method-of-verification detail for the item they already reviewed.",
    reason:
      "Fits when something in their review doesn’t line up with your records or feels incomplete.",
  },
  {
    id: "cfpb",
    title: "File a formal complaint",
    support:
      "We’ll help you prepare a CFPB complaint when you need a stronger, documented channel.",
    reason: "Usually considered later — after you’ve given ordinary follow-up a fair shot.",
  },
];

export function getEscalationOption(
  id: EscalationOptionId,
): EscalationOption {
  const o = ESCALATION_OPTIONS.find((x) => x.id === id);
  if (!o) return ESCALATION_OPTIONS[0];
  return o;
}
