import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import { formatDate, formatKES, statusClass } from "../../lib/format";
import DataTable from "../ui/DataTable";
import Modal from "../ui/Modal";

function MemberProfile({ memberId }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [payload, setPayload] = useState(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiFetch(`/api/members/${memberId}`)
      .then((res) => {
        if (!mounted) return;
        setPayload(res?.data || null);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load member profile");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [memberId]);

  if (loading) return <p className="muted">Loading member profile...</p>;
  if (error) return <p className="error-box">{error}</p>;
  if (!payload) return <p className="muted">No member details available.</p>;

  const member = payload.member || {};
  const loans = payload.loans || [];
  const savings = payload.savings_transactions || [];
  const repayments = payload.repayments || [];

  return (
    <div className="stack">
      <div className="card-grid compact">
        <div className="surface-card">
          <span>Name</span>
          <strong>{member.name || "-"}</strong>
        </div>
        <div className="surface-card">
          <span>Status</span>
          <strong>{member.status || "-"}</strong>
        </div>
        <div className="surface-card">
          <span>Phone</span>
          <strong>{member.phone || "-"}</strong>
        </div>
        <div className="surface-card">
          <span>Savings</span>
          <strong>{formatKES(member.savings)}</strong>
        </div>
      </div>

      <div className="layout-two-wide">
        <section className="panel stack">
          <h4>Loans</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Loan</th>
                  <th>Status</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {loans.slice(0, 8).map((loan) => (
                  <tr key={loan.id}>
                    <td>{loan.id}</td>
                    <td><span className={statusClass(loan.status)}>{loan.status}</span></td>
                    <td>{formatKES(loan.amount)}</td>
                  </tr>
                ))}
                {loans.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="table-empty">No loans found.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel stack">
          <h4>Activity Timeline</h4>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Activity</th>
                  <th>Amount</th>
                </tr>
              </thead>
              <tbody>
                {[...savings.map((row) => ({
                  date: row.txn_date,
                  type: `Savings ${row.type}`,
                  amount: row.type === "withdrawal" ? -Number(row.amount || 0) : Number(row.amount || 0),
                  id: row.id,
                })),
                ...repayments.map((row) => ({
                  date: row.payment_date,
                  type: "Loan repayment",
                  amount: Number(row.amount || 0),
                  id: row.id,
                }))]
                  .sort((a, b) => String(b.date || "").localeCompare(String(a.date || "")))
                  .slice(0, 15)
                  .map((item) => (
                    <tr key={item.id}>
                      <td>{formatDate(item.date)}</td>
                      <td>{item.type}</td>
                      <td>{formatKES(item.amount)}</td>
                    </tr>
                  ))}
                {savings.length + repayments.length === 0 ? (
                  <tr>
                    <td colSpan={3} className="table-empty">No activity available.</td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </div>
  );
}

function MemberTable() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [status, setStatus] = useState("all");
  const [q, setQ] = useState("");
  const [selectedMemberId, setSelectedMemberId] = useState("");

  useEffect(() => {
    let mounted = true;
    setLoading(true);

    const query = new URLSearchParams({
      status,
      type: "member",
      page: String(page),
      limit: "10",
      q,
    });

    apiFetch(`/api/members?${query.toString()}`)
      .then((res) => {
        if (!mounted) return;
        const data = res?.data || {};
        setRows(data.members || []);
        setPages(Number(data.pages || 1));
        setError("");
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load members");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [page, q, status]);

  const columns = useMemo(
    () => [
      { key: "name", label: "Member", render: (row) => <><strong>{row.name}</strong><p className="muted-inline">{row.id}</p></> },
      { key: "phone", label: "Phone", render: (row) => row.phone || "-" },
      { key: "status", label: "Status", render: (row) => <span className={statusClass(row.status)}>{row.status}</span> },
      { key: "savings", label: "Savings", render: (row) => formatKES(row.savings) },
      { key: "joined_date", label: "Joined", render: (row) => formatDate(row.joined_date) },
      {
        key: "actions",
        label: "Actions",
        render: (row) => (
          <button type="button" className="ghost-btn" onClick={() => setSelectedMemberId(row.id)}>
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
        <h3>Members</h3>
        <span className="muted">Member profile + timeline modal</span>
      </div>

      <div className="toolbar">
        <input
          type="search"
          placeholder="Search member by name, ID, phone"
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
          <option value="active">Active</option>
          <option value="inactive">Inactive</option>
          <option value="suspended">Suspended</option>
          <option value="blacklisted">Blacklisted</option>
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
        emptyMessage="No members found."
      />

      <Modal
        open={Boolean(selectedMemberId)}
        title={`Member Profile ${selectedMemberId}`}
        onClose={() => setSelectedMemberId("")}
        maxWidth="1100px"
      >
        {selectedMemberId ? <MemberProfile memberId={selectedMemberId} /> : null}
      </Modal>
    </section>
  );
}

export default MemberTable;
