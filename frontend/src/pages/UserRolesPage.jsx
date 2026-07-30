import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";
import { AVAILABLE_PERMISSIONS, ROLE_PERMISSIONS, ROLES, permissionLabel, roleLabel } from "../lib/access";
import { formatDate } from "../lib/format";
import DataTable from "../components/ui/DataTable";
import Modal from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";

function UserRolesPage() {
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [savingId, setSavingId] = useState(null);
  const [editingUser, setEditingUser] = useState(null);
  const [draftAccess, setDraftAccess] = useState({
    role: "cashier",
    permissions: [],
    active: true,
  });
  const [error, setError] = useState("");

  const pushToast = useToast();

  async function loadUsers() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/users");
      setUsers(res?.data || []);
    } catch (err) {
      setError(err.message || "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadUsers();
  }, []);

  function openAccessEditor(user) {
    setEditingUser(user);
    setDraftAccess({
      role: user.role || "cashier",
      permissions: Array.isArray(user.permissions) ? [...user.permissions] : [],
      active: Boolean(user.active),
    });
  }

  function closeAccessEditor() {
    setEditingUser(null);
    setDraftAccess({ role: "cashier", permissions: [], active: true });
  }

  function togglePermission(permission) {
    setDraftAccess((prev) => {
      const permissions = new Set(prev.permissions || []);
      if (permissions.has(permission)) {
        permissions.delete(permission);
      } else {
        permissions.add(permission);
      }
      return { ...prev, permissions: [...permissions] };
    });
  }

  async function saveAccess(event) {
    event.preventDefault();
    if (!editingUser) return;

    setSavingId(editingUser.id);
    try {
      const res = await apiFetch(`/api/users/${editingUser.id}`, {
        method: "PUT",
        body: JSON.stringify({
          name: editingUser.name,
          username: editingUser.username,
          email: editingUser.email,
          role: draftAccess.role,
          permissions: draftAccess.permissions,
          active: draftAccess.active,
        }),
      });

      const updated = res?.data || {};
      setUsers((prev) => prev.map((user) => (user.id === editingUser.id ? { ...user, ...updated } : user)));
      pushToast(`${editingUser.name} access updated.`, "success");
      closeAccessEditor();
    } catch (err) {
      pushToast(err.message || "Could not update access", "error");
    } finally {
      setSavingId(null);
    }
  }

  async function assignRole(user, role) {
    if (!user || role === user.role) return;
    setSavingId(user.id);
    try {
      const res = await apiFetch(`/api/users/${user.id}/role`, {
        method: "PATCH",
        body: JSON.stringify({ role }),
      });
      const updated = res?.data || {};
      setUsers((prev) => prev.map((item) => (item.id === user.id ? { ...item, ...updated } : item)));
      pushToast(`${user.name} is now ${roleLabel(role)}.`, "success");
    } catch (err) {
      pushToast(err.message || "Could not assign role", "error");
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
      {
        key: "role",
        label: "Role",
        render: (row) => (
          <div className="role-assigner">
            <span className={`role-pill role-${row.role}`}>{roleLabel(row.role)}</span>
            <select
              aria-label={`Assign role for ${row.name}`}
              value={row.role || "cashier"}
              disabled={savingId === row.id}
              onChange={(event) => assignRole(row, event.target.value)}
            >
              {ROLES.map((role) => (
                <option key={role.value} value={role.value}>
                  {role.label}
                </option>
              ))}
            </select>
          </div>
        ),
      },
      {
        key: "permissions",
        label: "Extra Access",
        render: (row) =>
          Array.isArray(row.permissions) && row.permissions.length > 0 ? (
            <div className="permission-summary">
              {row.permissions.map((permission) => (
                <span key={permission} className="permission-chip">
                  {permissionLabel(permission)}
                </span>
              ))}
            </div>
          ) : (
            <span className="muted">No custom permissions</span>
          ),
      },
      { key: "active", label: "Status", render: (row) => (row.active ? "Active" : "Inactive") },
      { key: "created_at", label: "Created", render: (row) => formatDate(row.created_at) },
      {
        key: "actions",
        label: "Actions",
        render: (row) => (
          <button type="button" className="ghost-btn" onClick={() => openAccessEditor(row)}>
            Edit Access
          </button>
        ),
      },
    ],
    [savingId]
  );

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Users & Roles</h2>
        <p>Admins can assign a base role and add extra capabilities on top of it.</p>
      </header>

      <section className="panel stack">
        <div className="row-between">
          <h3>Role Baselines</h3>
          <span className="muted">Roles stay the default access layer. Permissions add extra modules when needed.</span>
        </div>
        <div className="role-grid">
          {ROLES.map((role) => (
            <article className="role-card" key={role.value}>
              <span className={`role-pill role-${role.value}`}>{role.label}</span>
              <ul>
                {(ROLE_PERMISSIONS[role.value] || []).map((permission) => (
                  <li key={permission}>{permission}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </section>

      <section className="panel stack">
        <div className="row-between">
          <h3>Permission Catalog</h3>
          <span className="muted">Use these permissions to extend a user beyond their role.</span>
        </div>
        <div className="permission-grid">
          {AVAILABLE_PERMISSIONS.map((permission) => (
            <article className="permission-card" key={permission.value}>
              <strong>{permission.label}</strong>
              <p>{permission.description}</p>
            </article>
          ))}
        </div>
      </section>

      {error ? <p className="error-box">{error}</p> : null}

      <section className="panel stack">
        <div className="row-between">
          <h3>Users</h3>
          <button type="button" className="ghost-btn" onClick={loadUsers} disabled={loading}>
            Refresh
          </button>
        </div>

        <DataTable columns={columns} rows={users} rowKey="id" loading={loading} emptyMessage="No users found." />
      </section>

      <Modal
        open={Boolean(editingUser)}
        title={editingUser ? `Edit Access: ${editingUser.name}` : "Edit Access"}
        onClose={closeAccessEditor}
        maxWidth="760px"
      >
        <form className="stack" onSubmit={saveAccess}>
          <div className="two-col">
            <label>
              Role
              <select
                value={draftAccess.role}
                onChange={(event) => setDraftAccess((prev) => ({ ...prev, role: event.target.value }))}
              >
                {ROLES.map((role) => (
                  <option key={role.value} value={role.value}>
                    {role.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="checkbox-field">
              Active
              <span className="checkbox-row">
                <input
                  type="checkbox"
                  checked={draftAccess.active}
                  onChange={(event) => setDraftAccess((prev) => ({ ...prev, active: event.target.checked }))}
                />
                <span>{draftAccess.active ? "Enabled" : "Disabled"}</span>
              </span>
            </label>
          </div>

          <div className="stack">
            <div className="row-between">
              <h4>Extra Permissions</h4>
              <span className="muted">Checked items add access beyond the selected role.</span>
            </div>
            <div className="permission-grid">
              {AVAILABLE_PERMISSIONS.map((permission) => {
                const checked = draftAccess.permissions.includes(permission.value);
                return (
                  <label className="permission-select" key={permission.value}>
                    <span className="checkbox-row">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => togglePermission(permission.value)}
                      />
                      <span>
                        <strong>{permission.label}</strong>
                        <small>{permission.description}</small>
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          </div>

          <button type="submit" className="primary-btn" disabled={savingId === editingUser?.id}>
            {savingId === editingUser?.id ? "Saving..." : "Save Access"}
          </button>
        </form>
      </Modal>
    </div>
  );
}

export default UserRolesPage;
