import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { formatKES } from "../../lib/format";

const EMPTY = {
  active_loans: 0,
  overdue_loans: 0,
  total_members: 0,
  account_current_balance: 0,
  total_savings: 0,
  total_repaid: 0,
};

function Dashboard() {
  const [stats, setStats] = useState(EMPTY);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/dashboard")
      .then((res) => {
        if (!mounted) return;
        setStats(res?.data?.stats || EMPTY);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Could not load dashboard");
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="stack">
      <header className="page-head">
        <h2>Portfolio Snapshot</h2>
        <p>Live metrics from the core lending account.</p>
      </header>

      {error ? <p className="error-box">{error}</p> : null}

      <div className="card-grid">
        <article className="metric-card">
          <span>Account Balance</span>
          <strong>{formatKES(stats.account_current_balance)}</strong>
        </article>
        <article className="metric-card">
          <span>Active Loans</span>
          <strong>{stats.active_loans}</strong>
        </article>
        <article className="metric-card">
          <span>Overdue Loans</span>
          <strong>{stats.overdue_loans}</strong>
        </article>
        <article className="metric-card">
          <span>Total Members</span>
          <strong>{stats.total_members}</strong>
        </article>
        <article className="metric-card">
          <span>Total Savings</span>
          <strong>{formatKES(stats.total_savings)}</strong>
        </article>
        <article className="metric-card">
          <span>Total Repaid</span>
          <strong>{formatKES(stats.total_repaid)}</strong>
        </article>
      </div>
    </section>
  );
}

export default Dashboard;
