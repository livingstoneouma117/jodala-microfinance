import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { formatKES, statusClass } from "../../lib/format";

function LoanList({ refreshToken }) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/loans?status=all&limit=100")
      .then((res) => {
        if (!mounted) return;
        setRows(res?.data?.loans || []);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load loans");
      });
    return () => {
      mounted = false;
    };
  }, [refreshToken]);

  return (
    <section className="panel stack">
      <h3>Loan Portfolio</h3>
      {error ? <p className="error-box">{error}</p> : null}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Loan</th>
              <th>Borrower</th>
              <th>Status</th>
              <th>Principal</th>
              <th>Repaid</th>
              <th>Outstanding</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((loan) => (
              <tr key={loan.id}>
                <td>{loan.id}</td>
                <td>{loan.member_name || loan.member_id}</td>
                <td><span className={statusClass(loan.status)}>{loan.status}</span></td>
                <td>{formatKES(loan.amount)}</td>
                <td>{formatKES(loan.total_paid)}</td>
                <td>{formatKES(loan.outstanding)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default LoanList;
