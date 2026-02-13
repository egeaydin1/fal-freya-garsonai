import TableForm from "./TableForm";
import TableCard from "./TableCard";

export default function TablesList({ tables, onCreateTable, onDeleteTable, onPayAll }) {
  const copyQR = (token) => {
    const url = `${window.location.origin}/menu/${token}`;
    navigator.clipboard.writeText(url);
    alert("QR link copied!");
  };

  return (
    <div>
      <TableForm onSubmit={onCreateTable} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {tables.map((table) => (
          <TableCard
            key={table.id}
            table={table}
            onCopyQR={copyQR}
            onDelete={onDeleteTable}
            onPayAll={onPayAll}
          />
        ))}
      </div>
    </div>
  );
}
