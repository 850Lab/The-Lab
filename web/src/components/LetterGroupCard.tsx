import { motion } from "framer-motion";
import type { LetterRow } from "@/lib/letterTypes";

type Props = {
  letter: LetterRow;
  onViewLetter: () => void;
};

function previewSummaryLine(letter: LetterRow): string {
  const cats = letter.categories?.filter(Boolean) ?? [];
  if (cats.length) return cats.slice(0, 4).join(" · ");
  const n = letter.charCount ?? 0;
  return n ? `${n.toLocaleString()} characters` : "Bureau dispute letter";
}

export function LetterGroupCard({ letter, onViewLetter }: Props) {
  const v = letter.violationCount ?? 0;
  const bureau = letter.bureauDisplay || letter.bureau;
  const cats = letter.categories?.filter(Boolean) ?? [];
  const showDetails = cats.length > 2;

  return (
    <motion.article
      variants={{
        hidden: { opacity: 0, y: 14 },
        show: {
          opacity: 1,
          y: 0,
          transition: { duration: 0.44, ease: [0.22, 1, 0.36, 1] },
        },
      }}
      className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-5 shadow-lg shadow-black/20 sm:px-6 sm:py-5"
    >
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div>
          <h3 className="text-[15px] font-semibold text-lab-text sm:text-base">
            {bureau}{" "}
            <span className="font-normal text-lab-muted">—</span>{" "}
            <span className="text-lab-text">
              {v} cited issue{v === 1 ? "" : "s"}
            </span>
          </h3>
          <p className="mt-1.5 text-sm text-lab-muted">
            This letter group covers items prepared for {bureau}. Review this draft before the next
            step — nothing is mailed from here.
          </p>
          {showDetails ? (
            <details className="mt-3 text-xs text-lab-subtle">
              <summary className="cursor-pointer select-none text-lab-muted hover:text-lab-text">
                Items referenced in this letter
              </summary>
              <p className="mt-2 leading-relaxed">{cats.join(" · ")}</p>
            </details>
          ) : (
            <p className="mt-3 text-xs text-lab-subtle">{previewSummaryLine(letter)}</p>
          )}
        </div>
        <motion.button
          type="button"
          onClick={onViewLetter}
          className="mt-4 shrink-0 self-start rounded-lg border border-white/[0.1] bg-white/[0.03] px-3.5 py-2 text-sm font-medium text-lab-text transition-colors hover:border-white/[0.22] hover:bg-white/[0.06] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-500/40 sm:mt-0 sm:self-center"
          whileHover={{ y: -1 }}
          whileTap={{ scale: 0.98 }}
          transition={{ type: "spring", stiffness: 480, damping: 28 }}
        >
          Preview letter
        </motion.button>
      </div>
    </motion.article>
  );
}
