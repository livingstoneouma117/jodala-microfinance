import { useEffect, useMemo, useState } from "react";
import { apiFetch, apiFetchBlob } from "../lib/api";
import { formatDate, formatKES, statusClass } from "../lib/format";
import DataTable from "../components/ui/DataTable";
import Modal from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";

const TODAY = new Date().toISOString().slice(0, 10);

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

function SavingsPage() {
  const [members, setMembers] = useState([]);
  const [membersLoading, setMembersLoading] = useState(true);
  const [transactions, setTransactions] = useState([]);
  const [txLoading, setTxLoading] = useState(true);
  const [txPage, setTxPage] = useState(1);
  const [txPages, setTxPages] = useState(1);
  const [txQuery, setTxQuery] = useState("");
  const [error, setError] = useState("");

  const [openModal, setOpenModal] = useState(false);
  const [openBulkModal, setOpenBulkModal] = useState(false);
  const [actionType, setActionType] = useState("deposit");
  const [form, setForm] = useState({ member_id: "", amount: "", category: "voluntary", date: TODAY, reference: "" });
  const [bulkForm, setBulkForm] = useState({ category: "mandatory", date: TODAY, reference: "" });
  const [bulkRows, setBulkRows] = useState([]);
  const [saving, setSaving] = useState(false);
  const pushToast = useToast();

  async function loadSavingsData() {
    const [membersRes, txRes] = await Promise.all([
      apiFetch("/api/savings"),
      apiFetch(`/api/savings/transactions?page=${txPage}&limit=10&q=${encodeURIComponent(txQuery)}`),
    ]);
    const list = membersRes?.data || [];
    setMembers(list);
    if (!form.member_id && list.length > 0) setForm((prev) => ({ ...prev, member_id: list[0].id }));
    const txData = txRes?.data || {};
    setTransactions(txData.transactions || []);
    setTxPages(Number(txData.pages || 1));
  }

  useEffect(() => {
    let mounted = true;
    setMembersLoading(true);
    apiFetch("/api/savings")
      .then((res) => {
        if (!mounted) return;
        const list = res?.data || [];
        setMembers(list);
        if (!form.member_id && list.length > 0) setForm((prev) => ({ ...prev, member_id: list[0].id }));
      })
      .catch((err) => { if (mounted) setError(err.message || "Failed to load savings accounts"); })
      .finally(() => { if (mounted) setMembersLoading(false); });
    return () => { mounted = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    let mounted = true;
    setTxLoading(true);
    const query = new URLSearchParams({ page: String(txPage), limit: "10", q: txQuery });
    apiFetch(`/api/savings/transactions?${query.toString()}`)
      .then((res) => {
        if (!mounted) return;
        const data = res?.data || {};
        setTransactions(data.transactions || []);
        setTxPages(Number(data.pages || 1));
      })
      .catch((err) => { if (mounted) setError(err.message || "Failed to load savings transactions"); })
      .finally(() => { if (mounted) setTxLoading(false); });
    return () => { mounted = false; };
  }, [txPage, txQuery]);

  function openBulk() {
    setBulkRows(members.map((member) => ({ member_id: member.id, name: member.name, amount: "" })));
    setBulkForm({ category: "mandatory", date: TODAY, reference: `MEETING-${TODAY}` });
    setOpenBulkModal(true);
  }

  async function downloadPassbook(member, format) {
    try {
      const res = await apiFetchBlob(`/api/members/${member.id}/passbook?format=${format}`);
      triggerDownload(res.blob, `passbook-${member.id}.${format}`);
      pushToast(`Passbook ${format.toUpperCase()} downloaded.`, "success");
    } catch (err) {
      pushToast(err.message || "Could not download passbook", "error");
    }
  }

  const memberColumns = useMemo(() => [
    { key: "name", label: "Member", render: (row) => <><strong>{row.name}</strong><p className="muted-inline">{row.id}</p></> },
    { key: "phone", label: "Phone", render: (row) => row.phone || "-" },
    { key: "status", label: "Status", render: (row) => <span className={statusClass(row.status)}>{row.status}</span> },
    { key: "balance", label: "Balance", render: (row) => formatKES(row.balance) },
    { key: "txn_count", label: "Transactions" },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="table-actions">
          <button type="button" className="ghost-btn" onClick={() => { setActionType("deposit"); setForm((prev) => ({ ...prev, member_id: row.id })); setOpenModal(true); }}>Deposit</button>
          <button type="button" className="ghost-btn" onClick={() => { setActionType("withdraw"); setForm((prev) => ({ ...prev, member_id: row.id })); setOpenModal(true); }}>Withdraw</button>
          <button type="button" className="ghost-btn" onClick={() => downloadPassbook(row, "pdf")}>Passbook PDF</button>
          <button type="button" className="ghost-btn" onClick={() => downloadPassbook(row, "xlsx")}>Passbook Excel</button>
        </div>
      ),
    },
  ], []);

  const txColumns = useMemo(() => [
    { key: "id", label: "Txn ID" },
    { key: "member_name", label: "Member" },
    { key: "type", label: "Type" },
    { key: "amount", label: "Amount", render: (row) => formatKES(row.type === "withdrawal" ? -Number(row.amount || 0) : row.amount) },
    { key: "txn_date", label: "Date", render: (row) => formatDate(row.txn_date) },
    { key: "reference", label: "Reference" },
    { key: "balance_after", label: "Balance After", render: (row) => formatKES(row.balance_after) },
  ], []);

  async function submitTransaction(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const endpoint = actionType === "withdraw" ? "/api/savings/withdraw" : "/api/savings/deposit";
      await apiFetch(endpoint, { method: "POST", body: JSON.stringify({ member_id: form.member_id, amount: Number(form.amount), category: form.category, date: form.date, reference: form.reference }) });
      pushToast(`${actionType === "withdraw" ? "Withdrawal" : "Deposit"} recorded.`, "success");
      setForm((prev) => ({ ...prev, amount: "", reference: "" }));
      setOpenModal(false);
      await loadSavingsData();
    } catch (err) {
      pushToast(err.message || "Could not record transaction", "error");
    } finally {
      setSaving(false);
    }
  }

  async function submitBulkDeposit(event) {
    event.preventDefault();
    const items = bulkRows.filter((row) => Number(row.amount || 0) > 0).map((row) => ({ member_id: row.member_id, amount: Number(row.amount) }));
    if (!items.length) {
      pushToast("Enter at least one deposit amount.", "error");
      return;
    }
    setSaving(true);
    try {
      const res = await apiFetch("/api/savings/bulk-deposit", { method: "POST", body: JSON.stringify({ ...bulkForm, items }) });
      pushToast(`Bulk deposit recorded: ${res?.data?.count || items.length} members.`, "success");
      setOpenBulkModal(false);
      await loadSavingsData();
    } catch (err) {
      pushToast(err.message || "Could not record bulk deposit", "error");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="stack">
      <div className="row-between">
        <header className="page-head"><h2>Savings Workspace</h2><p>Manage deposits, withdrawals, bulk monthly collections, and member passbooks.</p></header>
        <div className="table-actions">
          <button type="button" className="ghost-btn" onClick={openBulk}>Bulk Meeting Deposit</button>
          <button type="button" className="primary-btn" onClick={() => { setActionType("deposit"); setOpenModal(true); }}>Record Transaction</button>
        </div>
      </div>

      {error ? <p className="error-box">{error}</p> : null}
      <section className="panel stack"><h3>Member Savings Accounts</h3><DataTable columns={memberColumns} rows={members} rowKey="id" loading={membersLoading} emptyMessage="No savings accounts yet." /></section>
      <section className="panel stack">
        <div className="row-between"><h3>Transactions</h3><input type="search" placeholder="Search member or reference" value={txQuery} onChange={(event) => { setTxPage(1); setTxQuery(event.target.value); }} /></div>
        <DataTable columns={txColumns} rows={transactions} rowKey="id" loading={txLoading} page={txPage} pages={txPages} onPageChange={setTxPage} emptyMessage="No savings transactions found." />
      </section>

      <Modal open={openModal} title={actionType === "withdraw" ? "Record Withdrawal" : "Record Deposit"} onClose={() => setOpenModal(false)} maxWidth="680px">
        <form className="stack" onSubmit={submitTransaction}>
          <label>Member<select value={form.member_id} onChange={(event) => setForm((prev) => ({ ...prev, member_id: event.target.value }))} required><option value="">Select member</option>{members.map((member) => <option key={member.id} value={member.id}>{member.name} ({member.id})</option>)}</select></label>
          <div className="two-col"><label>Amount (KES)<input type="number" min="1" value={form.amount} onChange={(event) => setForm((prev) => ({ ...prev, amount: event.target.value }))} required /></label><label>Category<select value={form.category} onChange={(event) => setForm((prev) => ({ ...prev, category: event.target.value }))}><option value="voluntary">Voluntary</option><option value="mandatory">Mandatory</option></select></label></div>
          <div className="two-col"><label>Date<input type="date" value={form.date} onChange={(event) => setForm((prev) => ({ ...prev, date: event.target.value }))} /></label><label>Reference<input type="text" value={form.reference} onChange={(event) => setForm((prev) => ({ ...prev, reference: event.target.value }))} placeholder="Optional" /></label></div>
          <button type="submit" className="primary-btn" disabled={saving}>{saving ? "Saving..." : actionType === "withdraw" ? "Record Withdrawal" : "Record Deposit"}</button>
        </form>
      </Modal>

      <Modal open={openBulkModal} title="Bulk Savings Deposit" onClose={() => setOpenBulkModal(false)} maxWidth="960px">
        <form className="stack" onSubmit={submitBulkDeposit}>
          <div className="two-col"><label>Date<input type="date" value={bulkForm.date} onChange={(event) => setBulkForm((prev) => ({ ...prev, date: event.target.value }))} /></label><label>Reference<input value={bulkForm.reference} onChange={(event) => setBulkForm((prev) => ({ ...prev, reference: event.target.value }))} /></label></div>
          <label>Category<select value={bulkForm.category} onChange={(event) => setBulkForm((prev) => ({ ...prev, category: event.target.value }))}><option value="mandatory">Mandatory</option><option value="voluntary">Voluntary</option></select></label>
          <div className="table-wrap"><table><thead><tr><th>Member</th><th>Amount Paid</th></tr></thead><tbody>{bulkRows.map((row, index) => <tr key={row.member_id}><td><strong>{row.name}</strong><p className="muted-inline">{row.member_id}</p></td><td><input type="number" min="0" value={row.amount} onChange={(event) => setBulkRows((prev) => prev.map((item, idx) => idx === index ? { ...item, amount: event.target.value } : item))} placeholder="0" /></td></tr>)}</tbody></table></div>
          <button type="submit" className="primary-btn" disabled={saving}>{saving ? "Saving..." : "Save Bulk Deposit"}</button>
        </form>
      </Modal>
    </div>
  );
}

export default SavingsPage;
