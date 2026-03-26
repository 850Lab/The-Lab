export type LetterGroupData = {
  id: string;
  bureau: string;
  disputeCount: number;
  supportLine: string;
  previewSummary: string;
};

export const LETTER_GROUPS: LetterGroupData[] = [
  {
    id: "equifax",
    bureau: "Equifax",
    disputeCount: 3,
    supportLine: "Prepared and ready for delivery",
    previewSummary: "3 disputed items · bureau letter",
  },
  {
    id: "experian",
    bureau: "Experian",
    disputeCount: 2,
    supportLine: "Prepared and ready for delivery",
    previewSummary: "2 disputed items · bureau letter",
  },
  {
    id: "transunion",
    bureau: "TransUnion",
    disputeCount: 2,
    supportLine: "Prepared and ready for delivery",
    previewSummary: "2 disputed items · bureau letter",
  },
];

export function letterPreviewBody(bureau: string, disputeCount: number): string {
  const today = new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  }).format(new Date());

  return [
    `${bureau}`,
    "Consumer Dispute Department",
    "",
    `Date: ${today}`,
    "",
    "Re: Formal dispute of inaccurate credit report information",
    "",
    `Dear ${bureau} Team,`,
    "",
    `I am writing to dispute ${disputeCount} item${disputeCount === 1 ? "" : "s"} appearing on my credit file. Under the Fair Credit Reporting Act (FCRA), I request that you conduct a reasonable investigation, contact the furnisher(s) as appropriate, and correct or delete any information that cannot be verified as accurate.`,
    "",
    "The challenged entries have been documented and enclosed per your dispute procedures. Please complete your review promptly and provide written confirmation of the outcome, including an updated copy of my credit report if changes are made.",
    "",
    "Thank you for your attention to this matter.",
    "",
    "Sincerely,",
    "",
    "[Account holder name]",
    "[Address]",
    "[City, State ZIP]",
  ].join("\n");
}

export function combinedLettersDownloadText(): string {
  const header =
    "850 Lab — Dispute letter package (preview)\r\n" +
    "This document is a consolidated preview for your records.\r\n" +
    "—".repeat(48) +
    "\r\n\r\n";

  return (
    header +
    LETTER_GROUPS.map((g) => {
      const body = letterPreviewBody(g.bureau, g.disputeCount);
      return `${"═".repeat(40)}\r\n${g.bureau.toUpperCase()}\r\n${"═".repeat(40)}\r\n\r\n${body}\r\n\r\n`;
    }).join("")
  );
}
