import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import { formatDate, formatKES, statusClass } from "../../lib/format";
import StatCard from "../ui/StatCard";
import DataTable from "../ui/DataTable";

const EMPTY_STATS = {
  active_loans: 0,
  overdue_loans: 0,
  total_members: 0,
  account_current_balance: 0,
  total_savings: 0,
  total_repaid: 0,
  due_today: 0,
  collection_rate: 0,
  portfolio_at_risk: 0,
};

function MonthlyRepaymentsChart({ points }) {
  if (!points.length) return <p className="muted">No monthly repayment data yet.</p>;

  const maxValue = Math.max(...points.map((item) => Number(item.total || 0)), 1);

  return (
    <div className="bars-grid">
      {points.map((item) => {
        const amount = Number(item.total || 0);
        const height = Math.max(8, Math.round((amount / maxValue) * 120));
        return (
          <div className="bar-item" key={item.month}>
            <div className="bar-fill" style={{ height }} title={`${item.month}: ${formatKES(amount)}`} />
            <small>{item.month?.slice(5) || "--"}</small>
          </div>
        );
      })}
    </div>
  );
}

function LoanStatusChart({ items }) {
  const clean = items
    .map((item, index) => ({
      id: `${item.status || "unknown"}-${index}`,
      label: String(item.status || "unknown"),
      count: Number(item.count || 0),
    }))
    .filter((item) => item.count > 0);

  const total = clean.reduce((sum, item) => sum + item.count, 0);
  if (!total) return <p className="muted">No loan status data available.</p>;

  const colors = ["#0f766e", "#1d4ed8", "#b45309", "#b91c1c", "#166534", "#6d28d9"];
  const radius = 42;
  const circumference = 2 * Math.PI * radius;
  let progress = 0;

  return (
    <div className="donut-wrap">
      <svg viewBox="0 0 120 120" className="donut-chart" aria-label="Loan status breakdown">
        <circle cx="60" cy="60" r={radius} fill="none" stroke="#e5edf7" strokeWidth="14" />
        {clean.map((item, index) => {
          const portion = item.count / total;
          const dash = portion * circumference;
          const offset = -progress * circumference;
          progress += portion;
          return (
            <circle
              key={item.id}
              cx="60"
              cy="60"
              r={radius}
              fill="none"
              stroke={colors[index % colors.length]}
              strokeWidth="14"
              strokeDasharray={`${dash} ${circumference - dash}`}
              strokeDashoffset={offset}
              transform="rotate(-90 60 60)"
            />
          );
        })}
        <text x="60" y="55" textAnchor="middle" className="donut-total">{total}</text>
        <text x="60" y="70" textAnchor="middle" className="donut-label">Loans</text>
      </svg>
      <div className="donut-legend">
        {clean.map((item, index) => (
          <div className="legend-row" key={item.id}>
            <span className="legend-dot" style={{ backgroundColor: colors[index % colors.length] }} />
            <span>{item.label}</span>
            <strong>{item.count}</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

function Dashboard() {
  const [stats, setStats] = useState(EMPTY_STATS);
  const [monthly, setMonthly] = useState([]);
  const [breakdown, setBreakdown] = useState([]);
  const [recentLoans, setRecentLoans] = useState([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiFetch("/api/dashboard")
      .then((res) => {
        if (!mounted) return;
        const data = res?.data || {};
        setStats(data.stats || EMPTY_STATS);
        setMonthly(data.monthly_repayments || []);
        setBreakdown(data.loan_breakdown || []);
        setRecentLoans(data.recent_loans || []);
        setError("");
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Could not load dashboard");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, []);

  const recentColumns = useMemo(
    () => [
      { key: "id", label: "Loan" },
      { key: "member_name", label: "Member" },
      { key: "status", label: "Status", render: (row) => <span className={statusClass(row.status)}>{row.status}</span> },
      { key: "amount", label: "Amount", render: (row) => formatKES(row.amount) },
      { key: "applied_date", label: "Applied", render: (row) => formatDate(row.applied_date) },
    ],
    []
  );

  return (
    <section className="stack">
      <header className="page-head">
        <h2>Portfolio Snapshot</h2>
        <p>Live portfolio, risk, and cashflow metrics with monthly trend charts.</p>
      </header>

      {error ? <p className="error-box">{error}</p> : null}

      <div className="card-grid">
        <StatCard label="Account Balance" value={formatKES(stats.account_current_balance)} tone="primary" subtitle="Main account" />
        <StatCard label="Active Loans" value={String(stats.active_loans || 0)} tone="ok" subtitle="Currently running" />
        <StatCard label="Overdue Loans" value={String(stats.overdue_loans || 0)} tone="danger" subtitle="Need follow-up" />
        <StatCard label="Total Members" value={String(stats.total_members || 0)} subtitle="Registered members" />
        <StatCard label="Total Savings" value={formatKES(stats.total_savings)} tone="primary" subtitle="Member savings" />
        <StatCard label="Total Repaid" value={formatKES(stats.total_repaid)} tone="ok" subtitle="Loan collections" />
        <StatCard label="Due Today" value={formatKES(stats.due_today)} tone="warn" subtitle="Today schedule" />
        <StatCard label="Collection Rate" value={`${Number(stats.collection_rate || 0).toFixed(1)}%`} tone="ok" subtitle="Repaid / Disbursed" />
        <StatCard label="Portfolio At Risk" value={`${Number(stats.portfolio_at_risk || 0).toFixed(1)}%`} tone="danger" subtitle="Arrears pressure" />
      </div>

      <div className="layout-two-wide">
        <section className="panel stack">
          <h3>Monthly Repayment Trend</h3>
          {loading ? <p className="muted">Loading chart...</p> : <MonthlyRepaymentsChart points={monthly} />}
        </section>

        <section className="panel stack">
          <h3>Loan Status Breakdown</h3>
          {loading ? <p className="muted">Loading chart...</p> : <LoanStatusChart items={breakdown} />}
        </section>
      </div>

      <section className="panel stack">
        <h3>Recent Loans</h3>
        <DataTable columns={recentColumns} rows={recentLoans} rowKey="id" loading={loading} emptyMessage="No recent loans found." />
      </section>
    </section>
  );
}

export default Dashboard;
