import { NavLink } from "react-router-dom";

function Shell({ children, onLogout }) {
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

        <nav>
          <NavLink to="/dashboard" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>Dashboard</NavLink>
          <NavLink to="/loans" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>Loans</NavLink>
          <NavLink to="/members" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>Members</NavLink>
          <NavLink to="/savings" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>Savings</NavLink>
          <NavLink to="/repayments" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>Repayments</NavLink>
          <NavLink to="/reports" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>Reports</NavLink>
          <NavLink to="/settings" className={({ isActive }) => isActive ? "nav-link active" : "nav-link"}>Settings</NavLink>
        </nav>

        <button type="button" className="ghost-btn" onClick={onLogout}>Logout</button>
      </aside>

      <main className="content-area">{children}</main>
    </div>
  );
}

export default Shell;
