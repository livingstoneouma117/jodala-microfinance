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
  if (safe === "written_off") return "status status-written-off";
  return "status";
}

export function formatDate(value) {
  if (!value) return "-";
  const safe = String(value).slice(0, 10);
  const date = new Date(safe);
  if (Number.isNaN(date.getTime())) return safe;
  return date.toLocaleDateString("en-KE", { year: "numeric", month: "short", day: "numeric" });
}
