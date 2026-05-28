import { NavLink } from "react-router-dom";
import { canAccess, roleLabel } from "../../lib/access";

const NAV_ITEMS = [
  { to: "/dashboard", label: "Dashboard" },
  { to: "/loans", label: "Loans" },
  { to: "/members", label: "Members" },
  { to: "/savings", label: "Savings" },
  { to: "/repayments", label: "Repayments" },
  { to: "/reports", label: "Reports" },
  { to: "/settings", label: "Settings" },
  { to: "/users", label: "Users & Roles", roles: ["admin"] },
];

function Shell({ children, onLogout, user }) {
  const visibleItems = NAV_ITEMS.filter((item) => canAccess(user?.role, item.roles));

  return (
    <div className="app-shell">
      <aside className="side-nav">
        <div className="brand-block">
          <div className="brand-mark">JM</div>
          <div>
            <h1>Jodala v3</h1>
            <p>Modern Workspace</p>
          </div>
        </div>

        {user ? (
          <div className="signed-user">
            <span>{user.name}</span>
            <strong className={`role-pill role-${user.role}`}>{roleLabel(user.role)}</strong>
          </div>
        ) : null}

        <nav>
          {visibleItems.map((item) => (
            <NavLink key={item.to} to={item.to} className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <button type="button" className="ghost-btn" onClick={onLogout}>Logout</button>
      </aside>

      <main className="content-area">{children}</main>
    </div>
  );
}

export default Shell;
