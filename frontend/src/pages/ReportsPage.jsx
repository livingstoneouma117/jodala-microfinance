import { useEffect, useMemo, useState } from "react";
import { apiFetch, apiFetchBlob } from "../lib/api";
import { formatDate, formatKES } from "../lib/format";
import DataTable from "../components/ui/DataTable";
import { useToast } from "../components/ui/Toast";

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

function formatMonthLabel(monthKey) {
  if (!monthKey) return "--";
  const date = new Date(`${monthKey}-01T00:00:00`);
  if (Number.isNaN(date.getTime())) return monthKey;
  return date.toLocaleDateString("en-KE", { month: "short", year: "numeric" });
}

function flattenFinancialRows(data, viewType) {
  if (viewType === "profit-loss") {
    return [
      ...(data?.income || []).map((row) => ({ ...row, section: "Income" })),
      ...(data?.expenses || []).map((row) => ({ ...row, section: "Expenses" })),
      {
        code: "NET",
        name: "Net Profit",
        section: "Result",
        balance: data?.totals?.net_profit || 0,
      },
    ];
  }

  if (viewType === "balance-sheet") {
    return [
      ...(data?.assets || []).map((row) => ({ ...row, section: "Assets" })),
      ...(data?.liabilities || []).map((row) => ({ ...row, section: "Liabilities" })),
      ...(data?.equity || []).map((row) => ({ ...row, section: "Equity" })),
    ];
  }

  return [];
}

