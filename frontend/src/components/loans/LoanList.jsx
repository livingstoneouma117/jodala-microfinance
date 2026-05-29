import { useEffect, useMemo, useState } from "react";
import { apiFetch, apiFetchBlob } from "../../lib/api";
import { formatDate, formatKES, statusClass } from "../../lib/format";
import DataTable from "../ui/DataTable";
import Modal from "../ui/Modal";
import { useToast } from "../ui/Toast";

const TODAY = new Date().toISOString().slice(0, 10);

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function LoanDetails({ loanId, onChanged }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);
  const [members, setMembers] = useState([]);
  const [guarantorForm, setGuarantorForm] = useState({ guarantor_id: "", amount: "", notes: "" });
  const [restructureForm, setRestructureForm] = useState({ term_months: "", annual_rate: "", method: "reducing", effective_date: TODAY, notes: "" });
  const [saving, setSaving] = useState(false);
  const pushToast = useToast();

  async function loadDetails() {
    setLoading(true);
    setError("");
    try {
      const [loanRes, membersRes] = await Promise.all([
        apiFetch(`/api/loans/${loanId}`),
        apiFetch("/api/members?limit=300&type=member"),
      ]);
      const data = loanRes?.data || null;
      setPayload(data);
      setMembers(membersRes?.data?.members || []);
      if (data?.loan) {
        setRestructureForm((prev) => ({
          ...prev,
          term_months: String(data.loan.term_months || ""),
          annual_rate: String(data.loan.annual_rate || ""),
          method: data.loan.method || "reducing",
        }));
      }
    } catch (err) {
      setError(err.message || "Failed to load loan details");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDetails();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loanId]);

  if (loading) return <p className="muted">Loading loan details...</p>;
  if (error) return <p className="error-box">{error}</p>;
  if (!payload) return <p className="muted">No details available.</p>;

  const loan = payload.loan || {};
  const summary = payload.summary || {};
  const schedule = payload.schedule || [];
  const guarantors = payload.guarantors || [];
  const canRestructure = ["active", "overdue"].includes(String(loan.status || "").toLowerCase());

  async function addGuarantor(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await apiFetch(`/api/loans/${loanId}/guarantors`, {
        method: "POST",
        body: JSON.stringify({
          guarantor_id: guarantorForm.guarantor_id,
          amount: Number(guarantorForm.amount || 0),
          notes: guarantorForm.notes,
        }),
      });
      pushToast("Guarantor added.", "success");
      setGuarantorForm({ guarantor_id: "", amount: "", notes: "" });
      await loadDetails();
      onChanged?.();
    } catch (err) {
      pushToast(err.message || "Could not add guarantor", "error");
    } finally {
      setSaving(false);
    }
  }

  async function removeGuarantor(row) {
    setSaving(true);
    try {
      await apiFetch(`/api/loans/${loanId}/guarantors/${row.id}`, { method: "DELETE" });
      pushToast("Guarantor removed.", "success");
      await loadDetails();
    } catch (err) {
      pushToast(err.message || "Could not remove guarantor", "error");
    } finally {
      setSaving(false);
    }
  }

  async function restructureLoan(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await apiFetch(`/api/loans/${loanId}/restructure`, {
        method: "POST",
        body: JSON.stringify({
          term_months: Number(restructureForm.term_months),
          annual_rate: Number(restructureForm.annual_rate || 0),
          method: restructureForm.method,
          effective_date: restructureForm.effective_date,
          notes: restructureForm.notes,
        }),
      });
      pushToast("Loan restructured.", "success");
      await loadDetails();
      onChanged?.();
    } catch (err) {
      pushToast(err.message || "Could not restructure loan", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <div className="card-grid compact">
        <div className="surface-card"><span>Borrower</span><strong>{loan.member_name || loan.member_id || "-"}</strong></div>
        <div className="surface-card"><span>Principal</span><strong>{formatKES(loan.amount)}</strong></div>
        <div className="surface-card"><span>Total Repaid</span><strong>{formatKES(loan.total_paid)}</strong></div>
        <div className="surface-card"><span>Outstanding</span><strong>{formatKES(summary.outstanding)}</strong></div>
      </div>

      <section className="surface-card stack">
        <div className="row-between">
          <h4>Guarantors</h4>
          <span className="muted">Attach members guaranteeing this loan.</span>
        </div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Guarantor</th><th>Phone</th><th>Guaranteed</th><th>Savings</th><th></th></tr></thead>
            <tbody>
              {guarantors.map((row) => (
                <tr key={row.id}>
                  <td>{row.guarantor_name || row.guarantor_id}</td>
                  <td>{row.guarantor_phone || "-"}</td>
                  <td>{formatKES(row.amount)}</td>
                  <td>{formatKES(row.guarantor_savings)}</td>
                  <td><button type="button" className="ghost-btn" disabled={saving} onClick={() => removeGuarantor(row)}>Remove</button></td>
                </tr>
              ))}
              {guarantors.length === 0 ? <tr><td colSpan={5} className="table-empty">No guarantors attached.</td></tr> : null}
            </tbody>
          </table>
        </div>
        <form className="row-form" onSubmit={addGuarantor}>
          <select value={guarantorForm.guarantor_id} onChange={(event) => setGuarantorForm((prev) => ({ ...prev, guarantor_id: event.target.value }))} required>
            <option value="">Select guarantor</option>
            {members.filter((member) => member.id !== loan.member_id).map((member) => (
              <option key={member.id} value={member.id}>{member.name} ({member.id})</option>
            ))}
          </select>
          <input type="number" min="0" placeholder="Guaranteed amount" value={guarantorForm.amount} onChange={(event) => setGuarantorForm((prev) => ({ ...prev, amount: event.target.value }))} />
          <input type="text" placeholder="Notes" value={guarantorForm.notes} onChange={(event) => setGuarantorForm((prev) => ({ ...prev, notes: event.target.value }))} />
          <button type="submit" className="primary-btn" disabled={saving}>Add Guarantor</button>
        </form>
      </section>

      <section className="surface-card stack">
        <div className="row-between">
          <h4>Loan Restructuring</h4>
          <span className="muted">Extend term or adjust rate on active loans.</span>
        </div>
        {!canRestructure ? <p className="muted">Only active or overdue loans can be restructured.</p> : (
          <form className="stack" onSubmit={restructureLoan}>
            <div className="two-col">
              <label>New Term (months)<input type="number" min="1" value={restructureForm.term_months} onChange={(event) => setRestructureForm((prev) => ({ ...prev, term_months: event.target.value }))} required /></label>
              <label>New Annual Rate %<input type="number" min="0" step="0.01" value={restructureForm.annual_rate} onChange={(event) => setRestructureForm((prev) => ({ ...prev, annual_rate: event.target.value }))} /></label>
            </div>
            <div className="two-col">
              <label>Method<select value={restructureForm.method} onChange={(event) => setRestructureForm((prev) => ({ ...prev, method: event.target.value }))}><option value="reducing">Reducing Balance</option><option value="flat">Flat Rate</option></select></label>
              <label>Effective Date<input type="date" value={restructureForm.effective_date} onChange={(event) => setRestructureForm((prev) => ({ ...prev, effective_date: event.target.value }))} /></label>
            </div>
            <label>Reason / Notes<input value={restructureForm.notes} onChange={(event) => setRestructureForm((prev) => ({ ...prev, notes: event.target.value }))} placeholder="Optional" /></label>
            <button type="submit" className="primary-btn" disabled={saving}>{saving ? "Saving..." : "Restructure Loan"}</button>
          </form>
        )}
      </section>

      <div className="table-wrap">
        <table>
          <thead><tr><th>#</th><th>Due Date</th><th>Repayment</th><th>Balance</th><th>Paid</th></tr></thead>
          <tbody>
            {schedule.slice(0, 12).map((row) => (
              <tr key={row.id || `${loan.id}-${row.installment}`}>
                <td>{row.installment}</td>
                <td>{formatDate(row.due_date)}</td>
                <td>{formatKES(row.repayment)}</td>
                <td>{formatKES(row.balance)}</td>
                <td>{row.paid ? "Yes" : "No"}</td>
              </tr>
            ))}
            {schedule.length === 0 ? <tr><td colSpan={5} className="table-empty">No repayment schedule available yet.</td></tr> : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function LoanList({ refreshToken }) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const [selectedLoanId, setSelectedLoanId] = useState("");
  const [localRefresh, setLocalRefresh] = useState(0);
  const pushToast = useToast();

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    const query = new URLSearchParams({ status, q, page: String(page), limit: "10" });
    apiFetch(`/api/loans?${query.toString()}`)
      .then((res) => {
        if (!mounted) return;
        const data = res?.data || {};
        setRows(data.loans || []);
        setPages(Number(data.pages || 1));
        setError("");
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load loans");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => { mounted = false; };
  }, [page, q, refreshToken, status, localRefresh]);

  async function downloadStatement(row) {
    try {
      const res = await apiFetchBlob(`/api/loans/${row.id}/statement?format=pdf`);
      triggerDownload(res.blob, `loan-statement-${row.id}.pdf`);
      pushToast("Loan statement downloaded.", "success");
    } catch (err) {
      pushToast(err.message || "Could not download statement", "error");
    }
  }

  const columns = useMemo(() => [
    { key: "id", label: "Loan" },
    { key: "member_name", label: "Borrower", render: (row) => row.member_name || row.member_id },
    { key: "status", label: "Status", render: (row) => <span className={statusClass(row.status)}>{row.status}</span> },
    { key: "amount", label: "Principal", render: (row) => formatKES(row.amount) },
    { key: "total_paid", label: "Repaid", render: (row) => formatKES(row.total_paid) },
    { key: "outstanding", label: "Outstanding", render: (row) => formatKES(row.outstanding) },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="table-actions">
          <button type="button" className="ghost-btn" onClick={() => setSelectedLoanId(row.id)}>View</button>
          <button type="button" className="ghost-btn" onClick={() => downloadStatement(row)}>Download Statement</button>
        </div>
      ),
    },
  ], []);

  return (
    <section className="panel stack">
      <div className="row-between"><h3>Loan Portfolio</h3><span className="muted">All statuses visible</span></div>
      <div className="toolbar">
        <input type="search" placeholder="Search loan, borrower, purpose" value={q} onChange={(event) => { setPage(1); setQ(event.target.value); }} />
        <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }}>
          <option value="all">All Status</option><option value="pending">Pending</option><option value="approved">Approved</option><option value="active">Active</option><option value="overdue">Overdue</option><option value="completed">Completed</option><option value="rejected">Rejected</option>
        </select>
      </div>
      {error ? <p className="error-box">{error}</p> : null}
      <DataTable columns={columns} rows={rows} rowKey="id" loading={loading} page={page} pages={pages} onPageChange={setPage} emptyMessage="No loans found for this filter." />
      <Modal open={Boolean(selectedLoanId)} title={`Loan Details ${selectedLoanId}`} onClose={() => setSelectedLoanId("")} maxWidth="1040px">
        {selectedLoanId ? <LoanDetails loanId={selectedLoanId} onChanged={() => setLocalRefresh((prev) => prev + 1)} /> : null}
      </Modal>
    </section>
  );
}

export default LoanList;
