export default function ProductCard({ product, onDelete }) {
  return (
    <div className="card bg-base-100 shadow-xl">
      <div className="card-body">
        <h2 className="card-title">{product.name}</h2>
        <p className="text-sm opacity-70">{product.description}</p>
        <p className="text-lg font-bold">{product.price} TL</p>
        <div className="badge badge-outline">{product.category}</div>
        <div className="card-actions justify-end">
          <button
            className="btn btn-sm btn-error"
            onClick={() => onDelete(product.id)}
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}
