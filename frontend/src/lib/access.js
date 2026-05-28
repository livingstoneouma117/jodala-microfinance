const ROLES = [
  { value: "admin", label: "Admin" },
  { value: "officer", label: "Loan Officer" },
  { value: "accountant", label: "Accountant" },
  { value: "cashier", label: "Cashier" },
];

const ROLE_LABELS = Object.fromEntries(ROLES.map((role) => [role.value, role.label]));

const ROLE_PERMISSIONS = {
  admin: [
    "Full system access",
    "Manage users and assign roles",
    "Approve, disburse, edit, and delete records",
    "Application settings and audit logs",
  ],
  officer: [
    "Register members and borrowers",
    "Create and manage loan applications",
    "Record savings and repayments",
    "View operational reports",
  ],
  accountant: [
    "Accounting reports and ledgers",
    "Expenses and chart of accounts",
    "Loan disbursement support",
    "Audit log visibility",
  ],
  cashier: [
    "Savings deposits and withdrawals",
    "Loan repayment collection",
    "Cash collection workflow",
  ],
};

function normalizeRole(role) {
  return String(role || "").trim().toLowerCase();
}

function roleLabel(role) {
  const normalized = normalizeRole(role);
  return ROLE_LABELS[normalized] || role || "-";
}

function canAccess(role, allowedRoles = []) {
  const requiredRoles = Array.isArray(allowedRoles) ? allowedRoles : [];
  return requiredRoles.length === 0 || requiredRoles.includes(normalizeRole(role));
}

export { ROLES, ROLE_PERMISSIONS, roleLabel, canAccess };
