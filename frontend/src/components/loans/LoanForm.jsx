import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";

function LoanForm({ onSaved }) {
  const [borrowers, setBorrowers] = useState([]);
  const [form, setForm] = useState({
    member_id: "",
    purpose: "Working Capital",
    amount: "",
    annual_rate: "0",
    term_months: "1",
    method: "reducing",
    applied_date: new Date().toISOString().slice(0, 10),
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    apiFetch("/api/borrowers?limit=200")
      .then((res) => {
        const list = res?.data?.borrowers || [];
        setBorrowers(list);
        if (!form.member_id && list.length > 0) {
          setForm((prev) => ({ ...prev, member_id: list[0].id }));
        }
      })
      .catch((err) => setError(err.message || "Failed to load borrowers"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const disabled = useMemo(() => {
    return saving || !form.member_id || !form.amount || Number(form.amount) <= 0;
  }, [form, saving]);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      await apiFetch("/api/loans", {
        method: "POST",
        body: JSON.stringify({
          member_id: form.member_id,
          purpose: form.purpose,
          amount: Number(form.amount),
          annual_rate: Number(form.annual_rate || 0),
          term_months: Number(form.term_months || 1),
          method: form.method,
          applied_date: form.applied_date,
        }),
      });
      setForm((prev) => ({ ...prev, amount: "", annual_rate: "0", term_months: "1" }));
      if (onSaved) onSaved();
    } catch (err) {
      setError(err.message || "Failed to submit loan");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="panel stack">
      <h3>Loan Form</h3>
      <p className="muted">Create a loan application with reusable form logic.</p>

      {error ? <p className="error-box">{error}</p> : null}

      <label>
        Borrower
        <select
          value={form.member_id}
          onChange={(e) => setForm((prev) => ({ ...prev, member_id: e.target.value }))}
        >
          {borrowers.map((b) => (
            <option value={b.id} key={b.id}>{b.name} ({b.id})</option>
          ))}
        </select>
      </label>

      <div className="two-col">
        <label>
          Principal (KES)
          <input
            type="number"
            value={form.amount}
            onChange={(e) => setForm((prev) => ({ ...prev, amount: e.target.value }))}
          />
        </label>
        <label>
          Monthly Rate (%)
          <input
            type="number"
            value={form.annual_rate}
            onChange={(e) => setForm((prev) => ({ ...prev, annual_rate: e.target.value }))}
          />
        </label>
      </div>

      <div className="two-col">
        <label>
          Term (months)
          <input
            type="number"
            value={form.term_months}
            onChange={(e) => setForm((prev) => ({ ...prev, term_months: e.target.value }))}
          />
        </label>
        <label>
          Applied Date
          <input
            type="date"
            value={form.applied_date}
            onChange={(e) => setForm((prev) => ({ ...prev, applied_date: e.target.value }))}
          />
        </label>
      </div>

      <label>
        Purpose
        <input
          type="text"
          value={form.purpose}
          onChange={(e) => setForm((prev) => ({ ...prev, purpose: e.target.value }))}
        />
      </label>

      <button type="submit" className="primary-btn" disabled={disabled}>
        {saving ? "Submitting..." : "Submit Loan"}
      </button>
    </form>
  );
}

export default LoanForm;
