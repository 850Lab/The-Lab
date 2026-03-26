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
      "We’ll prepare a dispute directed to the company furnishing the account information.",
    reason:
      "This is often the right next move after a bureau verifies an item.",
    recommended: true,
  },
  {
    id: "reverify",
    title: "Ask them to verify it again",
    support:
      "We’ll request method of verification for the item they reviewed.",
    reason:
      "Useful when something about their review doesn’t line up with what you know.",
  },
  {
    id: "cfpb",
    title: "File a formal complaint",
    support:
      "We’ll help you prepare a CFPB complaint if stronger escalation is needed.",
    reason: "Best when you’ve tried the standard paths and still need traction.",
  },
];

export function getEscalationOption(
  id: EscalationOptionId,
): EscalationOption {
  const o = ESCALATION_OPTIONS.find((x) => x.id === id);
  if (!o) return ESCALATION_OPTIONS[0];
  return o;
}
