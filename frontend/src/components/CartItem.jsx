const API_BASE = "http://localhost:8000";

export default function CartItem({ item, onAdd, onRemove }) {
  const imageUrl = item.product.image_url
    ? item.product.image_url.startsWith("http")
      ? item.product.image_url
      : `${API_BASE}${item.product.image_url}`
    : null;

  return (
    <div className="flex items-center gap-3 p-3 bg-base-200 rounded-2xl animate-fade-in-up">
      {/* Thumbnail */}
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={item.product.name}
          className="w-14 h-14 rounded-xl object-cover flex-shrink-0"
        />
      ) : (
        <div className="w-14 h-14 rounded-xl bg-base-300 flex items-center justify-center flex-shrink-0 text-2xl opacity-40">
          🍽️
        </div>
      )}

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="font-semibold truncate">{item.product.name}</p>
        <p className="text-sm opacity-60">
          {item.product.price.toFixed(2)} ₺
        </p>
      </div>

      {/* Quantity controls */}
      <div className="flex items-center gap-2 bg-base-100 rounded-full px-2 py-1 shadow-sm">
        <button
          className="btn btn-ghost btn-xs btn-circle"
          onClick={() => onRemove(item.product_id)}
        >
          −
        </button>
        <span className="font-bold min-w-[1.5rem] text-center">{item.quantity}</span>
        <button
          className="btn btn-ghost btn-xs btn-circle"
          onClick={() => onAdd(item.product)}
        >
          +
        </button>
      </div>

      {/* Item total */}
      <span className="font-bold text-sm min-w-[4rem] text-right">
        {(item.product.price * item.quantity).toFixed(2)} ₺
      </span>
    </div>
  );
}
