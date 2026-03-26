const KEY = "850lab_proof_verification_v1";

export type ProofVerificationSnapshot = {
  idFileName: string | null;
  idComplete: boolean;
  addressFileName: string | null;
  addressComplete: boolean;
  signatureMode: "draw" | "type";
  signatureTyped: string;
  /** PNG data URL when user confirms a drawn signature; may be empty after load if omitted */
  signatureDrawDataUrl: string | null;
  signatureDrawComplete: boolean;
  signatureComplete: boolean;
  updatedAt: number;
};

const defaultSnapshot = (): ProofVerificationSnapshot => ({
  idFileName: null,
  idComplete: false,
  addressFileName: null,
  addressComplete: false,
  signatureMode: "draw",
  signatureTyped: "",
  signatureDrawDataUrl: null,
  signatureDrawComplete: false,
  signatureComplete: false,
  updatedAt: 0,
});

export function loadProofVerification(): ProofVerificationSnapshot {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return defaultSnapshot();
    const p = JSON.parse(raw) as Partial<ProofVerificationSnapshot>;
    return {
      ...defaultSnapshot(),
      ...p,
      signatureMode: p.signatureMode === "type" ? "type" : "draw",
    };
  } catch {
    return defaultSnapshot();
  }
}

export function saveProofVerification(s: ProofVerificationSnapshot): void {
  const next = { ...s, updatedAt: Date.now() };
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    try {
      const lean: ProofVerificationSnapshot = {
        ...next,
        signatureDrawDataUrl: null,
        signatureDrawComplete: false,
        signatureComplete: next.signatureMode === "type" && next.signatureTyped.trim().length >= 2,
      };
      localStorage.setItem(KEY, JSON.stringify(lean));
    } catch {
      /* quota or private mode — in-session flow still works */
    }
  }
}
