import { useState } from "react";

export default function TableForm({ onSubmit }) {
  const [newTableNumber, setNewTableNumber] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(newTableNumber);
    setNewTableNumber("");
  };

  return (
    <form onSubmit={handleSubmit} className="card bg-base-100 p-4 mb-4">
      <h3 className="text-lg font-bold mb-2">Add Table</h3>
      <div className="flex gap-2">
        <input
          type="number"
          placeholder="Table Number"
          className="input input-bordered flex-1"
          value={newTableNumber}
          onChange={(e) => setNewTableNumber(e.target.value)}
          required
        />
        <button type="submit" className="btn btn-primary">
          Add
        </button>
      </div>
    </form>
  );
}
