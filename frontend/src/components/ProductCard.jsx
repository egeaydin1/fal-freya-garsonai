const API_BASE = "http://localhost:8000";

export default function ProductCard({ product, onDelete }) {
  const imageUrl = product.image_url
    ? product.image_url.startsWith("http")
      ? product.image_url
      : `${API_BASE}${product.image_url}`
    : null;

  return (
    <div className="card bg-base-100 shadow-xl">
      {imageUrl ? (
        <figure className="h-48 overflow-hidden">
          <img
            src={imageUrl}
            alt={product.name}
            className="w-full h-full object-cover"
          />
        </figure>
      ) : (
        <figure className="h-48 bg-base-200 flex items-center justify-center">
          <span className="text-5xl opacity-30">🍽️</span>
        </figure>
      )}
      <div className="card-body">
        <h2 className="card-title">{product.name}</h2>
        {product.description && (
          <p className="text-sm opacity-70">{product.description}</p>
        )}
        <p className="text-lg font-bold">{product.price} ₺</p>
        {product.category && (
          <div className="badge badge-outline">{product.category}</div>
        )}
        {product.allergens && product.allergens.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {product.allergens.map((a) => (
              <span
                key={a.id}
                className="badge badge-error badge-sm gap-1"
              >
                {a.icon || "⚠️"} {a.name}
              </span>
            ))}
          </div>
        )}
        <div className="card-actions justify-end mt-2">
          <button
            className="btn btn-sm btn-error"
            onClick={() => onDelete(product.id)}
          >
            Sil
          </button>
        </div>
      </div>
    </div>
  );
}
