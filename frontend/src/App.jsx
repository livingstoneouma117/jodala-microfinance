import { Navigate, Route, Routes } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import Shell from "./components/layout/Shell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LoansPage from "./pages/LoansPage";
import MembersPage from "./pages/MembersPage";
import SavingsPage from "./pages/SavingsPage";
import RepaymentsPage from "./pages/RepaymentsPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import UserRolesPage from "./pages/UserRolesPage";
import AccessDenied from "./components/ui/AccessDenied";
import { canAccess } from "./lib/access";
import { apiFetch, getToken, setToken } from "./lib/api";
import { ToastProvider } from "./components/ui/Toast";

function LoadingShell() {
  return (
    <div className="login-wrap">
      <div className="login-card">
        <h1>Jodala Microfinance v3</h1>
        <p>Checking your access...</p>
      </div>
    </div>
  );
}

function RequireRole({ user, roles, children }) {
  if (!canAccess(user?.role, roles)) {
    return <AccessDenied user={user} allowedRoles={roles} />;
  }
  return children;
}

function App() {
  const [token, setSessionToken] = useState(getToken());
  const [user, setUser] = useState(null);
  const [sessionLoading, setSessionLoading] = useState(Boolean(token));
  const session = useMemo(() => ({ token, setSessionToken, user, role: user?.role || "" }), [token, user]);

  useEffect(() => {
    let mounted = true;

    if (!token) {
      setUser(null);
      setSessionLoading(false);
      return () => {
        mounted = false;
      };
    }

    setSessionLoading(true);
    apiFetch("/api/auth/me")
      .then((res) => {
        if (!mounted) return;
        setUser(res?.data || null);
      })
      .catch(() => {
        if (!mounted) return;
        setToken("");
        setSessionToken("");
        setUser(null);
      })
      .finally(() => {
        if (mounted) setSessionLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [token]);

  function handleLogout() {
    setToken("");
    setSessionToken("");
    setUser(null);
  }

  return (
    <ToastProvider>
      {!token ? (
        <LoginPage onLogin={(next) => { setToken(next); setSessionToken(next); }} />
      ) : sessionLoading ? (
        <LoadingShell />
      ) : (
        <Shell user={user} onLogout={handleLogout}>
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage session={session} />} />
            <Route path="/loans" element={<LoansPage session={session} />} />
            <Route path="/members" element={<MembersPage session={session} />} />
            <Route path="/savings" element={<SavingsPage session={session} />} />
            <Route path="/repayments" element={<RepaymentsPage session={session} />} />
            <Route path="/reports" element={<ReportsPage session={session} />} />
            <Route path="/settings" element={<SettingsPage session={session} />} />
            <Route
              path="/users"
              element={(
                <RequireRole user={user} roles={["admin"]}>
                  <UserRolesPage session={session} />
                </RequireRole>
              )}
            />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Shell>
      )}
    </ToastProvider>
  );
}

export default App;
