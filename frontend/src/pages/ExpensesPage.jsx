import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../lib/api";
import { canAccess } from "../lib/access";
import { formatDate, formatKES, statusClass } from "../lib/format";
import DataTable from "../components/ui/DataTable";
import Modal from "../components/ui/Modal";
import { useToast } from "../components/ui/Toast";

const TODAY = new Date().toISOString().slice(0, 10);

function blankTransactionForm(accountId = "") {
  return {
    account_id: accountId,
    amount: "",
    expense_date: TODAY,
    reference: "",
    payee: "",
    notes: "",
  };
}

function buildTransactionQuery(page, filters) {
  return new URLSearchParams({
    page: String(page),
    limit: "15",
    q: filters.q,
    account_id: filters.account_id,
    date_from: filters.date_from,
    date_to: filters.date_to,
  }).toString();
}

function ExpensesPage({ session }) {
  const currentUser = session?.user || session || null;
  const canCreate = canAccess(currentUser, ["admin", "accountant"], ["expenses.create"]);
  const canEdit = canAccess(currentUser, ["admin", "accountant"], ["expenses.edit"]);
  const canDelete = canAccess(currentUser, ["admin", "accountant"], ["expenses.delete"]);

  const [accounts, setAccounts] = useState([]);
  const [accountsLoading, setAccountsLoading] = useState(true);
  const [includeInactive, setIncludeInactive] = useState(false);
  const [accountModalOpen, setAccountModalOpen] = useState(false);
  const [accountSaving, setAccountSaving] = useState(false);
  const [accountForm, setAccountForm] = useState({
    name: "",
    code: "",
    description: "",
  });

  const [transactions, setTransactions] = useState([]);
  const [txLoading, setTxLoading] = useState(true);
  const [txPage, setTxPage] = useState(1);
  const [txPages, setTxPages] = useState(1);
  const [txFilters, setTxFilters] = useState({
    q: "",
    account_id: "",
    date_from: "",
    date_to: "",
  });
  const [txModalOpen, setTxModalOpen] = useState(false);
  const [txSaving, setTxSaving] = useState(false);
  const [editingTx, setEditingTx] = useState(null);
  const [txForm, setTxForm] = useState(blankTransactionForm());

  const pushToast = useToast();

  const defaultAccountId = useMemo(() => {
    const active = accounts.find((account) => Number(account.active) === 1);
    return active ? String(active.id) : accounts[0]?.id ? String(accounts[0].id) : "";
  }, [accounts]);

  useEffect(() => {
    let mounted = true;
    setAccountsLoading(true);

    apiFetch(`/api/expenses/accounts${includeInactive ? "?include_inactive=true" : ""}`)
      .then((res) => {
        if (!mounted) return;
        const list = res?.data || [];
        setAccounts(list);
        setTxForm((prev) => {
          if (prev.account_id || list.length === 0) return prev;
          return { ...prev, account_id: String(list[0].id) };
        });
      })
      .catch((err) => {
        if (!mounted) return;
        pushToast(err.message || "Failed to load expense accounts", "error");
      })
      .finally(() => {
        if (mounted) setAccountsLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [includeInactive, pushToast]);

  useEffect(() => {
    let mounted = true;
    setTxLoading(true);

    apiFetch(`/api/expenses/transactions?${buildTransactionQuery(txPage, txFilters)}`)
      .then((res) => {
        if (!mounted) return;
        const data = res?.data || {};
        setTransactions(data.transactions || []);
        setTxPages(Number(data.pages || 1));
      })
      .catch((err) => {
        if (!mounted) return;
        pushToast(err.message || "Failed to load expense transactions", "error");
      })
      .finally(() => {
        if (mounted) setTxLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [txPage, txFilters, pushToast]);

  async function refreshWorkspace() {
    const [accountsRes, txRes] = await Promise.all([
      apiFetch(`/api/expenses/accounts${includeInactive ? "?include_inactive=true" : ""}`),
      apiFetch(`/api/expenses/transactions?${buildTransactionQuery(txPage, txFilters)}`),
    ]);
    setAccounts(accountsRes?.data || []);
    const data = txRes?.data || {};
    setTransactions(data.transactions || []);
    setTxPages(Number(data.pages || 1));
  }

  function openNewTransaction(accountId = defaultAccountId) {
    setEditingTx(null);
    setTxForm(blankTransactionForm(accountId));
    setTxModalOpen(true);
  }

  function openEditTransaction(row) {
    setEditingTx(row);
    setTxForm({
      account_id: row.account_id ? String(row.account_id) : "",
      amount: row.amount == null ? "" : String(row.amount),
      expense_date: String(row.expense_date || TODAY).slice(0, 10),
      reference: row.reference || "",
      payee: row.payee || "",
      notes: row.notes || "",
    });
    setTxModalOpen(true);
  }

  function closeTransactionModal() {
    setTxModalOpen(false);
    setEditingTx(null);
    setTxForm(blankTransactionForm(defaultAccountId));
  }

  async function deleteTransaction(row) {
    if (!window.confirm(`Delete expense ${row.id}?`)) return;
    try {
      await apiFetch(`/api/expenses/transactions/${row.id}`, { method: "DELETE" });
      pushToast("Expense deleted.", "success");
      await refreshWorkspace();
    } catch (err) {
      pushToast(err.message || "Could not delete expense", "error");
    }
  }

  const accountColumns = useMemo(
    () => [
      { key: "code", label: "Code", render: (row) => row.code || "-" },
      {
        key: "name",
        label: "Account",
        render: (row) => (
          <>
            <strong>{row.name}</strong>
            <p className="muted-inline">{row.description || "No description"}</p>
          </>
        ),
      },
      {
        key: "active",
        label: "Status",
        render: (row) => <span className={statusClass(row.active ? "active" : "inactive")}>{row.active ? "Active" : "Inactive"}</span>,
      },
      { key: "created_by_name", label: "Created By", render: (row) => row.created_by_name || "-" },
      {
        key: "actions",
        label: "Actions",
        render: (row) => (
          <div className="table-actions expense-row-actions">
            {canCreate ? (
              <button type="button" className="ghost-btn" onClick={() => openNewTransaction(String(row.id))}>
                Use
              </button>
            ) : null}
            {canEdit ? (
              <button
                type="button"
                className="ghost-btn"
                onClick={async () => {
                  try {
                    await apiFetch(`/api/expenses/accounts/${row.id}/status`, {
                      method: "PATCH",
                      body: JSON.stringify({ active: !row.active }),
                    });
                    pushToast(`Account ${row.active ? "deactivated" : "activated"}.`, "success");
                    const res = await apiFetch(`/api/expenses/accounts${includeInactive ? "?include_inactive=true" : ""}`);
                    setAccounts(res?.data || []);
                  } catch (err) {
                    pushToast(err.message || "Could not update account", "error");
                  }
                }}
              >
                {row.active ? "Deactivate" : "Activate"}
              </button>
            ) : null}
            {!canCreate && !canEdit ? <span className="muted-inline">View only</span> : null}
          </div>
        ),
      },
    ],
    [canCreate, canEdit, includeInactive, pushToast]
  );

  const txColumns = useMemo(
    () => [
      { key: "id", label: "Txn ID" },
      { key: "account_name", label: "Account" },
      { key: "amount", label: "Amount", render: (row) => formatKES(row.amount) },
      { key: "expense_date", label: "Date", render: (row) => formatDate(row.expense_date) },
      { key: "payee", label: "Payee", render: (row) => row.payee || "-" },
      { key: "reference", label: "Reference", render: (row) => row.reference || "-" },
      { key: "recorded_by_name", label: "Recorded By", render: (row) => row.recorded_by_name || "-" },
      {
        key: "actions",
        label: "Actions",
        render: (row) => (
          <div className="table-actions expense-row-actions">
            {canEdit ? (
              <button type="button" className="ghost-btn" onClick={() => openEditTransaction(row)}>
                Edit
              </button>
            ) : null}
            {canDelete ? (
              <button type="button" className="ghost-btn danger-soft" onClick={() => deleteTransaction(row)}>
                Delete
              </button>
            ) : null}
            {!canEdit && !canDelete ? <span className="muted-inline">View only</span> : null}
          </div>
        ),
      },
    ],
    [canDelete, canEdit, includeInactive, pushToast, txFilters, txPage]
  );

  async function submitAccount(event) {
    event.preventDefault();
    setAccountSaving(true);
    try {
      await apiFetch("/api/expenses/accounts", {
        method: "POST",
        body: JSON.stringify(accountForm),
      });
      pushToast("Expense account created.", "success");
      setAccountForm({ name: "", code: "", description: "" });
      setAccountModalOpen(false);
      const res = await apiFetch(`/api/expenses/accounts${includeInactive ? "?include_inactive=true" : ""}`);
      const list = res?.data || [];
      setAccounts(list);
      if (!txForm.account_id && list.length > 0) {
        setTxForm((prev) => ({ ...prev, account_id: String(list[0].id) }));
      }
    } catch (err) {
      pushToast(err.message || "Could not create account", "error");
    } finally {
      setAccountSaving(false);
    }
  }

  async function submitTransaction(event) {
    event.preventDefault();
    setTxSaving(true);
    try {
      const payload = {
        account_id: txForm.account_id,
        amount: Number(txForm.amount),
        expense_date: txForm.expense_date,
        reference: txForm.reference,
        payee: txForm.payee,
        notes: txForm.notes,
      };
      await apiFetch(
        editingTx ? `/api/expenses/transactions/${editingTx.id}` : "/api/expenses/transactions",
        {
          method: editingTx ? "PUT" : "POST",
          body: JSON.stringify(payload),
        }
      );
      pushToast(editingTx ? "Expense updated." : "Expense recorded.", "success");
      closeTransactionModal();
      await refreshWorkspace();
    } catch (err) {
      pushToast(err.message || (editingTx ? "Could not update expense" : "Could not record expense"), "error");
    } finally {
      setTxSaving(false);
    }
  }

  return (
    <div className="stack expenses-page">
      <div className="row-between expenses-header">
        <header className="page-head">
          <h2>Expenses Workspace</h2>
          <p>Track expense accounts and the transactions that flow through them.</p>
        </header>
        <div className="table-actions expense-page-actions">
          {canCreate ? (
            <button type="button" className="ghost-btn" onClick={() => setAccountModalOpen(true)}>
              New Account
            </button>
          ) : null}
          {canCreate ? (
            <button type="button" className="primary-btn" onClick={() => openNewTransaction()}>
              Record Expense
            </button>
          ) : null}
        </div>
      </div>

      <section className="panel stack expense-panel">
        <div className="row-between">
          <h3>Expense Accounts</h3>
          <label className="inline-toggle">
            <input type="checkbox" checked={includeInactive} onChange={(event) => setIncludeInactive(event.target.checked)} />
            Include inactive
          </label>
        </div>
        <DataTable
          columns={accountColumns}
          rows={accounts}
          rowKey="id"
          loading={accountsLoading}
          emptyMessage="No expense accounts yet."
        />
      </section>

      <section className="panel stack expense-panel">
        <div className="row-between expense-table-head">
          <h3>Transactions</h3>
          <div className="table-actions expense-filter-bar">
            <input
              type="search"
              placeholder="Search reference, payee, notes"
              value={txFilters.q}
              onChange={(event) => {
                setTxPage(1);
                setTxFilters((prev) => ({ ...prev, q: event.target.value }));
              }}
            />
            <select
              value={txFilters.account_id}
              onChange={(event) => {
                setTxPage(1);
                setTxFilters((prev) => ({ ...prev, account_id: event.target.value }));
              }}
            >
              <option value="">All accounts</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
            <input
              type="date"
              value={txFilters.date_from}
              onChange={(event) => {
                setTxPage(1);
                setTxFilters((prev) => ({ ...prev, date_from: event.target.value }));
              }}
            />
            <input
              type="date"
              value={txFilters.date_to}
              onChange={(event) => {
                setTxPage(1);
                setTxFilters((prev) => ({ ...prev, date_to: event.target.value }));
              }}
            />
          </div>
        </div>
        <DataTable
          columns={txColumns}
          rows={transactions}
          rowKey="id"
          loading={txLoading}
          page={txPage}
          pages={txPages}
          onPageChange={setTxPage}
          emptyMessage="No expense transactions found."
        />
      </section>

      <Modal open={accountModalOpen} title="New Expense Account" onClose={() => setAccountModalOpen(false)} maxWidth="560px">
        <form className="stack expense-modal-form" onSubmit={submitAccount}>
          <div className="two-col">
            <label>
              Account Name
              <input
                type="text"
                value={accountForm.name}
                onChange={(event) => setAccountForm((prev) => ({ ...prev, name: event.target.value }))}
                required
              />
            </label>
            <label>
              Code
              <input
                type="text"
                value={accountForm.code}
                onChange={(event) => setAccountForm((prev) => ({ ...prev, code: event.target.value }))}
                placeholder="Optional"
              />
            </label>
          </div>
          <label>
            Description
            <textarea
              rows="3"
              value={accountForm.description}
              onChange={(event) => setAccountForm((prev) => ({ ...prev, description: event.target.value }))}
              placeholder="Optional"
            />
          </label>
          <button type="submit" className="primary-btn" disabled={accountSaving}>
            {accountSaving ? "Saving..." : "Create Account"}
          </button>
        </form>
      </Modal>

      <Modal
        open={txModalOpen}
        title={editingTx ? `Edit Expense ${editingTx.id}` : "Record Expense"}
        onClose={closeTransactionModal}
        maxWidth="560px"
      >
        <form className="stack expense-modal-form" onSubmit={submitTransaction}>
          <label>
            Expense Account
            <select
              value={txForm.account_id}
              onChange={(event) => setTxForm((prev) => ({ ...prev, account_id: event.target.value }))}
              required
            >
              <option value="">Select account</option>
              {accounts.map((account) => (
                <option key={account.id} value={account.id} disabled={!account.active && String(account.id) !== txForm.account_id}>
                  {account.name} {account.code ? `(${account.code})` : ""}
                </option>
              ))}
            </select>
          </label>

          <div className="two-col">
            <label>
              Amount (KES)
              <input
                type="number"
                min="1"
                step="0.01"
                value={txForm.amount}
                onChange={(event) => setTxForm((prev) => ({ ...prev, amount: event.target.value }))}
                required
              />
            </label>
            <label>
              Date
              <input
                type="date"
                value={txForm.expense_date}
                onChange={(event) => setTxForm((prev) => ({ ...prev, expense_date: event.target.value }))}
              />
            </label>
          </div>

          <div className="two-col">
            <label>
              Payee
              <input
                type="text"
                value={txForm.payee}
                onChange={(event) => setTxForm((prev) => ({ ...prev, payee: event.target.value }))}
                placeholder="Optional"
              />
            </label>
            <label>
              Reference
              <input
                type="text"
                value={txForm.reference}
                onChange={(event) => setTxForm((prev) => ({ ...prev, reference: event.target.value }))}
                placeholder="Optional"
              />
            </label>
          </div>

          <label>
            Notes
            <textarea
              rows="3"
              value={txForm.notes}
              onChange={(event) => setTxForm((prev) => ({ ...prev, notes: event.target.value }))}
              placeholder="Optional"
            />
          </label>

          <div className="modal-actions-inline">
            <button type="button" className="ghost-btn" onClick={closeTransactionModal} disabled={txSaving}>
              Cancel
            </button>
            <button type="submit" className="primary-btn" disabled={txSaving}>
              {txSaving ? "Saving..." : editingTx ? "Save Changes" : "Record Expense"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}

export default ExpensesPage;