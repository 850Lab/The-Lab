import { useEffect, useState } from "react";
import { mccGet, mccPost, formatMccErrorMessage } from "@/lib/missionControlApi";

type Customer = {
  id: number;
  email: string;
  display_name: string;
  role: string;
  is_founder: boolean;
  created_at: string;
  report_count: number;
  letter_count: number;
};

type Report = {
  id: number;
  bureau: string;
  upload_date: string;
  full_text_len: number | null;
  letter_count: number;
  parsed_account_count: number;
};

type Letter = {
  id: number;
  report_id: number;
  bureau: string;
  letter_len: number;
  letter_preview: string;
  created_at: string;
};

type LetterFull = Letter & { letter_text: string };

type Proof = {
  id: number;
  bureau: string;
  file_name: string;
  doc_type: string;
  file_type: string;
  file_size: number;
};

type CustomerDetail = {
  user: {
    id: number;
    email: string;
    display_name: string;
    role: string;
    tier: string;
    is_founder: boolean;
    created_at: string;
  };
  reports: Report[];
  letters: Letter[];
  lettersFull: LetterFull[];
  proofs: Proof[];
  signatures: { id: number; created_at: string }[];
  entitlements: { ai_rounds: number; letters: number; mailings: number };
  mailApproved: boolean;
};

