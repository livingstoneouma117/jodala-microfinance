import { useState } from "react";
import LoanForm from "../components/loans/LoanForm";
import LoanList from "../components/loans/LoanList";
import LoanProducts from "../components/loans/LoanProducts";
import Modal from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";
import { canAccess } from "../lib/access";

function LoansPage({ session }) {
  const [refreshToken, setRefreshToken] = useState(0);
  const [openLoanForm, setOpenLoanForm] = useState(false);
  const pushToast = useToast();
  const user = session?.user;
  const canCreateLoan = canAccess(user, ["admin", "officer"], ["loans.create"]);
  const canViewLoanProducts = canAccess(user, ["admin"], ["loan-products"]);

  return (
    <div className="stack">
      <div className="row-between">
        <header className="page-head">
          <h2>Loan Workspace</h2>
          <p>Loan list now uses shared DataTable + LoanDetails modal.</p>
        </header>
        {canCreateLoan ? (
          <button type="button" className="primary-btn" onClick={() => setOpenLoanForm(true)}>
            New Loan Application
          </button>
        ) : null}
      </div>

      {canViewLoanProducts ? <LoanProducts user={user} /> : null}

      <LoanList refreshToken={refreshToken} user={user} />

      <Modal open={openLoanForm} title="Create Loan Application" onClose={() => setOpenLoanForm(false)} maxWidth="760px">
        <LoanForm
          asPanel={false}
          onSaved={() => {
            setOpenLoanForm(false);
            setRefreshToken((prev) => prev + 1);
            pushToast("Loan application submitted.", "success");
          }}
        />
      </Modal>
    </div>
  );
}

export default LoansPage;
