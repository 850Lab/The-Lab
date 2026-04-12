import { describe, expect, it } from "vitest";
import {
  pickProofMoreContextCopy,
  safeCustomerAiExplanation,
} from "./proofSupportingAiExplanation";

describe("safeCustomerAiExplanation", () => {
  it("returns null for null, missing fields, or invalid tone", () => {
    expect(safeCustomerAiExplanation(null)).toBeNull();
    expect(safeCustomerAiExplanation(undefined)).toBeNull();
    expect(safeCustomerAiExplanation({})).toBeNull();
    expect(
      safeCustomerAiExplanation({
        headline: "",
        body: "b",
        tone: "clear",
        groundedIn: { bestActionKey: "k" },
      }),
    ).toBeNull();
    expect(
      safeCustomerAiExplanation({
        headline: "h",
        body: "b",
        tone: "weird",
        groundedIn: {},
      }),
    ).toBeNull();
    expect(
      safeCustomerAiExplanation({
        headline: "h",
        body: "b",
        tone: "clear",
        groundedIn: { bestActionKey: 1 },
      }),
    ).toBeNull();
  });

  it("accepts a well-formed payload", () => {
    const x = safeCustomerAiExplanation({
      headline: "H",
      body: "B",
      tone: "calm",
      nextStepLabel: "Go",
      groundedIn: {
        bestActionKey: "proof_attachment",
        explanationType: "requirement",
        guidanceType: null,
      },
    });
    expect(x).not.toBeNull();
    expect(x!.headline).toBe("H");
    expect(x!.body).toBe("B");
    expect(x!.nextStepLabel).toBe("Go");
    expect(x!.groundedIn.bestActionKey).toBe("proof_attachment");
  });
});

describe("pickProofMoreContextCopy", () => {
  it("returns null when AI is absent or unusable", () => {
    expect(pickProofMoreContextCopy(null)).toBeNull();
    expect(
      pickProofMoreContextCopy({
        headline: "   ",
        body: "   ",
        tone: "clear",
        groundedIn: {},
      }),
    ).toBeNull();
  });

  it("returns trimmed copy when valid", () => {
    expect(
      pickProofMoreContextCopy({
        headline: "  Title  ",
        body: "  Body text  ",
        tone: "supportive",
        groundedIn: { bestActionKey: "x" },
      }),
    ).toEqual({ headline: "Title", body: "Body text" });
  });
});
