import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ProofMoreContextPanel } from "./ProofMoreContextPanel";

describe("ProofMoreContextPanel", () => {
  it("renders nothing when aiExplanation is null or invalid", () => {
    expect(renderToStaticMarkup(<ProofMoreContextPanel aiExplanation={null} />)).toBe("");
    expect(renderToStaticMarkup(<ProofMoreContextPanel aiExplanation={undefined} />)).toBe("");
    expect(renderToStaticMarkup(<ProofMoreContextPanel aiExplanation={{}} />)).toBe("");
  });

  it("renders supporting copy without replacing deterministic hero elsewhere", () => {
    const html = renderToStaticMarkup(
      <ProofMoreContextPanel
        aiExplanation={{
          headline: "Supporting headline",
          body: "Supporting body.",
          tone: "clear",
          groundedIn: { bestActionKey: "k" },
        }}
      />,
    );
    expect(html).toContain("More context");
    expect(html).toContain("Supporting headline");
    expect(html).toContain("Supporting body.");
  });
});
