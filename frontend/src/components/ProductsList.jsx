import { useState } from "react";
import ProductForm from "./ProductForm";
import ProductCard from "./ProductCard";

export default function ProductsList({
  products,
  allergens = [],
  onCreateProduct,
  onDeleteProduct,
  onCreateAllergen,
  onDeleteAllergen,
}) {
  const [showAllergenForm, setShowAllergenForm] = useState(false);
  const [newAllergen, setNewAllergen] = useState({ name: "", icon: "" });

  const handleAllergenSubmit = (e) => {
    e.preventDefault();
    if (!newAllergen.name.trim()) return;
    onCreateAllergen(newAllergen);
    setNewAllergen({ name: "", icon: "" });
  };

  return (
    <div>
      {/* Allergen Management */}
      <div className="card bg-base-100 p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <h3 className="text-lg font-bold">Alerjenler</h3>
          <button
            className="btn btn-sm btn-ghost"
            onClick={() => setShowAllergenForm(!showAllergenForm)}
          >
            {showAllergenForm ? "Kapat" : "+ Alerjen Ekle"}
          </button>
        </div>

        {showAllergenForm && (
          <form onSubmit={handleAllergenSubmit} className="flex gap-2 mb-3">
            <input
              type="text"
              placeholder="Alerjen adı (ör: Gluten)"
              className="input input-bordered input-sm flex-1"
              value={newAllergen.name}
              onChange={(e) =>
                setNewAllergen({ ...newAllergen, name: e.target.value })
              }
              required
            />
            <input
              type="text"
              placeholder="İkon (ör: 🌾)"
              className="input input-bordered input-sm w-20"
              value={newAllergen.icon}
              onChange={(e) =>
                setNewAllergen({ ...newAllergen, icon: e.target.value })
              }
            />
            <button type="submit" className="btn btn-sm btn-primary">
              Ekle
            </button>
          </form>
        )}

        <div className="flex flex-wrap gap-2">
          {allergens.map((allergen) => (
            <div
              key={allergen.id}
              className="badge badge-lg gap-2 badge-outline"
            >
              <span>{allergen.icon || "⚠️"}</span>
              <span>{allergen.name}</span>
              <button
                className="btn btn-ghost btn-xs p-0"
                onClick={() => onDeleteAllergen(allergen.id)}
              >
                ✕
              </button>
            </div>
          ))}
          {allergens.length === 0 && (
            <p className="text-sm opacity-50">
              Henüz alerjen eklenmedi. Önce alerjen ekleyin, sonra ürünlere atayın.
            </p>
          )}
        </div>
      </div>

      <ProductForm onSubmit={onCreateProduct} allergens={allergens} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {products.map((product) => (
          <ProductCard
            key={product.id}
            product={product}
            onDelete={onDeleteProduct}
          />
        ))}
      </div>
    </div>
  );
}
