export default function CartItem({ item, onAdd, onRemove }) {
  return (
    <div className="flex justify-between items-center p-2 bg-base-200 rounded">
      <div className="flex-1">
        <p className="font-bold">{item.product.name}</p>
        <p className="text-sm opacity-70">
          {item.product.price} TL x {item.quantity}
        </p>
      </div>
      <div className="flex gap-2 items-center">
        <button
          className="btn btn-xs"
          onClick={() => onRemove(item.product_id)}
        >
          -
        </button>
        <span>{item.quantity}</span>
        <button className="btn btn-xs" onClick={() => onAdd(item.product)}>
          +
        </button>
      </div>
    </div>
  );
}
