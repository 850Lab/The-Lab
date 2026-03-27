/**
 * Single source of truth for report acquisition outbound links (override via Vite env in deploy).
 */

const DEFAULT_IDIQ_REPORT_URL =
  "https://www.myscoreiq.com/get-fico-max.aspx?offercode=432142YL";

const DEFAULT_ANNUAL_CREDIT_REPORT_URL = "https://www.annualcreditreport.com/";

export const IDIQ_AFFILIATE_URL: string =
  (import.meta.env.VITE_IDIQ_REPORT_URL as string | undefined)?.trim() || DEFAULT_IDIQ_REPORT_URL;

export const ANNUAL_CREDIT_REPORT_URL: string =
  (import.meta.env.VITE_ANNUAL_CREDIT_REPORT_URL as string | undefined)?.trim() ||
  DEFAULT_ANNUAL_CREDIT_REPORT_URL;

export function openExternalUrl(url: string): void {
  window.open(url, "_blank", "noopener,noreferrer");
}
