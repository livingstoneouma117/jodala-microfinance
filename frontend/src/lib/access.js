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

const MODULE_ACTIONS = {
  dashboard: [],
  members: ["create", "edit", "delete", "export"],
  borrowers: ["create", "edit", "delete", "export"],
  loans: ["create", "edit", "delete", "approve", "disburse", "reject", "export"],
  "loan-products": ["create", "edit", "delete", "export"],
  savings: ["create", "edit", "delete", "export"],
  repayments: ["create", "edit", "delete", "export"],
  reports: ["export"],
  accounting: ["edit", "export"],
  expenses: ["create", "edit", "delete", "export"],
  settings: ["edit"],
  notifications: ["edit"],
  "audit-logs": ["export"],
};

const MODULE_LABELS = {
  dashboard: "Dashboard",
  members: "Members",
  borrowers: "Borrowers",
  loans: "Loans",
  "loan-products": "Loan Products",
  savings: "Savings",
  repayments: "Repayments",
  reports: "Reports",
  accounting: "Accounting",
  expenses: "Expenses",
  settings: "Settings",
  notifications: "Notifications",
  "audit-logs": "Audit Logs",
};

const ACTION_LABELS = {
  create: "Create",
  edit: "Edit",
  delete: "Delete",
  approve: "Approve",
  disburse: "Disburse",
  reject: "Reject",
  export: "Export",
};

const ACTION_DESCRIPTIONS = {
  create: "Add new records in this module.",
  edit: "Update records and settings in this module.",
  delete: "Remove records from this module.",
  approve: "Approve workflow items in this module.",
  disburse: "Release funds or complete disbursement actions.",
  reject: "Reject workflow items in this module.",
  export: "Export or download data from this module.",
};

function normalizeRole(role) {
  return String(role || "").trim().toLowerCase();
}

function splitPermission(permission) {
  const safe = String(permission || "").trim().toLowerCase().replace(/\s+/g, "_");
  if (!safe) return ["", null];
  if (!safe.includes(".")) return [safe, null];
  const [module, action] = safe.split(".", 2);
  if (action === "view") return [module, null];
  return [module, action || null];
}

function canonicalPermission(permission) {
  const [module, action] = splitPermission(permission);
  if (!module) return "";
  if (!action) return module;
  if (!MODULE_ACTIONS[module] || !MODULE_ACTIONS[module].includes(action)) return "";
  return `${module}.${action}`;
}

function buildPermissions() {
  return Object.entries(MODULE_ACTIONS).flatMap(([module, actions]) => {
    const entries = [
      {
        value: module,
        module,
        action: null,
        label: MODULE_LABELS[module] || module,
        description: `Open and view ${MODULE_LABELS[module] || module}.`,
      },
    ];

    for (const action of actions) {
      entries.push({
        value: `${module}.${action}`,
        module,
        action,
        label: `${MODULE_LABELS[module] || module} - ${ACTION_LABELS[action] || action}`,
        description: ACTION_DESCRIPTIONS[action] || `${ACTION_LABELS[action] || action} access for ${MODULE_LABELS[module] || module}.`,
      });
    }

    return entries;
  });
}

const AVAILABLE_PERMISSION_GROUPS = Object.entries(MODULE_ACTIONS).map(([module, actions]) => ({
  module,
  label: MODULE_LABELS[module] || module,
  description: `Grant access to ${MODULE_LABELS[module] || module.toLowerCase()}.`,
  permissions: [
    {
      value: module,
      label: "View",
      description: `Open and view ${MODULE_LABELS[module] || module}.`,
    },
    ...actions.map((action) => ({
      value: `${module}.${action}`,
      label: ACTION_LABELS[action] || action,
      description: ACTION_DESCRIPTIONS[action] || `${ACTION_LABELS[action] || action} access for this module.`,
    })),
  ],
}));

const AVAILABLE_PERMISSIONS = buildPermissions();

const PERMISSION_LABELS = Object.fromEntries(
  AVAILABLE_PERMISSIONS.map((permission) => [permission.value, permission.label])
);

const FEATURE_PERMISSIONS = {
  dashboard: "dashboard",
  members: "members",
  borrowers: "members",
  loans: "loans",
  "loan-products": "loan-products",
  savings: "savings",
  repayments: "repayments",
  reports: "reports",
  accounting: "accounting",
  expenses: "expenses",
  settings: "settings",
  notifications: "settings",
  "audit-logs": "settings",
};

function normalizePermissions(value) {
  if (value == null) return [];
  const rawList = Array.isArray(value)
    ? value
    : typeof value === "string"
      ? (() => {
          const raw = value.trim();
          if (!raw) return [];
          try {
            const parsed = JSON.parse(raw);
            if (Array.isArray(parsed)) return parsed;
          } catch (error) {
            // Fall through to comma-separated parsing.
          }
          return raw.split(",");
        })()
      : typeof value === "object"
        ? normalizePermissions(value.permissions)
        : [];

  const seen = new Set();
  const cleaned = [];
  for (const item of rawList) {
    const canonical = canonicalPermission(item);
    if (canonical && !seen.has(canonical)) {
      seen.add(canonical);
      cleaned.push(canonical);
    }
  }
  return cleaned;
}

function roleLabel(role) {
  const normalized = normalizeRole(role);
  return ROLE_LABELS[normalized] || role || "-";
}

