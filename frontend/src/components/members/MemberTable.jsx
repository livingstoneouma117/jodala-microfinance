import { useEffect, useState } from "react";
import { apiFetch } from "../../lib/api";
import { formatKES, statusClass } from "../../lib/format";

function MemberTable() {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/members?status=all&type=member&limit=200")
      .then((res) => {
        if (!mounted) return;
        setRows(res?.data?.members || []);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load members");
      });
    return () => {
      mounted = false;
    };
  }, []);

  return (
    <section className="panel stack">
      <h3>Member Table</h3>
      <p className="muted">Reusable component baseline for member management and filters.</p>
      {error ? <p className="error-box">{error}</p> : null}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Member</th>
              <th>Phone</th>
              <th>Status</th>
              <th>Savings</th>
              <th>Joined</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((member) => (
              <tr key={member.id}>
                <td>
                  <strong>{member.name}</strong>
                  <p className="muted-inline">{member.id}</p>
                </td>
                <td>{member.phone || "-"}</td>
                <td><span className={statusClass(member.status)}>{member.status}</span></td>
                <td>{formatKES(member.savings)}</td>
                <td>{member.joined_date || "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default MemberTable;
