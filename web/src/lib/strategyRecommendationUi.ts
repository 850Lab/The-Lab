import type { StrategyRecommendationItem } from "@/lib/strategyTypes";

export function strategyConfidencePillClass(
  level: StrategyRecommendationItem["confidence"]["level"],
): string {
  if (level === "high")
    return "bg-emerald-500/20 text-emerald-200/95 ring-1 ring-emerald-500/30";
  if (level === "medium")
    return "bg-zinc-500/15 text-zinc-200/90 ring-1 ring-white/10";
  return "bg-amber-500/10 text-amber-100/90 ring-1 ring-amber-400/25";
}

export function strategyConfidenceUserLabel(
  level: StrategyRecommendationItem["confidence"]["level"],
): string {
  if (level === "high") return "Strong signal";
  if (level === "medium") return "Moderate confidence";
  return "Review carefully";
}
