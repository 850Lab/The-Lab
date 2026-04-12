import { describe, expect, it } from "vitest";
import { Fragment } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ProofSupportScriptPanel } from "./ProofSupportScriptPanel";

describe("ProofSupportScriptPanel", () => {
  it("renders nothing when aiScript is null or invalid", () => {
    expect(renderToStaticMarkup(<ProofSupportScriptPanel aiScript={null} />)).toBe("");
    expect(renderToStaticMarkup(<ProofSupportScriptPanel aiScript={{}} />)).toBe("");
  });

  it("renders suggested wording block without replacing hero (hero is separate on page)", () => {
    const html = renderToStaticMarkup(
      <ProofSupportScriptPanel
        aiScript={{
          scriptIntent: "proof_submission_support",
          title: "Framing your proof step",
          intro: "Optional intro.",
          lines: [{ speaker: "user", text: "Hello" }],
          talkingPoints: ["Remember to follow the screen."],
          tone: "clear",
        }}
      />,
    );
    expect(html).toContain("Suggested wording");
    expect(html).toContain("Framing your proof step");
    expect(html).toContain("rounded-lg");
    expect(html).toContain("Hello");
    expect(html).toContain("Remember to follow the screen.");
  });

  it("can sit under deterministic hero copy without replacing it", () => {
    const html = renderToStaticMarkup(
      <Fragment>
        <h1 className="step-title">Deterministic ORION title</h1>
        <ProofSupportScriptPanel
          aiScript={{
            scriptIntent: "proof_submission_support",
            title: "Support title",
            intro: null,
            lines: [{ speaker: "user", text: "Line" }],
            talkingPoints: [],
            tone: "calm",
          }}
        />
      </Fragment>,
    );
    expect(html).toContain("Deterministic ORION title");
    expect(html).toContain("Suggested wording");
    expect(html).toContain("Support title");
  });
});