function permissionLabel(permission) {
  const [module, action] = splitPermission(permission);
  if (!module) return "-";
  if (!action) return MODULE_LABELS[module] || module;
  return `${MODULE_LABELS[module] || module} - ${ACTION_LABELS[action] || action}`;
}

function permissionDescription(permission) {
  const [module, action] = splitPermission(permission);
  if (!module) return "";
  if (!action) return `Open and view ${MODULE_LABELS[module] || module}.`;
  return ACTION_DESCRIPTIONS[action] || `${ACTION_LABELS[action] || action} access for ${MODULE_LABELS[module] || module}.`;
}

function permissionMatches(userPermission, requiredPermission) {
  const [userModule, userAction] = splitPermission(userPermission);
  const [requiredModule, requiredAction] = splitPermission(requiredPermission);
  if (!userModule || !requiredModule || userModule !== requiredModule) return false;
  if (!userAction || !requiredAction) return true;
  return userAction === requiredAction;
}

function routePermissionForPath(path, method = "GET") {
  const safePath = String(path || "");
  const safeMethod = String(method || "GET").toUpperCase();

  if (safePath.startsWith("/api/reports/export/")) return "reports.export";
  if (safePath.startsWith("/api/loans/") && safePath.endsWith("/approve")) return "loans.approve";
  if (safePath.startsWith("/api/loans/") && safePath.endsWith("/disburse")) return "loans.disburse";
  if (safePath.startsWith("/api/loans/") && safePath.endsWith("/reject")) return "loans.reject";
  if (safePath.startsWith("/api/loans/") && (safePath.endsWith("/statement.pdf") || safePath.endsWith("/statement"))) return "loans.export";
  if (safePath.startsWith("/api/loans/") && (safePath.includes("/guarantors") || safePath.endsWith("/restructure") || safePath.endsWith("/write-off"))) return "loans.edit";
  if (safePath.startsWith("/api/savings/") && safePath.includes("/passbook")) return "savings.export";
  if (safePath.startsWith("/api/expenses/accounts/") && safePath.endsWith("/status")) return "expenses.edit";
  if (safePath.startsWith("/api/notifications/read-all")) return "notifications.edit";
  if (safePath.startsWith("/api/notifications/") && safePath.endsWith("/read")) return "notifications.edit";
  if (safePath.startsWith("/api/settings/account/add")) return "settings.edit";
  if (safePath.startsWith("/api/settings")) {
    return safeMethod === "GET" ? "settings" : "settings.edit";
  }
  if (safePath.startsWith("/api/dividends")) {
    return safeMethod === "GET" || safeMethod === "HEAD" ? "accounting" : "accounting.edit";
  }

  const prefixMap = [
    ["/api/members", "members"],
    ["/api/borrowers", "members"],
    ["/api/loan-products", "loan-products"],
    ["/api/loans", "loans"],
    ["/api/savings", "savings"],
    ["/api/repayments", "repayments"],
    ["/api/reports", "reports"],
    ["/api/accounting", "accounting"],
    ["/api/expenses", "expenses"],
    ["/api/dashboard", "dashboard"],
  ];

  for (const [prefix, module] of prefixMap) {
    if (safePath.startsWith(prefix)) {
      if (safeMethod === "GET" || safeMethod === "HEAD") return module;
      if (safeMethod === "POST") return `${module}.create`;
      if (safeMethod === "PUT" || safeMethod === "PATCH") return `${module}.edit`;
      if (safeMethod === "DELETE") return `${module}.delete`;
      return module;
    }
  }

  return null;
}

function hasPermission(userOrPermissions, permission) {
  const required = canonicalPermission(permission);
  if (!required) return false;
  const permissions = Array.isArray(userOrPermissions)
    ? normalizePermissions(userOrPermissions)
    : normalizePermissions(userOrPermissions?.permissions ?? userOrPermissions);
  return permissions.some((userPermission) => permissionMatches(userPermission, required));
}

function canAccess(userOrRole, allowedRoles = [], allowedPermissions = []) {
  const requiredRoles = Array.isArray(allowedRoles) ? allowedRoles.map(normalizeRole).filter(Boolean) : [];
  const requiredPermissions = Array.isArray(allowedPermissions)
    ? allowedPermissions.map(canonicalPermission).filter(Boolean)
    : [];
  if (requiredRoles.length === 0 && requiredPermissions.length === 0) return true;

  const userRole = typeof userOrRole === "object" && userOrRole !== null ? normalizeRole(userOrRole.role) : normalizeRole(userOrRole);
  const userPermissions = typeof userOrRole === "object" && userOrRole !== null
    ? normalizePermissions(userOrRole.permissions)
    : [];

  if (requiredRoles.includes(userRole)) return true;
  return requiredPermissions.some((permission) => userPermissions.some((userPermission) => permissionMatches(userPermission, permission)));
}

export {
  ACTION_LABELS,
  AVAILABLE_PERMISSIONS,
  AVAILABLE_PERMISSION_GROUPS,
  FEATURE_PERMISSIONS,
  MODULE_ACTIONS,
  MODULE_LABELS,
  ROLES,
  ROLE_PERMISSIONS,
  canAccess,
  canonicalPermission,
  hasPermission,
  normalizePermissions,
  permissionDescription,
  permissionLabel,
  permissionMatches,
  roleLabel,
  routePermissionForPath,
  splitPermission,
};
