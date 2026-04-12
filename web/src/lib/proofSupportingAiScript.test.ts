import { describe, expect, it } from "vitest";
import { safeCustomerProofSupportScript } from "./proofSupportingAiScript";

describe("safeCustomerProofSupportScript", () => {
  it("returns null for wrong intent or invalid shapes", () => {
    expect(safeCustomerProofSupportScript(null)).toBeNull();
    expect(
      safeCustomerProofSupportScript({
        scriptIntent: "creditor_call_script",
        title: "T",
        intro: null,
        lines: [{ speaker: "user", "text": "x" }],
        talkingPoints: ["a"],
        tone: "clear",
      }),
    ).toBeNull();
    expect(
      safeCustomerProofSupportScript({
        scriptIntent: "proof_submission_support",
        title: "",
        intro: null,
        lines: [],
        talkingPoints: [],
        tone: "clear",
      }),
    ).toBeNull();
  });

  it("accepts proof_submission_support with lines and talking points", () => {
    const x = safeCustomerProofSupportScript({
      scriptIntent: "proof_submission_support",
      title: "Title",
      intro: "Intro",
      lines: [{ speaker: "user", text: "Line one" }],
      talkingPoints: ["Tip"],
      tone: "supportive",
    });
    expect(x).not.toBeNull();
    expect(x!.title).toBe("Title");
    expect(x!.lines).toHaveLength(1);
    expect(x!.talkingPoints).toHaveLength(1);
  });
});
