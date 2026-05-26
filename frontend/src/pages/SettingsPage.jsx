import { useEffect, useState } from "react";
import { apiFetch } from "../lib/api";
import { formatKES } from "../lib/format";
import StatCard from "../components/ui/StatCard";
import { useToast } from "../components/ui/Toast";

function SettingsPage() {
  const [form, setForm] = useState({
    sacco_name: "",
    logo_text: "",
    logo_url: "",
    address: "",
    phone: "",
    account_opening_balance: "0",
  });
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [fundAmount, setFundAmount] = useState("");
  const [funding, setFunding] = useState(false);

  const pushToast = useToast();

  useEffect(() => {
    let mounted = true;
    setLoading(true);

    Promise.all([apiFetch("/api/settings"), apiFetch("/api/dashboard")])
      .then(([settingsRes, dashboardRes]) => {
        if (!mounted) return;
        const settings = settingsRes?.data || {};
        setForm({
          sacco_name: settings.sacco_name || "",
          logo_text: settings.logo_text || "",
          logo_url: settings.logo_url || "",
          address: settings.address || "",
          phone: settings.phone || "",
          account_opening_balance: settings.account_opening_balance || "0",
        });
        setStats(dashboardRes?.data?.stats || null);
      })
      .catch((err) => {
        if (!mounted) return;
        pushToast(err.message || "Failed to load settings", "error");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [pushToast]);

  async function saveSettings(event) {
    event.preventDefault();
    setSaving(true);
    try {
      const payload = {
        sacco_name: form.sacco_name,
        logo_text: form.logo_text,
        logo_url: form.logo_url,
        address: form.address,
        phone: form.phone,
        account_opening_balance: form.account_opening_balance,
      };
      const res = await apiFetch("/api/settings", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      const updated = res?.data || {};
      setForm((prev) => ({
        ...prev,
        account_opening_balance: updated.account_opening_balance || prev.account_opening_balance,
      }));
      pushToast("Settings updated.", "success");
    } catch (err) {
      pushToast(err.message || "Could not save settings", "error");
    } finally {
      setSaving(false);
    }
  }

  async function addFunds(event) {
    event.preventDefault();
    setFunding(true);
    try {
      await apiFetch("/api/settings/account/add", {
        method: "POST",
        body: JSON.stringify({ amount: Number(fundAmount) }),
      });
      setFundAmount("");
      const [settingsRes, dashboardRes] = await Promise.all([apiFetch("/api/settings"), apiFetch("/api/dashboard")]);
      const settings = settingsRes?.data || {};
      setForm((prev) => ({ ...prev, account_opening_balance: settings.account_opening_balance || prev.account_opening_balance }));
      setStats(dashboardRes?.data?.stats || null);
      pushToast("Main account funded successfully.", "success");
    } catch (err) {
      pushToast(err.message || "Could not add funds", "error");
    } finally {
      setFunding(false);
    }
  }

  if (loading) {
    return (
      <div className="stack">
        <header className="page-head">
          <h2>Settings</h2>
          <p>Loading application settings...</p>
        </header>
      </div>
    );
  }

  return (
    <div className="stack">
      <header className="page-head">
        <h2>Settings</h2>
        <p>Manage app identity, contacts, and main account opening balance.</p>
      </header>

      {stats ? (
        <div className="card-grid">
          <StatCard label="Main Account Balance" value={formatKES(stats.account_current_balance)} tone="primary" />
          <StatCard label="Savings Collected" value={formatKES(stats.account_savings_collections)} tone="ok" />
          <StatCard label="Loan Repayments" value={formatKES(stats.account_loan_repayments)} tone="ok" />
          <StatCard label="Loan Disbursed" value={formatKES(stats.account_loan_disbursed)} tone="warn" />
          <StatCard label="Expenses" value={formatKES(stats.account_expenses)} tone="danger" />
          <StatCard label="Opening Balance" value={formatKES(form.account_opening_balance)} />
        </div>
      ) : null}

      <section className="panel stack">
        <h3>Application Profile</h3>
        <form className="stack" onSubmit={saveSettings}>
          <div className="two-col">
            <label>
              Organization Name
              <input
                type="text"
                value={form.sacco_name}
                onChange={(event) => setForm((prev) => ({ ...prev, sacco_name: event.target.value }))}
              />
            </label>
            <label>
              Logo Text
              <input
                type="text"
                value={form.logo_text}
                onChange={(event) => setForm((prev) => ({ ...prev, logo_text: event.target.value }))}
              />
            </label>
          </div>

          <div className="two-col">
            <label>
              Phone
              <input
                type="text"
                value={form.phone}
                onChange={(event) => setForm((prev) => ({ ...prev, phone: event.target.value }))}
              />
            </label>
            <label>
              Logo URL
              <input
                type="text"
                value={form.logo_url}
                onChange={(event) => setForm((prev) => ({ ...prev, logo_url: event.target.value }))}
              />
            </label>
          </div>

          <label>
            Address
            <input
              type="text"
              value={form.address}
              onChange={(event) => setForm((prev) => ({ ...prev, address: event.target.value }))}
            />
          </label>

          <label>
            Opening Balance (KES)
            <input
              type="number"
              value={form.account_opening_balance}
              onChange={(event) => setForm((prev) => ({ ...prev, account_opening_balance: event.target.value }))}
            />
          </label>

          <button type="submit" className="primary-btn" disabled={saving}>
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </form>
      </section>

      <section className="panel stack">
        <h3>Add Funds to Main Account</h3>
        <form className="row-form" onSubmit={addFunds}>
          <input
            type="number"
            min="1"
            step="0.01"
            placeholder="Amount"
            value={fundAmount}
            onChange={(event) => setFundAmount(event.target.value)}
            required
          />
          <button type="submit" className="primary-btn" disabled={funding}>
            {funding ? "Updating..." : "Add Funds"}
          </button>
        </form>
      </section>
    </div>
  );
}

export default SettingsPage;
