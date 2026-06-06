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
  monthly_collection_rate: 0,
  monthly_outstanding_portfolio: 0,
  monthly_portfolio_at_risk: 0,
  monthly_profit: 0,
};

const EMPTY_MONTHLY = {
  month: "",
  opening_balance: 0,
  savings_collections: 0,
  loan_repayments: 0,
  loan_disbursed: 0,
  expenses: 0,
  inflow: 0,
  outflow: 0,
  net: 0,
  closing_balance: 0,
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

function formatBuildStamp(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString("en-KE", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZoneName: "short",
  });
}

function Dashboard() {
  const [stats, setStats] = useState(EMPTY_STATS);
  const [buildInfo, setBuildInfo] = useState({ build_version: "", generated_at: "" });
  const [monthlySummary, setMonthlySummary] = useState(EMPTY_MONTHLY);
  const [cashFlowForecast, setCashFlowForecast] = useState({ month: "", projected_inflow: 0, projected_outflow: 0, projected_net: 0 });
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
        setBuildInfo({
          build_version: data.build_version || "",
          generated_at: data.generated_at || "",
        });
        setStats(data.stats || EMPTY_STATS);
        setMonthlySummary(data.monthly_summary || EMPTY_MONTHLY);
        setCashFlowForecast(data.cash_flow_forecast || { month: "", projected_inflow: 0, projected_outflow: 0, projected_net: 0 });
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
        <div className="row-between">
          <div>
            <h2>Portfolio Snapshot</h2>
            <p>Live portfolio, risk, and cashflow metrics with monthly trend charts.</p>
          </div>
          <div className="build-stamp muted">
            <strong>{buildInfo.build_version ? `Build ${buildInfo.build_version}` : "Build"}</strong>
            {buildInfo.generated_at ? <span>{formatBuildStamp(buildInfo.generated_at)}</span> : <span>Waiting for build info</span>}
          </div>
        </div>
      </header>

      {error ? <p className="error-box">{error}</p> : null}

      <div className="card-grid">
        <StatCard label="Month-End Balance" value={formatKES(monthlySummary.closing_balance)} tone="primary" subtitle={monthlySummary.month ? `Closing balance for ${monthlySummary.month}` : "Current month closing balance"} />
        <StatCard label="Active Loans" value={String(stats.active_loans || 0)} tone="ok" subtitle="Currently running" />
        <StatCard label="Overdue Loans" value={String(stats.overdue_loans || 0)} tone="danger" subtitle="Need follow-up" />
        <StatCard label="Total Members" value={String(stats.total_members || 0)} subtitle="Registered members" />
        <StatCard label="Savings This Month" value={formatKES(monthlySummary.savings_collections)} tone="primary" subtitle="Collected this month" />
        <StatCard label="Repayments This Month" value={formatKES(monthlySummary.loan_repayments)} tone="ok" subtitle="Repaid this month" />
        <StatCard label="Disbursed This Month" value={formatKES(monthlySummary.loan_disbursed)} tone="warn" subtitle="Loans issued this month" />
        <StatCard
          label="Outstanding Portfolio"
          value={formatKES(stats.monthly_outstanding_portfolio)}
          tone="warn"
          subtitle={`Monthly disbursed ${formatKES(monthlySummary.loan_disbursed)} · total outstanding balance after issue`}
        />
        <StatCard label="Expenses This Month" value={formatKES(monthlySummary.expenses)} tone="danger" subtitle="Spent this month" />
        <StatCard label="Net Movement" value={formatKES(monthlySummary.net)} tone={Number(monthlySummary.net || 0) >= 0 ? "ok" : "danger"} subtitle="This month inflow minus outflow" />
        <StatCard label="Monthly Collection Rate" value={`${Number(stats.monthly_collection_rate || 0).toFixed(1)}%`} tone="ok" subtitle="Repaid / disbursed this month" />
        <StatCard label="Monthly PAR" value={`${Number(stats.monthly_portfolio_at_risk || 0).toFixed(1)}%`} tone="danger" subtitle="Arrears pressure this month" />
        <StatCard label="Monthly Profit" value={formatKES(stats.monthly_profit)} tone={Number(stats.monthly_profit || 0) >= 0 ? "ok" : "danger"} subtitle="Loan repayments minus expenses" />
        <StatCard label="Due Today" value={formatKES(stats.due_today)} tone="warn" subtitle="Today schedule" />
        <StatCard label="Portfolio At Risk" value={`${Number(stats.portfolio_at_risk || 0).toFixed(1)}%`} tone="danger" subtitle="All-time arrears pressure" />
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

      <section className="panel stack">
        <div className="row-between">
          <h3>Cash Flow Forecast</h3>
          <span className="muted">{cashFlowForecast.month || "Next month"}</span>
        </div>
        <div className="card-grid compact">
          <StatCard label="Projected Inflow" value={formatKES(cashFlowForecast.projected_inflow)} tone="ok" />
          <StatCard label="Projected Outflow" value={formatKES(cashFlowForecast.projected_outflow)} tone="warn" />
          <StatCard label="Projected Net" value={formatKES(cashFlowForecast.projected_net)} tone={Number(cashFlowForecast.projected_net || 0) >= 0 ? "ok" : "danger"} />
        </div>
      </section>
    </section>
  );
}

export default Dashboard;
