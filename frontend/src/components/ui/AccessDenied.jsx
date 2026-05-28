import { permissionLabel, roleLabel } from "../../lib/access";

function AccessDenied({ user, allowedRoles = [], allowedPermissions = [] }) {
  const requiredRoles = allowedRoles.length ? allowedRoles.map(roleLabel).join(", ") : "";
  const requiredPermissions = allowedPermissions.length ? allowedPermissions.map(permissionLabel).join(", ") : "";
  const required = [requiredRoles, requiredPermissions].filter(Boolean).join(" or ") || "authorized staff";

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Access Denied</h2>
        <p>Your current role or permissions do not allow this action.</p>
      </header>

      <section className="panel access-panel">
        <div>
          <span className="eyebrow">Signed in as</span>
          <h3>{user?.name || "Current user"}</h3>
          <p className="muted">Current role: {roleLabel(user?.role)}</p>
        </div>
        <div>
          <span className="eyebrow">Required access</span>
          <p>{required}</p>
        </div>
      </section>
    </div>
  );
}

export default AccessDenied;
