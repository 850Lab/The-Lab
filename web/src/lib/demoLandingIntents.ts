/** Values stored in demo_leads.meta.intent (API + Mission Control). */
export const DEMO_LANDING_INTENTS = [
  { value: "host_workshop", label: "Host a workshop" },
  { value: "use_in_class", label: "Use in my class or program" },
  { value: "try_myself", label: "Try for myself" },
  { value: "refer_someone", label: "Refer someone" },
] as const;

export type DemoLandingIntentValue = (typeof DEMO_LANDING_INTENTS)[number]["value"];

export function showOrgAudienceFields(intent: string): boolean {
  return intent === "host_workshop" || intent === "use_in_class";
}

export function showReferrerField(intent: string): boolean {
  return intent === "refer_someone";
}
