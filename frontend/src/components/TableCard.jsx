export default function TableCard({ table, onCopyQR, onDelete }) {
  return (
    <div className="card bg-base-100 shadow-xl">
      <div className="card-body">
        <h2 className="card-title">Table {table.table_number}</h2>
        <div className="text-xs opacity-70 truncate">{table.qr_token}</div>
        <div className="card-actions justify-end mt-2">
          <button
            className="btn btn-sm btn-primary"
            onClick={() => onCopyQR(table.qr_token)}
          >
            Copy Link
          </button>
          <button
            className="btn btn-sm btn-error"
            onClick={() => onDelete(table.id)}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
