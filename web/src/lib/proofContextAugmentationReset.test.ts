import { describe, expect, it, vi } from "vitest";
import { clearOptionalProofContextAugmentations } from "./proofContextAugmentationReset";

describe("clearOptionalProofContextAugmentations", () => {
  it("clears explanation and script setters (upload/signature refresh contract)", () => {
    const setEx = vi.fn();
    const setScr = vi.fn();
    clearOptionalProofContextAugmentations(setEx, setScr);
    expect(setEx).toHaveBeenCalledWith(null);
    expect(setScr).toHaveBeenCalledWith(null);
  });
});
