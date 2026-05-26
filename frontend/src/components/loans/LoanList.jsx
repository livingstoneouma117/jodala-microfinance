import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import { formatDate, formatKES, statusClass } from "../../lib/format";
import DataTable from "../ui/DataTable";
import Modal from "../ui/Modal";

function LoanDetails({ loanId }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiFetch(`/api/loans/${loanId}`)
      .then((res) => {
        if (!mounted) return;
        setPayload(res?.data || null);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load loan details");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [loanId]);

  if (loading) return <p className="muted">Loading loan details...</p>;
  if (error) return <p className="error-box">{error}</p>;
  if (!payload) return <p className="muted">No details available.</p>;

  const loan = payload.loan || {};
  const summary = payload.summary || {};
  const schedule = payload.schedule || [];

  return (
    <div className="stack">
      <div className="card-grid compact">
        <div className="surface-card">
          <span>Borrower</span>
          <strong>{loan.member_name || loan.member_id || "-"}</strong>
        </div>
        <div className="surface-card">
          <span>Principal</span>
          <strong>{formatKES(loan.amount)}</strong>
        </div>
        <div className="surface-card">
          <span>Total Repaid</span>
          <strong>{formatKES(loan.total_paid)}</strong>
        </div>
        <div className="surface-card">
          <span>Outstanding</span>
          <strong>{formatKES(summary.outstanding)}</strong>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>#</th>
              <th>Due Date</th>
              <th>Repayment</th>
              <th>Balance</th>
              <th>Paid</th>
            </tr>
          </thead>
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
            {schedule.length === 0 ? (
              <tr>
                <td colSpan={5} className="table-empty">No repayment schedule available yet.</td>
              </tr>
            ) : null}
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

  useEffect(() => {
    let mounted = true;
    setLoading(true);

    const query = new URLSearchParams({
      status,
      q,
      page: String(page),
      limit: "10",
    });

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

    return () => {
      mounted = false;
    };
  }, [page, q, refreshToken, status]);

  const columns = useMemo(
    () => [
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
          <button type="button" className="ghost-btn" onClick={() => setSelectedLoanId(row.id)}>
            View
          </button>
        ),
      },
    ],
    []
  );

  return (
    <section className="panel stack">
      <div className="row-between">
        <h3>Loan Portfolio</h3>
        <span className="muted">All statuses visible</span>
      </div>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search loan, borrower, purpose"
          value={q}
          onChange={(event) => {
            setPage(1);
            setQ(event.target.value);
          }}
        />
        <select
          value={status}
          onChange={(event) => {
            setPage(1);
            setStatus(event.target.value);
          }}
        >
          <option value="all">All Status</option>
          <option value="pending">Pending</option>
          <option value="approved">Approved</option>
          <option value="active">Active</option>
          <option value="overdue">Overdue</option>
          <option value="completed">Completed</option>
          <option value="rejected">Rejected</option>
        </select>
      </div>

      {error ? <p className="error-box">{error}</p> : null}

      <DataTable
        columns={columns}
        rows={rows}
        rowKey="id"
        loading={loading}
        page={page}
        pages={pages}
        onPageChange={setPage}
        emptyMessage="No loans found for this filter."
      />

      <Modal
        open={Boolean(selectedLoanId)}
        title={`Loan Details ${selectedLoanId}`}
        onClose={() => setSelectedLoanId("")}
        maxWidth="980px"
      >
        {selectedLoanId ? <LoanDetails loanId={selectedLoanId} /> : null}
      </Modal>
    </section>
  );
}

export default LoanList;
