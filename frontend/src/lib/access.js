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

const AVAILABLE_PERMISSIONS = [
  {
    value: "dashboard",
    label: "Dashboard",
    description: "View member, loan, cashflow, and portfolio summaries.",
  },
  {
    value: "members",
    label: "Members",
    description: "Create, update, and review member records.",
  },
  {
    value: "loans",
    label: "Loans",
    description: "Work with loan applications, approvals, and schedules.",
  },
  {
    value: "savings",
    label: "Savings",
    description: "Record savings deposits and withdrawals.",
  },
  {
    value: "repayments",
    label: "Repayments",
    description: "Post loan repayments and collection activity.",
  },
  {
    value: "reports",
    label: "Reports",
    description: "Open operational and portfolio reports.",
  },
  {
    value: "accounting",
    label: "Accounting",
    description: "Use account ledgers and accounting reports.",
  },
  {
    value: "expenses",
    label: "Expenses",
    description: "Manage expense accounts and expense transactions.",
  },
  {
    value: "settings",
    label: "Settings",
    description: "Adjust settings, notifications, and audit logs.",
  },
];

const PERMISSION_LABELS = Object.fromEntries(
  AVAILABLE_PERMISSIONS.map((permission) => [permission.value, permission.label])
);

const FEATURE_PERMISSIONS = {
  dashboard: "dashboard",
  members: "members",
  borrowers: "members",
  loans: "loans",
  "loan-products": "loans",
  savings: "savings",
  repayments: "repayments",
  reports: "reports",
  accounting: "accounting",
  expenses: "expenses",
  settings: "settings",
  notifications: "settings",
  "audit-logs": "settings",
};

function normalizeRole(role) {
  return String(role || "").trim().toLowerCase();
}

function normalizePermissions(value) {
  if (value == null) return [];
  if (Array.isArray(value)) return value.map((item) => String(item || "").trim().toLowerCase()).filter(Boolean);
  if (typeof value === "string") {
    const raw = value.trim();
    if (!raw) return [];
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return normalizePermissions(parsed);
      }
    } catch (error) {
      // Fall through to comma-separated strings.
    }
    return raw
      .split(",")
      .map((item) => String(item || "").trim().toLowerCase().replace(/\s+/g, "_"))
      .filter(Boolean);
  }
  if (typeof value === "object") {
    return normalizePermissions(value.permissions);
  }
  return [];
}

function roleLabel(role) {
  const normalized = normalizeRole(role);
  return ROLE_LABELS[normalized] || role || "-";
}

function permissionLabel(permission) {
  const normalized = String(permission || "").trim().toLowerCase();
  return PERMISSION_LABELS[normalized] || normalized.replace(/_/g, " ");
}

function routePermissionForPath(path) {
  const safePath = String(path || "");
  for (const [prefix, permission] of Object.entries(FEATURE_PERMISSIONS)) {
    if (safePath.startsWith(`/api/${prefix}`)) {
      return permission;
    }
  }
  return null;
}

function hasPermission(userOrPermissions, permission) {
  const normalizedPermission = String(permission || "").trim().toLowerCase();
  if (!normalizedPermission) return false;
  const permissions = Array.isArray(userOrPermissions)
    ? normalizePermissions(userOrPermissions)
    : normalizePermissions(userOrPermissions?.permissions ?? userOrPermissions);
  return permissions.includes(normalizedPermission);
}

function canAccess(userOrRole, allowedRoles = [], allowedPermissions = []) {
  const requiredRoles = Array.isArray(allowedRoles) ? allowedRoles.map(normalizeRole).filter(Boolean) : [];
  const requiredPermissions = Array.isArray(allowedPermissions)
    ? allowedPermissions.map((permission) => String(permission || "").trim().toLowerCase()).filter(Boolean)
    : [];
  if (requiredRoles.length === 0 && requiredPermissions.length === 0) return true;

  const userRole = typeof userOrRole === "object" && userOrRole !== null ? normalizeRole(userOrRole.role) : normalizeRole(userOrRole);
  const userPermissions = typeof userOrRole === "object" && userOrRole !== null
    ? normalizePermissions(userOrRole.permissions)
    : [];

  if (requiredRoles.includes(userRole)) return true;
  return requiredPermissions.some((permission) => userPermissions.includes(permission));
}

export {
  AVAILABLE_PERMISSIONS,
  FEATURE_PERMISSIONS,
  ROLES,
  ROLE_PERMISSIONS,
  canAccess,
  hasPermission,
  normalizePermissions,
  permissionLabel,
  roleLabel,
  routePermissionForPath,
};
