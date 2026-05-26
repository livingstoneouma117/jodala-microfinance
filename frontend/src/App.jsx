import { Navigate, Route, Routes } from "react-router-dom";
import { useMemo, useState } from "react";
import Shell from "./components/layout/Shell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LoansPage from "./pages/LoansPage";
import MembersPage from "./pages/MembersPage";
import SavingsPage from "./pages/SavingsPage";
import RepaymentsPage from "./pages/RepaymentsPage";
import ReportsPage from "./pages/ReportsPage";
import SettingsPage from "./pages/SettingsPage";
import { getToken, setToken } from "./lib/api";
import { ToastProvider } from "./components/ui/Toast";

function App() {
  const [token, setSessionToken] = useState(getToken());
  const session = useMemo(() => ({ token, setSessionToken }), [token]);

  return (
    <ToastProvider>
      {!token ? (
        <LoginPage onLogin={(next) => { setToken(next); setSessionToken(next); }} />
      ) : (
        <Shell
          onLogout={() => {
            setToken("");
            setSessionToken("");
          }}
        >
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<DashboardPage session={session} />} />
            <Route path="/loans" element={<LoansPage session={session} />} />
            <Route path="/members" element={<MembersPage session={session} />} />
            <Route path="/savings" element={<SavingsPage session={session} />} />
            <Route path="/repayments" element={<RepaymentsPage session={session} />} />
            <Route path="/reports" element={<ReportsPage session={session} />} />
            <Route path="/settings" element={<SettingsPage session={session} />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Shell>
      )}
    </ToastProvider>
  );
}

export default App;
