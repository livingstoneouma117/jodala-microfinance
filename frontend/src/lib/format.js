export function formatKES(value) {
  const amount = Number(value || 0);
  return `KES ${amount.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function statusClass(status) {
  const safe = String(status || "unknown").toLowerCase();
  if (safe === "active") return "status status-active";
  if (safe === "overdue") return "status status-overdue";
  if (safe === "completed") return "status status-completed";
  if (safe === "approved") return "status status-approved";
  if (safe === "pending") return "status status-pending";
  if (safe === "rejected") return "status status-rejected";
  return "status";
}