export function McCustomers() {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<CustomerDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [expandedLetter, setExpandedLetter] = useState<number | null>(null);
  const [approving, setApproving] = useState(false);

  useEffect(() => {
    setLoading(true);
    mccGet<{ customers: Customer[] }>("/internal/admin/customers")
      .then((d) => setCustomers(d.customers))
      .catch((e) => setError(formatMccErrorMessage(e)))
      .finally(() => setLoading(false));
  }, []);

  const loadDetail = (userId: number) => {
    setSelectedId(userId);
    setDetailLoading(true);
    setDetail(null);
    setExpandedLetter(null);
    mccGet<CustomerDetail>(`/internal/admin/customer/${userId}`)
      .then(setDetail)
      .catch((e) => setError(formatMccErrorMessage(e)))
      .finally(() => setDetailLoading(false));
  };

  const toggleMailApproval = async () => {
    if (!detail) return;
    setApproving(true);
    try {
      const endpoint = detail.mailApproved
        ? "/internal/admin/mail/revoke"
        : "/internal/admin/mail/approve";
      await mccPost(endpoint, { user_id: detail.user.id });
      loadDetail(detail.user.id);
    } catch (e) {
      setError(formatMccErrorMessage(e));
    } finally {
      setApproving(false);
    }
  };

  if (loading) return <p className="text-lab-muted text-sm">Loading customers...</p>;
  if (error) return <p className="text-red-400 text-sm">{error}</p>;

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-lab-text">Customers</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-1 space-y-1 max-h-[75vh] overflow-auto">
          {customers.map((c) => (
            <button
              key={c.id}
              onClick={() => loadDetail(c.id)}
              className={`w-full text-left rounded px-3 py-2 text-sm transition ${
                selectedId === c.id
                  ? "bg-lab-accent/20 border border-lab-accent/40"
                  : "bg-lab-elevated hover:bg-lab-elevated/80 border border-transparent"
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-lab-text truncate">{c.display_name || c.email}</span>
                <span className="text-xs text-lab-muted">#{c.id}</span>
              </div>
              <div className="text-xs text-lab-muted mt-0.5">
                {c.email} {c.is_founder && <span className="text-amber-400 ml-1">Founder</span>}
              </div>
              <div className="text-xs text-lab-subtle mt-0.5">
                {c.report_count} reports, {c.letter_count} letters
              </div>
            </button>
          ))}
        </div>

        <div className="lg:col-span-2">
          {detailLoading && <p className="text-lab-muted text-sm">Loading...</p>}
          {!detailLoading && !detail && (
            <p className="text-lab-subtle text-sm">Select a customer to view details.</p>
          )}
          {detail && <CustomerDetailView detail={detail} expandedLetter={expandedLetter} setExpandedLetter={setExpandedLetter} toggleMailApproval={toggleMailApproval} approving={approving} />}
        </div>
      </div>
    </div>
  );
}

function CustomerDetailView({
  detail,
  expandedLetter,
  setExpandedLetter,
  toggleMailApproval,
  approving,
}: {
  detail: CustomerDetail;
  expandedLetter: number | null;
  setExpandedLetter: (id: number | null) => void;
  toggleMailApproval: () => void;
  approving: boolean;
}) {
  const { user, reports, letters, lettersFull, proofs, signatures, entitlements, mailApproved } = detail;

  return (
    <div className="space-y-4">
      <div className="bg-lab-surface border border-white/10 rounded-lg p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h3 className="text-base font-semibold text-lab-text">{user.display_name || user.email}</h3>
            <p className="text-xs text-lab-muted">{user.email} &middot; ID #{user.id} &middot; {user.role} &middot; {user.tier || "no tier"}</p>
          </div>
          {user.is_founder && (
            <span className="text-xs font-bold bg-amber-500/20 text-amber-400 px-2 py-0.5 rounded">FOUNDER</span>
          )}
        </div>
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="bg-lab-elevated rounded p-2">
            <div className="text-lg font-bold text-lab-accent">{entitlements.ai_rounds}</div>
            <div className="text-xs text-lab-muted">AI Rounds</div>
          </div>
          <div className="bg-lab-elevated rounded p-2">
            <div className="text-lg font-bold text-lab-accent">{entitlements.letters}</div>
            <div className="text-xs text-lab-muted">Letters</div>
          </div>
          <div className="bg-lab-elevated rounded p-2">
            <div className="text-lg font-bold text-lab-accent">{entitlements.mailings}</div>
            <div className="text-xs text-lab-muted">Mailings</div>
          </div>
        </div>
        <div className="mt-3 flex items-center justify-between">
          <div className="text-sm">
            Mail approval:{" "}
            <span className={mailApproved ? "text-green-400 font-medium" : "text-amber-400 font-medium"}>
              {mailApproved ? "Approved" : "Pending"}
            </span>
          </div>
          <button
            onClick={toggleMailApproval}
            disabled={approving}
            className={`text-xs px-3 py-1 rounded font-medium ${
              mailApproved
                ? "bg-red-500/20 text-red-400 hover:bg-red-500/30"
                : "bg-green-500/20 text-green-400 hover:bg-green-500/30"
            } disabled:opacity-50`}
          >
            {approving ? "..." : mailApproved ? "Revoke" : "Approve Mail"}
          </button>
        </div>
      </div>

      <div className="bg-lab-surface border border-white/10 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-lab-text mb-2">Reports ({reports.length})</h4>
        {reports.length === 0 ? (
          <p className="text-xs text-lab-subtle">No reports uploaded.</p>
        ) : (
          <div className="space-y-1">
            {reports.map((r) => (
              <div key={r.id} className="flex items-center justify-between bg-lab-elevated rounded px-3 py-2 text-sm">
                <div>
                  <span className="font-medium text-lab-text capitalize">{r.bureau}</span>
                  <span className="text-xs text-lab-muted ml-2">Report #{r.id}</span>
                </div>
                <div className="flex items-center gap-3 text-xs text-lab-muted">
                  <span>{r.parsed_account_count} accounts parsed</span>
                  <span>{r.letter_count} letter{r.letter_count !== 1 ? "s" : ""}</span>
                  <span className={r.full_text_len ? "text-green-400" : "text-red-400"}>
                    {r.full_text_len ? "text OK" : "no text"}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-lab-surface border border-white/10 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-lab-text mb-2">Letters ({letters.length})</h4>
        {letters.length === 0 ? (
          <p className="text-xs text-lab-subtle">No letters generated.</p>
        ) : (
          <div className="space-y-2">
            {letters.map((l) => {
              const full = lettersFull.find((f) => f.id === l.id);
              const isExpanded = expandedLetter === l.id;
              return (
                <div key={l.id} className="bg-lab-elevated rounded overflow-hidden">
                  <button
                    onClick={() => setExpandedLetter(isExpanded ? null : l.id)}
                    className="w-full text-left px-3 py-2 flex items-center justify-between hover:bg-white/5"
                  >
                    <div className="text-sm">
                      <span className="font-medium text-lab-text capitalize">{l.bureau}</span>
                      <span className="text-xs text-lab-muted ml-2">Letter #{l.id} &middot; {(l.letter_len / 1024).toFixed(1)}KB</span>
                    </div>
                    <span className="text-xs text-lab-accent">{isExpanded ? "Collapse" : "View full letter"}</span>
                  </button>
                  {isExpanded && full && (
                    <pre className="px-3 pb-3 text-xs text-lab-muted whitespace-pre-wrap max-h-[60vh] overflow-auto border-t border-white/5 pt-2 font-mono leading-relaxed">
                      {full.letter_text}
                    </pre>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      <div className="bg-lab-surface border border-white/10 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-lab-text mb-2">Proof Documents ({proofs.length})</h4>
        {proofs.length === 0 ? (
          <p className="text-xs text-lab-subtle">No proof documents uploaded.</p>
        ) : (
          <div className="space-y-1">
            {proofs.map((p) => (
              <div key={p.id} className="flex items-center justify-between bg-lab-elevated rounded px-3 py-2 text-sm">
                <div>
                  <span className="font-medium text-lab-text">{p.doc_type === "government_id" ? "Government ID" : "Address Proof"}</span>
                  <span className="text-xs text-lab-muted ml-2">{p.file_name}</span>
                </div>
                <span className="text-xs text-lab-muted">{(p.file_size / 1024).toFixed(0)}KB &middot; {p.file_type}</span>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-lab-surface border border-white/10 rounded-lg p-4">
        <h4 className="text-sm font-semibold text-lab-text mb-2">Signature</h4>
        <p className="text-xs text-lab-subtle">
          {signatures.length > 0 ? `${signatures.length} signature(s) on file` : "No signature on file"}
        </p>
      </div>
    </div>
  );
}
