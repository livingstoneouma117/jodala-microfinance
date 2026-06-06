import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";
import { formatDate, formatKES, statusClass } from "../lib/format";
import DataTable from "../components/ui/DataTable";
import Modal from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";

const TODAY = new Date().toISOString().slice(0, 10);

function RepaymentsPage() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [q, setQ] = useState("");

  const [loans, setLoans] = useState([]);
  const [openModal, setOpenModal] = useState(false);
  const [form, setForm] = useState({
    loan_id: "",
    amount: "",
    payment_date: TODAY,
    method: "cash",
    reference: "",
    type: "installment",
  });
  const [saving, setSaving] = useState(false);

  const pushToast = useToast();

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    const query = new URLSearchParams({ page: String(page), limit: "10", q });

    apiFetch(`/api/repayments?${query.toString()}`)
      .then((res) => {
        if (!mounted) return;
        const data = res?.data || {};
        setRows(data.repayments || []);
        setPages(Number(data.pages || 1));
        setError("");
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load repayments");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [page, q]);

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/loans?status=all&limit=200")
      .then((res) => {
        if (!mounted) return;
        const all = res?.data?.loans || [];
        const eligible = all.filter((loan) => ["active", "overdue"].includes(String(loan.status || "").toLowerCase()));
        setLoans(eligible);
        if (!form.loan_id && eligible.length > 0) {
          setForm((prev) => ({ ...prev, loan_id: eligible[0].id }));
        }
      })
      .catch(() => {
        // keep page usable even if loan list fails
      });

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const selectedLoan = loans.find((loan) => String(loan.id) === String(form.loan_id));
    if (!selectedLoan) return;

    const outstanding = Math.max(0, Number(selectedLoan.outstanding || 0));
    setForm((prev) => {
      const nextAmount = String(outstanding);
      return prev.amount === nextAmount ? prev : { ...prev, amount: nextAmount };
    });
  }, [form.loan_id, loans]);

  const columns = useMemo(
    () => [
      { key: "id", label: "Receipt" },
      { key: "loan_id", label: "Loan" },
      { key: "member_name", label: "Member" },
      { key: "amount", label: "Amount", render: (row) => formatKES(row.amount) },
      { key: "payment_date", label: "Date", render: (row) => formatDate(row.payment_date) },
      { key: "method", label: "Method" },
      { key: "reference", label: "Reference", render: (row) => row.reference || "-" },
    ],
    []
  );

  async function submitRepayment(event) {
    event.preventDefault();
    setSaving(true);
    try {
      await apiFetch("/api/repayments", {
        method: "POST",
        body: JSON.stringify({
          loan_id: form.loan_id,
          amount: Number(form.amount),
          payment_date: form.payment_date,
          method: form.method,
          reference: form.reference,
          type: form.type,
        }),
      });
      pushToast("Repayment recorded successfully.", "success");
      setOpenModal(false);
      setForm((prev) => ({ ...prev, amount: "", reference: "" }));
      setPage(1);
      const refreshed = await apiFetch("/api/repayments?page=1&limit=10");
      const data = refreshed?.data || {};
      setRows(data.repayments || []);
      setPages(Number(data.pages || 1));
    } catch (err) {
      pushToast(err.message || "Could not record repayment", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <div className="row-between">
        <header className="page-head">
          <h2>Repayments Workspace</h2>
          <p>Track repayments with pagination and fast posting modal.</p>
        </header>
        <button type="button" className="primary-btn" onClick={() => setOpenModal(true)}>Record Repayment</button>
      </div>

      {error ? <p className="error-box">{error}</p> : null}

      <section className="panel stack">
        <div className="row-between">
          <h3>Repayment Ledger</h3>
          <input
            type="search"
            placeholder="Search loan/member/reference"
            value={q}
            onChange={(event) => {
              setPage(1);
              setQ(event.target.value);
            }}
          />
        </div>
        <DataTable
          columns={columns}
          rows={rows}
          rowKey="id"
          loading={loading}
          page={page}
          pages={pages}
          onPageChange={setPage}
          emptyMessage="No repayments recorded yet."
        />
      </section>

      <section className="panel stack">
        <h3>Open Loans Eligible for Repayment</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Loan</th>
                <th>Borrower</th>
                <th>Status</th>
                <th>Penalties</th>
                <th>Outstanding</th>
              </tr>
            </thead>
            <tbody>
              {loans.slice(0, 10).map((loan) => (
                <tr key={loan.id}>
                  <td>{loan.id}</td>
                  <td>{loan.member_name || loan.member_id}</td>
                  <td><span className={statusClass(loan.status)}>{loan.status}</span></td>
                  <td>{formatKES(loan.penalties)}</td>
                  <td>{formatKES(loan.outstanding)}</td>
                </tr>
              ))}
              {loans.length === 0 ? (
                <tr>
                  <td colSpan={5} className="table-empty">No active or overdue loans available.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <Modal open={openModal} title="Record Loan Repayment" onClose={() => setOpenModal(false)} maxWidth="700px">
        <form className="stack" onSubmit={submitRepayment}>
          <label>
            Loan
            <select
              value={form.loan_id}
              onChange={(event) => setForm((prev) => ({ ...prev, loan_id: event.target.value }))}
              required
            >
              <option value="">Select loan</option>
              {loans.map((loan) => (
                <option key={loan.id} value={loan.id}>
                  {loan.id} - {loan.member_name || loan.member_id} ({formatKES(loan.outstanding)} outstanding, {formatKES(loan.penalties)} penalties)
                </option>
              ))}
            </select>
          </label>

          <div className="two-col">
            <label>
              Amount (KES)
              <input
                type="number"
                min="1"
                value={form.amount}
                onChange={(event) => setForm((prev) => ({ ...prev, amount: event.target.value }))}
                required
              />
            </label>
            <label>
              Date
              <input
                type="date"
                value={form.payment_date}
                onChange={(event) => setForm((prev) => ({ ...prev, payment_date: event.target.value }))}
                required
              />
            </label>
          </div>

          <div className="two-col">
            <label>
              Method
              <select
                value={form.method}
                onChange={(event) => setForm((prev) => ({ ...prev, method: event.target.value }))}
              >
                <option value="cash">Cash</option>
                <option value="mpesa">M-Pesa</option>
                <option value="bank">Bank</option>
              </select>
            </label>
            <label>
              Type
              <select
                value={form.type}
                onChange={(event) => setForm((prev) => ({ ...prev, type: event.target.value }))}
              >
                <option value="installment">Installment</option>
                <option value="penalty">Penalty</option>
                <option value="other">Other</option>
              </select>
            </label>
          </div>

          <label>
            Reference
            <input
              type="text"
              value={form.reference}
              onChange={(event) => setForm((prev) => ({ ...prev, reference: event.target.value }))}
              placeholder="Optional"
            />
          </label>

          <button type="submit" className="primary-btn" disabled={saving}>
            {saving ? "Saving..." : "Submit Repayment"}
          </button>
        </form>
      </Modal>
    </div>
  );
}

export default RepaymentsPage;
