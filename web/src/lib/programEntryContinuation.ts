import { safeAppPath } from "@/lib/postAuthRedirect";

/** In-app destinations where we frame auth as “entering the program” (not client workflow state). */
export function resolvedProgramNextFromSearch(search: string): string | null {
  try {
    const q = new URLSearchParams(search.startsWith("?") ? search.slice(1) : search);
    return safeAppPath(q.get("next"));
  } catch {
    return null;
  }
}

export function isProgramOnboardingNext(path: string | null | undefined): boolean {
  if (!path) return false;
  if (path === "/get-report" || path.startsWith("/get-report/")) return true;
  if (path === "/upload") return true;
  return false;
}

export function afterVerifyProgramLine(returnPath: string): string {
  if (returnPath === "/get-report" || returnPath.startsWith("/get-report/")) {
    return "As soon as this is confirmed, your next program step is Step 1: get your credit report — that file is what powers your analysis.";
  }
  if (returnPath === "/upload") {
    return "As soon as this is confirmed, you’ll continue to upload your report — that’s where we parse your file and guide you through findings and next actions.";
  }
  return "As soon as this is confirmed, we’ll take you to the next screen so you can keep moving forward.";
}
