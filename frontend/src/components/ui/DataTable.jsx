function clampPage(target, pages) {
  if (pages < 1) return 1;
  return Math.max(1, Math.min(pages, target));
}

function pageWindow(page, pages) {
  const start = Math.max(1, page - 2);
  const end = Math.min(pages, start + 4);
  const adjustedStart = Math.max(1, end - 4);
  const list = [];
  for (let i = adjustedStart; i <= end; i += 1) list.push(i);
  return list;
}

function DataTable({
  columns,
  rows,
  rowKey,
  loading = false,
  emptyMessage = "No records found.",
  page = 1,
  pages = 1,
  onPageChange,
}) {
  const hasRows = Array.isArray(rows) && rows.length > 0;

  return (
    <div className="table-shell">
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col.key} className={col.headClassName || ""}>{col.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={columns.length} className="table-empty">Loading...</td>
              </tr>
            ) : null}
            {!loading && !hasRows ? (
              <tr>
                <td colSpan={columns.length} className="table-empty">{emptyMessage}</td>
              </tr>
            ) : null}
            {!loading && hasRows
              ? rows.map((row, index) => (
                  <tr key={rowKey ? row[rowKey] : index}>
                    {columns.map((col) => (
                      <td key={`${col.key}-${rowKey ? row[rowKey] : index}`} className={col.cellClassName || ""}>
                        {col.render ? col.render(row) : row[col.key] ?? "-"}
                      </td>
                    ))}
                  </tr>
                ))
              : null}
          </tbody>
        </table>
      </div>

      {pages > 1 ? (
        <div className="table-pager">
          <button
            type="button"
            className="ghost-btn"
            onClick={() => onPageChange?.(clampPage(page - 1, pages))}
            disabled={page <= 1}
          >
            Prev
          </button>
          <div className="page-buttons">
            {pageWindow(page, pages).map((item) => (
              <button
                key={item}
                type="button"
                className={item === page ? "page-btn active" : "page-btn"}
                onClick={() => onPageChange?.(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="ghost-btn"
            onClick={() => onPageChange?.(clampPage(page + 1, pages))}
            disabled={page >= pages}
          >
            Next
          </button>
        </div>
      ) : null}
    </div>
  );
}

export default DataTable;
