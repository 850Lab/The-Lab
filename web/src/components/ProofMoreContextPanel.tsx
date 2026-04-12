import { pickProofMoreContextCopy } from "@/lib/proofSupportingAiExplanation";

type Props = {
  /** Raw API value; may be null, invalid, or omitted upstream. */
  aiExplanation: unknown;
};

/**
 * Supporting copy only — placed below deterministic ORION hero on proof verification.
 */
export function ProofMoreContextPanel({ aiExplanation }: Props) {
  const copy = pickProofMoreContextCopy(aiExplanation);
  if (!copy) return null;

  return (
    <div className="mx-auto mt-5 max-w-lg rounded-xl border border-white/[0.06] bg-black/20 px-4 py-3.5 sm:px-5">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-lab-subtle">
        More context
      </p>
      <p className="mt-2 text-sm font-medium leading-snug text-lab-text">{copy.headline}</p>
      <p className="mt-2 text-sm leading-relaxed text-lab-muted">{copy.body}</p>
    </div>
  );
}
