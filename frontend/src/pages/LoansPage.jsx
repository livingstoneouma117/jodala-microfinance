import { useState } from "react";
import LoanForm from "../components/loans/LoanForm";
import LoanList from "../components/loans/LoanList";

function LoansPage() {
  const [refreshToken, setRefreshToken] = useState(0);

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Loan Workspace</h2>
        <p>Reusable LoanForm and LoanList components replacing monolithic UI logic.</p>
      </header>

      <div className="layout-two">
        <LoanForm onSaved={() => setRefreshToken((prev) => prev + 1)} />
        <LoanList refreshToken={refreshToken} />
      </div>
    </div>
  );
}

export default LoansPage;
