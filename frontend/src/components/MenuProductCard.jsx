export default function MenuProductCard({ product, onAdd }) {
  return (
    <div className="card bg-base-100 shadow-xl">
      {product.image_url && (
        <figure>
          <img src={product.image_url} alt={product.name} />
        </figure>
      )}
      <div className="card-body">
        <h2 className="card-title">{product.name}</h2>
        <p className="text-sm opacity-70">{product.description}</p>
        <div className="flex justify-between items-center mt-2">
          <span className="text-xl font-bold">{product.price} TL</span>
          <button
            className="btn btn-primary btn-sm"
            onClick={() => onAdd(product)}
          >
            Add +
          </button>
        </div>
      </div>
    </div>
  );
}
