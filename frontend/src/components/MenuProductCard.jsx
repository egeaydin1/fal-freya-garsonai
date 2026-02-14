import { useState } from "react";

import { config } from "../config";
const API_BASE = config.API_BASE;

export default function MenuProductCard({ product, onAdd, cartQuantity = 0 }) {
  const [added, setAdded] = useState(false);

  const imageUrl = product.image_url
    ? product.image_url.startsWith("http")
      ? product.image_url
      : `${API_BASE}${product.image_url}`
    : null;

  const handleAdd = () => {
    onAdd(product);
    setAdded(true);
    setTimeout(() => setAdded(false), 600);
  };

  return (
    <div className="group bg-base-100 rounded-2xl shadow-md overflow-hidden hover:shadow-xl transition-all duration-300 animate-fade-in-up">
      {/* Image */}
      {imageUrl ? (
        <div className="h-44 overflow-hidden relative">
          <img
            src={imageUrl}
            alt={product.name}
            className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
          />
          {cartQuantity > 0 && (
            <div className="absolute top-3 right-3 badge badge-primary badge-lg shadow-lg animate-pop-bounce">
              {cartQuantity}
            </div>
          )}
        </div>
      ) : (
        <div className="h-32 bg-gradient-to-br from-base-200 to-base-300 flex items-center justify-center relative">
          <span className="text-5xl opacity-20">🍽️</span>
          {cartQuantity > 0 && (
            <div className="absolute top-3 right-3 badge badge-primary badge-lg shadow-lg animate-pop-bounce">
              {cartQuantity}
            </div>
          )}
        </div>
      )}

      <div className="p-4">
        <h3 className="font-bold text-lg leading-tight mb-1">{product.name}</h3>
        {product.description && (
          <p className="text-sm opacity-60 line-clamp-2 mb-2">{product.description}</p>
        )}

        {/* Allergens */}
        {product.allergens && product.allergens.length > 0 && (
          <div className="flex flex-wrap gap-1 mb-3">
            {product.allergens.map((a) => (
              <span key={a.id} className="badge badge-warning badge-xs gap-0.5">
                {a.icon || "⚠️"} {a.name}
              </span>
            ))}
          </div>
        )}

        {/* Price + Add button */}
        <div className="flex justify-between items-center">
          <span className="text-xl font-bold">{product.price} ₺</span>
          <button
            className={`btn btn-sm rounded-xl transition-all duration-300 ${
              added
                ? "btn-success scale-110"
                : "btn-primary"
            }`}
            onClick={handleAdd}
          >
            {added ? "✓" : "Ekle"}
          </button>
        </div>
      </div>
    </div>
  );
}
