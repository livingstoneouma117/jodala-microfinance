import { useEffect, useMemo, useState } from "react";
import { apiFetch } from "../../lib/api";
import { formatKES } from "../../lib/format";
import DataTable from "../ui/DataTable";
import Modal from "../ui/Modal";
import { useToast } from "../ui/Toast";

const EMPTY_PRODUCT = {
  name: "",
  min_amount: "0",
  max_amount: "",
  min_term: "1",
  max_term: "12",
  annual_rate: "0",
  method: "reducing",
  penalty_rate: "5",
  active: true,
};

function LoanProducts() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(null);
  const [form, setForm] = useState(EMPTY_PRODUCT);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const pushToast = useToast();

  async function loadProducts() {
    setLoading(true);
    setError("");
    try {
      const res = await apiFetch("/api/loan-products?include_inactive=1");
      setProducts(res?.data || []);
    } catch (err) {
      setError(err.message || "Failed to load loan products");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadProducts();
  }, []);

  function openEditor(product = null) {
    setEditing(product);
    setForm(product ? {
      name: product.name || "",
      min_amount: String(product.min_amount ?? 0),
      max_amount: String(product.max_amount ?? ""),
      min_term: String(product.min_term ?? 1),
      max_term: String(product.max_term ?? 12),
      annual_rate: String(product.annual_rate ?? 0),
      method: product.method || "reducing",
      penalty_rate: String(product.penalty_rate ?? 5),
      active: Boolean(product.active),
    } : EMPTY_PRODUCT);
    setOpen(true);
  }

  async function submitProduct(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = {
        ...form,
        min_amount: Number(form.min_amount),
        max_amount: Number(form.max_amount),
        min_term: Number(form.min_term),
        max_term: Number(form.max_term),
        annual_rate: Number(form.annual_rate),
        penalty_rate: Number(form.penalty_rate),
      };
      await apiFetch(editing ? `/api/loan-products/${editing.id}` : "/api/loan-products", {
        method: editing ? "PUT" : "POST",
        body: JSON.stringify(payload),
      });
      pushToast(editing ? "Loan product updated." : "Loan product created.", "success");
      setOpen(false);
      await loadProducts();
    } catch (err) {
      pushToast(err.message || "Could not save loan product", "error");
    } finally {
      setSaving(false);
    }
  }

  async function toggleStatus(product) {
    try {
      await apiFetch(`/api/loan-products/${product.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ active: !product.active }),
      });
      pushToast(product.active ? "Loan product deactivated." : "Loan product activated.", "success");
      await loadProducts();
    } catch (err) {
      pushToast(err.message || "Could not update product status", "error");
    }
  }

  const columns = useMemo(() => [
    { key: "name", label: "Product", render: (row) => <><strong>{row.name}</strong><p className="muted-inline">{row.method}</p></> },
    { key: "amount", label: "Amount Range", render: (row) => `${formatKES(row.min_amount)} - ${formatKES(row.max_amount)}` },
    { key: "term", label: "Term", render: (row) => `${row.min_term}-${row.max_term} months` },
    { key: "annual_rate", label: "Rate", render: (row) => `${Number(row.annual_rate || 0).toFixed(2)}%` },
    { key: "penalty_rate", label: "Penalty", render: (row) => `${Number(row.penalty_rate || 0).toFixed(2)}%` },
    { key: "active", label: "Status", render: (row) => (row.active ? "Active" : "Inactive") },
    {
      key: "actions",
      label: "Actions",
      render: (row) => (
        <div className="table-actions">
          <button type="button" className="ghost-btn" onClick={() => openEditor(row)}>Edit</button>
          <button type="button" className="ghost-btn" onClick={() => toggleStatus(row)}>
            {row.active ? "Deactivate" : "Activate"}
          </button>
        </div>
      ),
    },
  ], []);

  return (
    <section className="panel stack">
      <div className="row-between">
        <div>
          <h3>Loan Products</h3>
          <p className="muted">Create, edit, and deactivate the product types officers use on applications.</p>
        </div>
        <button type="button" className="primary-btn" onClick={() => openEditor()}>New Product</button>
      </div>

      {error ? <p className="error-box">{error}</p> : null}
      <DataTable columns={columns} rows={products} rowKey="id" loading={loading} emptyMessage="No loan products found." />

      <Modal open={open} title={editing ? "Edit Loan Product" : "New Loan Product"} onClose={() => setOpen(false)} maxWidth="760px">
        <form className="stack" onSubmit={submitProduct}>
          <label>
            Product Name
            <input value={form.name} onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))} required />
          </label>
          <div className="two-col">
            <label>Min Amount<input type="number" min="0" value={form.min_amount} onChange={(event) => setForm((prev) => ({ ...prev, min_amount: event.target.value }))} required /></label>
            <label>Max Amount<input type="number" min="1" value={form.max_amount} onChange={(event) => setForm((prev) => ({ ...prev, max_amount: event.target.value }))} required /></label>
          </div>
          <div className="two-col">
            <label>Min Term<input type="number" min="1" value={form.min_term} onChange={(event) => setForm((prev) => ({ ...prev, min_term: event.target.value }))} required /></label>
            <label>Max Term<input type="number" min="1" value={form.max_term} onChange={(event) => setForm((prev) => ({ ...prev, max_term: event.target.value }))} required /></label>
          </div>
          <div className="two-col">
            <label>Annual Rate %<input type="number" min="0" step="0.01" value={form.annual_rate} onChange={(event) => setForm((prev) => ({ ...prev, annual_rate: event.target.value }))} /></label>
            <label>Penalty Rate %<input type="number" min="0" step="0.01" value={form.penalty_rate} onChange={(event) => setForm((prev) => ({ ...prev, penalty_rate: event.target.value }))} /></label>
          </div>
          <div className="two-col">
            <label>
              Interest Method
              <select value={form.method} onChange={(event) => setForm((prev) => ({ ...prev, method: event.target.value }))}>
                <option value="reducing">Reducing Balance</option>
                <option value="flat">Flat Rate</option>
              </select>
            </label>
            <label className="checkbox-field">
              Active
              <span className="checkbox-row">
                <input type="checkbox" checked={form.active} onChange={(event) => setForm((prev) => ({ ...prev, active: event.target.checked }))} />
                <span>{form.active ? "Enabled" : "Disabled"}</span>
              </span>
            </label>
          </div>
          <button type="submit" className="primary-btn" disabled={saving}>{saving ? "Saving..." : "Save Product"}</button>
        </form>
      </Modal>
    </section>
  );
}

export default LoanProducts;
