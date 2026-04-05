import type { PublicDemoLetter } from "@/lib/publicDemoTypes";

type BureauKey = "equifax" | "transunion" | "experian";

const BUREAU_ORDER: BureauKey[] = ["equifax", "transunion", "experian"];

const TILE: Record<
  BureauKey,
  { label: string; className: string; testId: string }
> = {
  equifax: {
    label: "Equifax",
    className:
      "border-red-700/45 bg-gradient-to-b from-red-950/50 to-red-950/20 text-red-100 hover:border-red-500/55 hover:from-red-900/45",
    testId: "demo-bureau-tile-equifax",
  },
  transunion: {
    label: "TransUnion",
    className:
      "border-emerald-700/45 bg-gradient-to-b from-emerald-950/45 to-emerald-950/15 text-emerald-100 hover:border-emerald-500/50 hover:from-emerald-900/40",
    testId: "demo-bureau-tile-transunion",
  },
  experian: {
    label: "Experian",
    className:
      "border-blue-800/50 bg-gradient-to-b from-blue-950/55 to-blue-950/20 text-blue-100 hover:border-blue-500/55 hover:from-blue-900/45",
    testId: "demo-bureau-tile-experian",
  },
};

function normalizeBureauBlob(L: PublicDemoLetter): string {
  return `${L.bureau ?? ""} ${L.bureauDisplay ?? ""}`.toLowerCase().replace(/\s+/g, "");
}

function letterForBureau(letters: PublicDemoLetter[], key: BureauKey): PublicDemoLetter | null {
  const hit = letters.find((L) => {
    const b = normalizeBureauBlob(L);
    if (key === "equifax") return b.includes("equifax");
    if (key === "experian") return b.includes("experian");
    return b.includes("transunion");
  });
  return hit ?? null;
}

export type PublicDemoBureauLetterStripProps = {
  letters: PublicDemoLetter[];
  onOpen: (letter: PublicDemoLetter) => void;
};

export function PublicDemoBureauLetterStrip({ letters, onOpen }: PublicDemoBureauLetterStripProps) {
  return (
    <div data-testid="demo-bureau-letter-strip" className="mt-4">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-lab-subtle">
        Bureau letters
      </p>
      <p className="mt-1 text-xs text-lab-muted">Tap a bureau for full letter text.</p>
      <div className="mt-3 grid grid-cols-3 gap-2">
        {BUREAU_ORDER.map((key) => {
          const meta = TILE[key];
          const L = letterForBureau(letters, key);
          const disabled = !L;
          return (
            <button
              key={key}
              type="button"
              data-testid={meta.testId}
              disabled={disabled}
              onClick={() => L && onOpen(L)}
              className={`flex min-h-[4.5rem] flex-col items-center justify-center rounded-xl border px-1.5 py-3 text-center shadow-md shadow-black/20 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-lab-accent/40 disabled:cursor-not-allowed disabled:opacity-40 ${meta.className}`}
            >
              <span className="text-[11px] font-bold leading-tight sm:text-xs">{meta.label}</span>
              <span className="mt-1.5 line-clamp-2 text-[10px] font-medium leading-snug text-white/75">
                {L ? "Open letter" : "—"}
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
