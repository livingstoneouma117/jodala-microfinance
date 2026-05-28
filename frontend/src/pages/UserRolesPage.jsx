import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";
import { formatDate } from "../lib/format";
import DataTable from "../components/ui/DataTable";
import { useToast } from "../components/ui/Toast";

const ROLES = [
  { value: "admin", label: "Admin" },
  { value: "officer", label: "Loan Officer" },
  { value: "accountant", label: "Accountant" },
  { value: "cashier", label: "Cashier" },
];

function roleLabel(role) {
  return ROLES.find((item) => item.value === role)?.label || role || "-";
}

function UserRolesPage() {
  const [users, setUsers] = useState([]);
  const [draftRoles, setDraftRoles] = useState({});
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [error, setError] = useState("");
  const pushToast = useToast();

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/users");
      const list = res?.data || [];
      setUsers(list);
      setDraftRoles(Object.fromEntries(list.map((user) => [user.id, user.role])));
    } catch (err) {
      setError(err.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  async function assignRole(user) {
    const nextRole = draftRoles[user.id];
    if (!nextRole || nextRole === user.role) {
      return;
    }

    setSavingId(user.id);
    try {
      const res = await apiFetch(`/api/users/${user.id}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role: nextRole }),
      });
      const updated = res?.data;
      setUsers((prev) => prev.map((item) => (item.id === user.id ? { ...item, role: updated?.role || nextRole } : item)));
      pushToast(`${user.name} is now ${roleLabel(nextRole)}.`, "success");
    } catch (err) {
      pushToast(err.message || "Could not assign role", "error");
      setDraftRoles((prev) => ({ ...prev, [user.id]: user.role }));
    } finally {
      setSavingId(null);
    }
  }

  const columns = useMemo(
    () => [
      {
        key: "name",
        label: "User",
        render: (row) => (
          <>
            <strong>{row.name}</strong>
            <p className="muted-inline">{row.username || row.email}</p>
          </>
        ),
      },
      { key: "email", label: "Email" },
      {
        key: "role",
        label: "Current Role",
        render: (row) => <span className={`role-pill role-${row.role}`}>{roleLabel(row.role)}</span>,
      },
      {
        key: "assign",
        label: "Assign Role",
        render: (row) => (
          <div className="table-actions">
            <select
              value={draftRoles[row.id] || row.role}
              onChange={(event) => setDraftRoles((prev) => ({ ...prev, [row.id]: event.target.value }))}
            >
              {ROLES.map((role) => (
                <option key={role.value} value={role.value}>{role.label}</option>
              ))}
            </select>
            <button
              type="button"
              className="primary-btn"
              disabled={savingId === row.id || (draftRoles[row.id] || row.role) === row.role}
              onClick={() => assignRole(row)}
            >
              {savingId === row.id ? "Saving..." : "Assign"}
            </button>
          </div>
        ),
      },
      { key: "active", label: "Status", render: (row) => (row.active ? "Active" : "Inactive") },
      { key: "created_at", label: "Created", render: (row) => formatDate(row.created_at) },
    ],
    [draftRoles, savingId]
  );

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Users & Roles</h2>
        <p>Assign staff roles for admin, loan officer, accountant, and cashier access.</p>
      </header>

      {error ? <p className="error-box">{error}</p> : null}

      <section className="panel stack">
        <div className="row-between">
          <h3>Role Assignment</h3>
          <button type="button" className="ghost-btn" onClick={loadUsers} disabled={loading}>
            Refresh
          </button>
        </div>

        <DataTable
          columns={columns}
          rows={users}
          rowKey="id"
          loading={loading}
          emptyMessage="No users found."
        />
      </section>
    </div>
  );
}

export default UserRolesPage;
