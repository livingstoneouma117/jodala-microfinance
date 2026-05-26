import { Navigate, Route, Routes } from "react-router-dom";
import { useMemo, useState } from "react";
import Shell from "./components/layout/Shell";
import LoginPage from "./pages/LoginPage";
import DashboardPage from "./pages/DashboardPage";
import LoansPage from "./pages/LoansPage";
import MembersPage from "./pages/MembersPage";
import { getToken, setToken } from "./lib/api";

function App() {
  const [token, setSessionToken] = useState(getToken());
  const session = useMemo(() => ({ token, setSessionToken }), [token]);

  if (!token) {
    return <LoginPage onLogin={(next) => { setToken(next); setSessionToken(next); }} />;
  }

  return (
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
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </Shell>
  );
}

export default App;