function ReportsPage() {
  const [viewType, setViewType] = useState("account-monthly");
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [regionRows, setRegionRows] = useState([]);
  const [accounts, setAccounts] = useState([]);
  const [selectedAccount, setSelectedAccount] = useState("1000");
  const [loanMonths, setLoanMonths] = useState([]);
  const [selectedLoanMonth, setSelectedLoanMonth] = useState("");
  const [error, setError] = useState("");
  const [exportType, setExportType] = useState("account-monthly");
  const [exportFormat, setExportFormat] = useState("xlsx");
  const [exporting, setExporting] = useState(false);
  const [dividendForm, setDividendForm] = useState({ year: String(new Date().getFullYear()), surplus: "" });
  const [dividendRuns, setDividendRuns] = useState([]);
  const [dividendAllocations, setDividendAllocations] = useState([]);
  const [dividendLoading, setDividendLoading] = useState(false);

  const pushToast = useToast();

  async function loadDividends() {
    setDividendLoading(true);
    try {
      const res = await apiFetch(`/api/dividends?year=${encodeURIComponent(dividendForm.year)}`);
      setDividendRuns(res?.data?.runs || []);
      setDividendAllocations(res?.data?.allocations || []);
    } catch (err) {
      pushToast(err.message || "Failed to load dividends", "error");
    } finally {
      setDividendLoading(false);
    }
  }

  useEffect(() => {
    loadDividends();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let mounted = true;
    apiFetch("/api/accounting/chart-of-accounts")
      .then((res) => {
        if (!mounted) return;
        setAccounts(res?.data || []);
      })
      .catch(() => undefined);
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError("");

    const endpointMap = {
      "account-monthly": "/api/reports/account-monthly",
      savings: "/api/reports/savings",
      "chart-of-accounts": "/api/accounting/chart-of-accounts",
      "journal-entries": "/api/accounting/journal-entries?limit=50",
      "general-ledger": `/api/accounting/general-ledger?account_code=${encodeURIComponent(selectedAccount)}`,
      "trial-balance": "/api/accounting/trial-balance",
      "profit-loss": "/api/accounting/profit-loss",
      "balance-sheet": "/api/accounting/balance-sheet",
      "cash-flow": "/api/accounting/cash-flow",
    };
    const loansEndpoint = `/api/reports/portfolio${selectedLoanMonth ? `?month=${encodeURIComponent(selectedLoanMonth)}` : ""}`;

    apiFetch(viewType === "loans" ? loansEndpoint : endpointMap[viewType])
      .then((res) => {
        if (!mounted) return;
        const data = res?.data;
        if (viewType === "loans") {
          setRows(data?.loans || []);
          setRegionRows(data?.regions || []);
          setLoanMonths(data?.months || []);
        }
        else if (viewType === "savings") setRows(data || []);
        else if (viewType === "account-monthly") setRows(data?.months || []);
        else if (viewType === "journal-entries") setRows(data?.entries || []);
        else if (viewType === "general-ledger") setRows(data?.lines || []);
        else if (viewType === "trial-balance") setRows(data?.rows || []);
        else if (viewType === "profit-loss" || viewType === "balance-sheet") setRows(flattenFinancialRows(data, viewType));
        else if (viewType === "cash-flow") setRows(data?.months || []);
        else if (viewType === "chart-of-accounts") setRows(data || []);
      })
      .catch((err) => {
        if (!mounted) return;
        setError(err.message || "Failed to load report");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [selectedAccount, selectedLoanMonth, viewType]);

  const columns = useMemo(() => {
    if (viewType === "loans") {
      return [
        { key: "id", label: "Loan" },
        { key: "member_name", label: "Member" },
        { key: "amount", label: "Disbursed", render: (row) => formatKES(row.amount) },
        { key: "total_paid", label: "Repaid", render: (row) => formatKES(row.total_paid) },
        { key: "outstanding", label: "Outstanding", render: (row) => formatKES(row.outstanding) },
        { key: "amount_in_arrears", label: "Arrears", render: (row) => formatKES(row.amount_in_arrears) },
      ];
    }

    if (viewType === "savings") {
      return [
        { key: "id", label: "Member ID" },
        { key: "name", label: "Member" },
        { key: "status", label: "Status" },
        { key: "balance", label: "Balance", render: (row) => formatKES(row.balance) },
        { key: "total_deposits", label: "Deposits", render: (row) => formatKES(row.total_deposits) },
        { key: "total_withdrawals", label: "Withdrawals", render: (row) => formatKES(row.total_withdrawals) },
      ];
    }

    if (viewType === "chart-of-accounts") {
      return [
        { key: "code", label: "Code" },
        { key: "name", label: "Account" },
        { key: "type", label: "Type" },
      ];
    }

    if (viewType === "journal-entries") {
      return [
        { key: "id", label: "Entry" },
        { key: "entry_date", label: "Date", render: (row) => formatDate(row.entry_date) },
        { key: "source", label: "Source" },
        { key: "description", label: "Description" },
        { key: "total_debit", label: "Debit", render: (row) => formatKES(row.total_debit) },
        { key: "total_credit", label: "Credit", render: (row) => formatKES(row.total_credit) },
      ];
    }

    if (viewType === "general-ledger") {
      return [
        { key: "entry_date", label: "Date", render: (row) => formatDate(row.entry_date) },
        { key: "entry_id", label: "Entry" },
        { key: "description", label: "Description" },
        { key: "debit", label: "Debit", render: (row) => formatKES(row.debit) },
        { key: "credit", label: "Credit", render: (row) => formatKES(row.credit) },
        { key: "running_balance", label: "Running", render: (row) => formatKES(row.running_balance) },
      ];
    }

    if (viewType === "trial-balance") {
      return [
        { key: "code", label: "Code" },
        { key: "name", label: "Account" },
        { key: "type", label: "Type" },
        { key: "debit_balance", label: "Debit", render: (row) => formatKES(row.debit_balance) },
        { key: "credit_balance", label: "Credit", render: (row) => formatKES(row.credit_balance) },
      ];
    }

    if (viewType === "profit-loss" || viewType === "balance-sheet") {
      return [
        { key: "section", label: "Section" },
        { key: "code", label: "Code" },
        { key: "name", label: "Account" },
        { key: "balance", label: "Balance", render: (row) => formatKES(row.balance) },
      ];
    }

    if (viewType === "cash-flow") {
      return [
        { key: "month", label: "Month" },
        { key: "operating", label: "Operating", render: (row) => formatKES(row.operating) },
        { key: "investing", label: "Investing", render: (row) => formatKES(row.investing) },
        { key: "financing", label: "Financing", render: (row) => formatKES(row.financing) },
        { key: "net_cash_flow", label: "Net Cash Flow", render: (row) => formatKES(row.net_cash_flow) },
      ];
    }

    return [
      { key: "month", label: "Month" },
      { key: "opening_balance", label: "Opening", render: (row) => formatKES(row.opening_balance) },
      { key: "savings_collections", label: "Savings In", render: (row) => formatKES(row.savings_collections) },
      { key: "loan_repayments", label: "Repayments In", render: (row) => formatKES(row.loan_repayments) },
      { key: "loan_disbursed", label: "Disbursed Out", render: (row) => formatKES(row.loan_disbursed) },
      { key: "expenses", label: "Expenses Out", render: (row) => formatKES(row.expenses) },
      { key: "closing_balance", label: "Closing", render: (row) => formatKES(row.closing_balance) },
    ];
  }, [viewType]);

  async function calculateDividend(event) {
    event.preventDefault();
    setDividendLoading(true);
    try {
      const res = await apiFetch("/api/dividends/calculate", {
        method: "POST",
        body: JSON.stringify({ year: Number(dividendForm.year), surplus: Number(dividendForm.surplus) }),
      });
      setDividendAllocations(res?.data?.allocations || []);
      pushToast("Dividend allocation calculated.", "success");
      setDividendForm((prev) => ({ ...prev, surplus: "" }));
      await loadDividends();
    } catch (err) {
      pushToast(err.message || "Could not calculate dividends", "error");
    } finally {
      setDividendLoading(false);
    }
  }

  const dividendColumns = useMemo(() => [
    { key: "member_name", label: "Member" },
    { key: "basis_amount", label: "Savings Basis", render: (row) => formatKES(row.basis_amount) },
    { key: "dividend_amount", label: "Dividend", render: (row) => formatKES(row.dividend_amount) },
    { key: "paid", label: "Paid", render: (row) => (row.paid ? "Yes" : "No") },
  ], []);

  async function exportReport() {
    setExporting(true);
    try {
      const loanMonthQuery = exportType === "loans" && selectedLoanMonth ? `&month=${encodeURIComponent(selectedLoanMonth)}` : "";
      const res = await apiFetchBlob(`/api/reports/export/${exportType}?format=${exportFormat}${loanMonthQuery}`);
      const extension = exportFormat === "xlsx" ? "xlsx" : "csv";
      triggerDownload(res.blob, `${exportType}-report.${extension}`);
      pushToast(`Exported ${exportType} report (${exportFormat.toUpperCase()}).`, "success");
    } catch (err) {
      pushToast(err.message || "Export failed", "error");
    } finally {
      setExporting(false);
    }
  }

  const tableRowKey = viewType === "account-monthly" || viewType === "cash-flow"
    ? "month"
    : viewType === "loans" || viewType === "savings" || viewType === "journal-entries"
      ? "id"
      : viewType === "general-ledger"
        ? "entry_id"
        : "code";

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Reports & Accounting</h2>
        <p>Monthly reports, double-entry statements, ledger, and export files.</p>
      </header>

      <section className="panel stack">
        <div className="toolbar">
          <select value={viewType} onChange={(event) => setViewType(event.target.value)}>
            <option value="account-monthly">Account Monthly Report</option>
            <option value="loans">Loan Portfolio Report</option>
            <option value="savings">Savings Report</option>
            <option value="chart-of-accounts">Chart of Accounts</option>
            <option value="journal-entries">Journal Entries</option>
            <option value="general-ledger">General Ledger</option>
            <option value="trial-balance">Trial Balance</option>
            <option value="profit-loss">Profit & Loss</option>
            <option value="balance-sheet">Balance Sheet</option>
            <option value="cash-flow">Cash Flow</option>
          </select>

          {viewType === "general-ledger" ? (
            <select value={selectedAccount} onChange={(event) => setSelectedAccount(event.target.value)}>
              {accounts.map((account) => (
                <option key={account.code} value={account.code}>
                  {account.code} - {account.name}
                </option>
              ))}
            </select>
          ) : null}

          {viewType === "loans" ? (
            <select value={selectedLoanMonth} onChange={(event) => setSelectedLoanMonth(event.target.value)}>
              <option value="">All Months</option>
              {loanMonths.map((month) => (
                <option key={month.month} value={month.month}>
                  {formatMonthLabel(month.month)}
                </option>
              ))}
            </select>
          ) : null}
        </div>

        {error ? <p className="error-box">{error}</p> : null}

        {viewType === "loans" ? (
          <p className="muted">Select a month to view only the loans disbursed in that period.</p>
        ) : null}

        <DataTable
          columns={columns}
          rows={rows}
          rowKey={tableRowKey}
          loading={loading}
          emptyMessage="No report data available."
        />

        {viewType === "loans" ? (
          <section className="stack">
            <h3>Borrowing by Region</h3>
            <DataTable
              columns={[
                { key: "region", label: "Region" },
                { key: "loan_count", label: "Loans" },
                { key: "total_disbursed", label: "Total Disbursed", render: (row) => formatKES(row.total_disbursed) },
                { key: "outstanding", label: "Outstanding", render: (row) => formatKES(row.outstanding) },
              ]}
              rows={regionRows}
              rowKey="region"
              loading={loading}
              emptyMessage="No regional borrowing data yet."
            />
          </section>
        ) : null}
      </section>


      <section className="panel stack">
        <div className="row-between">
          <div>
            <h3>Dividend / Profit Sharing</h3>
            <p className="muted">Calculate year-end surplus distribution based on member savings balances.</p>
          </div>
          <button type="button" className="ghost-btn" onClick={loadDividends} disabled={dividendLoading}>Refresh</button>
        </div>
        <form className="row-form" onSubmit={calculateDividend}>
          <input type="number" min="2000" value={dividendForm.year} onChange={(event) => setDividendForm((prev) => ({ ...prev, year: event.target.value }))} placeholder="Year" required />
          <input type="number" min="1" value={dividendForm.surplus} onChange={(event) => setDividendForm((prev) => ({ ...prev, surplus: event.target.value }))} placeholder="Surplus amount" required />
          <button type="submit" className="primary-btn" disabled={dividendLoading}>{dividendLoading ? "Calculating..." : "Calculate Dividends"}</button>
        </form>
        {dividendRuns.length ? <p className="muted">Latest run: {dividendRuns[0].year} - {dividendRuns[0].status} - {formatKES(dividendRuns[0].allocated_total)}</p> : <p className="muted">No dividend runs for this year yet.</p>}
        <DataTable columns={dividendColumns} rows={dividendAllocations} rowKey="id" loading={dividendLoading} emptyMessage="No dividend allocations yet." />
      </section>

      <section className="panel stack">
        <h3>Export</h3>
        <div className="toolbar">
          <select value={exportType} onChange={(event) => setExportType(event.target.value)}>
            <option value="account-monthly">Account Monthly</option>
            <option value="loans">Loans</option>
            <option value="repayments">Repayments</option>
            <option value="savings">Savings</option>
            <option value="expenses">Expenses</option>
            <option value="members">Members</option>
            <option value="dividends">Dividends</option>
          </select>

          <select value={exportFormat} onChange={(event) => setExportFormat(event.target.value)}>
            <option value="xlsx">Excel (.xlsx)</option>
            <option value="csv">CSV (.csv)</option>
          </select>

          <button type="button" className="primary-btn" onClick={exportReport} disabled={exporting}>
            {exporting ? "Exporting..." : "Export"}
          </button>
        </div>
      </section>
    </div>
  );
}

export default ReportsPage;
