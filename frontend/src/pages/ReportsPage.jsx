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

function ReportsPage() {
  const [viewType, setViewType] = useState("account-monthly");
  const [loading, setLoading] = useState(true);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  const [exportType, setExportType] = useState("account-monthly");
  const [exportFormat, setExportFormat] = useState("xlsx");
  const [exporting, setExporting] = useState(false);

  const pushToast = useToast();

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError("");

    const endpoint = viewType === "loans"
      ? "/api/reports/portfolio"
      : viewType === "savings"
        ? "/api/reports/savings"
        : "/api/reports/account-monthly";

    apiFetch(endpoint)
      .then((res) => {
        if (!mounted) return;
        const data = res?.data;
        if (viewType === "loans") {
          setRows(data?.loans || []);
        } else if (viewType === "savings") {
          setRows(data || []);
        } else {
          setRows(data?.months || []);
        }
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
  }, [viewType]);

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

  async function exportReport() {
    setExporting(true);
    try {
      const res = await apiFetchBlob(`/api/reports/export/${exportType}?format=${exportFormat}`);
      const extension = exportFormat === "xlsx" ? "xlsx" : "csv";
      triggerDownload(res.blob, `${exportType}-report.${extension}`);
      pushToast(`Exported ${exportType} report (${exportFormat.toUpperCase()}).`, "success");
    } catch (err) {
      pushToast(err.message || "Export failed", "error");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Reports & Analytics</h2>
        <p>View monthly account reports and export CSV/XLSX files for accounting.</p>
      </header>

      <section className="panel stack">
        <div className="toolbar">
          <select value={viewType} onChange={(event) => setViewType(event.target.value)}>
            <option value="account-monthly">Account Monthly Report</option>
            <option value="loans">Loan Portfolio Report</option>
            <option value="savings">Savings Report</option>
          </select>
        </div>

        {error ? <p className="error-box">{error}</p> : null}

        <DataTable
          columns={columns}
          rows={rows}
          rowKey={viewType === "account-monthly" ? "month" : "id"}
          loading={loading}
          emptyMessage="No report data available."
        />
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
