import { PaymentCTASection } from "@/components/PaymentCTASection";
import { PaymentShell } from "@/components/PaymentShell";
import { PreparedItemsSummary, type PreparedCategory } from "@/components/PreparedItemsSummary";
import { PriceRow } from "@/components/PriceRow";
import { ValueRecapList } from "@/components/ValueRecapList";

const DEFAULT_RECAP = [
  "We send your dispute letters.",
  "Credit bureaus begin reviewing the items we challenged.",
  "You can track progress inside your account.",
] as const;

type Props = {
  onActivate: () => void;
  categories?: PreparedCategory[];
  amountDisplay?: string;
  recapLines?: readonly string[];
};

const defaultCategories: PreparedCategory[] = [
  { label: "Collections", count: 3 },
  { label: "Charge-offs", count: 2 },
  { label: "Late payments", count: 4 },
];

export function ActivationCard({
  onActivate,
  categories = defaultCategories,
  amountDisplay = "$199",
  recapLines = DEFAULT_RECAP,
}: Props) {
  return (
    <div className="rounded-xl border border-white/[0.08] bg-lab-surface px-5 py-6 shadow-xl shadow-black/25 sm:px-7 sm:py-8">
      <ValueRecapList lines={[...recapLines]} />

      <div className="my-7 border-t border-white/[0.06] sm:my-8" />

      <PreparedItemsSummary categories={categories} />

      <div className="mt-6">
        <PriceRow label="Total" amountDisplay={amountDisplay} />
      </div>

      <div className="mt-6">
        <PaymentShell />
      </div>

      <div className="mt-7 border-t border-white/[0.06] pt-6 sm:mt-8 sm:pt-7">
        <PaymentCTASection onActivate={onActivate} />
      </div>
    </div>
  );
}
