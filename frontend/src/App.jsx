import { Navigate, Route, Routes } from "react-router-dom";
import { useEffect, useMemo, useState } from "react";
import Shell from "./components/layout/Shell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LoansPage from "./pages/LoansPage";
import MembersPage from "./pages/MembersPage";
import SavingsPage from "./pages/SavingsPage";
import ExpensesPage from "./pages/ExpensesPage";
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

function RequireAccess({ user, roles = [], permissions = [], children }) {
  if (!canAccess(user, roles, permissions)) {
    return <AccessDenied user={user} allowedRoles={roles} allowedPermissions={permissions} />;
  }
  return children;
}

function App() {
  const [token, setSessionToken] = useState(getToken());
  const [user, setUser] = useState(null);
  const [sessionLoading, setSessionLoading] = useState(Boolean(token));
  const session = useMemo(
    () => ({ token, setSessionToken, user, role: user?.role || "", permissions: user?.permissions || [] }),
    [token, user]
  );

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
            <Route
              path="/dashboard"
              element={(
                <RequireAccess user={user}>
                  <DashboardPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/loans"
              element={(
                <RequireAccess user={user} roles={["admin", "officer", "accountant"]} permissions={["loans"]}>
                  <LoansPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/members"
              element={(
                <RequireAccess user={user} roles={["admin", "officer"]} permissions={["members"]}>
                  <MembersPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/savings"
              element={(
                <RequireAccess user={user} roles={["admin", "officer", "cashier", "accountant"]} permissions={["savings"]}>
                  <SavingsPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/expenses"
              element={(
                <RequireAccess user={user} roles={["admin", "accountant"]} permissions={["expenses"]}>
                  <ExpensesPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/repayments"
              element={(
                <RequireAccess user={user} roles={["admin", "officer", "cashier"]} permissions={["repayments"]}>
                  <RepaymentsPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/reports"
              element={(
                <RequireAccess user={user} roles={["admin", "accountant"]} permissions={["reports"]}>
                  <ReportsPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/settings"
              element={(
                <RequireAccess user={user} roles={["admin", "accountant"]} permissions={["settings"]}>
                  <SettingsPage session={session} />
                </RequireAccess>
              )}
            />
            <Route
              path="/users"
              element={(
                <RequireAccess user={user} roles={["admin"]}>
                  <UserRolesPage session={session} />
                </RequireAccess>
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
