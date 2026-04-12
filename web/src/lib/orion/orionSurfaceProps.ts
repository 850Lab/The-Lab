/**
 * Maps ORION surface intent to coarse presentation hints — no layout or copy decisions.
 */

import type {
  OrionPrimaryRenderable,
  OrionRenderIntent,
  OrionPrimarySurfaceType,
} from "@/lib/orion/orionViewModel";

export type OrionSurfaceVisualHint = {
  /** Container emphasis for a strip/banner wrapper. */
  emphasis: "high" | "medium" | "low";
  /** Semantic tone for borders/background (Tailwind-oriented tokens). */
  tone: "amber" | "emerald" | "zinc" | "slate";
};

export function hintForPrimarySurface(
  surfaceType: OrionPrimarySurfaceType,
  renderIntent: OrionRenderIntent,
): OrionSurfaceVisualHint {
  if (surfaceType === "warning_banner" || renderIntent === "warning") {
    return { emphasis: "high", tone: "amber" };
  }
  if (surfaceType === "completion_status" || renderIntent === "completion") {
    return { emphasis: "low", tone: "slate" };
  }
  if (surfaceType === "passive_status" || renderIntent === "waiting") {
    return { emphasis: "medium", tone: "zinc" };
  }
  if (surfaceType === "hero_panel" || renderIntent === "requirement") {
    return { emphasis: "high", tone: "emerald" };
  }
  if (renderIntent === "review") {
    return { emphasis: "medium", tone: "emerald" };
  }
  return { emphasis: "medium", tone: "zinc" };
}

export function primaryHeadlineFromRenderable(p: OrionPrimaryRenderable): string | null {
  const c = p.content;
  if (!c) return null;
  if (typeof c.message === "string" && c.message.trim()) return c.message.trim();
  if (typeof c.summary === "string" && c.summary.trim()) return c.summary.trim();
  if (typeof c.label === "string" && c.label.trim()) return c.label.trim();
  return null;
}

export function supportingHeadlineFromContent(content: Record<string, unknown> | null): string | null {
  if (!content) return null;
  if (typeof content.summary === "string" && content.summary.trim()) return content.summary.trim();
  if (typeof content.message === "string" && content.message.trim()) return content.message.trim();
  if (typeof content.label === "string" && content.label.trim()) return content.label.trim();
  return null;
}
