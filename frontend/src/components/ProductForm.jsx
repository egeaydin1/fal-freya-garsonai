import { useState } from "react";

export default function ProductForm({ onSubmit }) {
  const [newProduct, setNewProduct] = useState({
    name: "",
    description: "",
    price: "",
    category: "",
  });

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(newProduct);
    setNewProduct({ name: "", description: "", price: "", category: "" });
  };

  return (
    <form onSubmit={handleSubmit} className="card bg-base-100 p-4 mb-4">
      <h3 className="text-lg font-bold mb-2">Add Product</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <input
          type="text"
          placeholder="Name"
          className="input input-bordered"
          value={newProduct.name}
          onChange={(e) =>
            setNewProduct({ ...newProduct, name: e.target.value })
          }
          required
        />
        <input
          type="number"
          step="0.01"
          placeholder="Price"
          className="input input-bordered"
          value={newProduct.price}
          onChange={(e) =>
            setNewProduct({ ...newProduct, price: e.target.value })
          }
          required
        />
        <input
          type="text"
          placeholder="Category"
          className="input input-bordered"
          value={newProduct.category}
          onChange={(e) =>
            setNewProduct({ ...newProduct, category: e.target.value })
          }
        />
        <input
          type="text"
          placeholder="Description"
          className="input input-bordered"
          value={newProduct.description}
          onChange={(e) =>
            setNewProduct({
              ...newProduct,
              description: e.target.value,
            })
          }
        />
      </div>
      <button type="submit" className="btn btn-primary mt-2">
        Add Product
      </button>
    </form>
  );
}
