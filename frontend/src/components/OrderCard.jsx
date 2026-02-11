export default function OrderCard({ order, onUpdateStatus }) {
  return (
    <div className="card bg-base-100 shadow-xl">
      <div className="card-body">
        <div className="flex justify-between items-center">
          <h2 className="card-title">
            Table {order.table_number} - Order #{order.id}
          </h2>
          <div className="badge badge-primary">{order.status}</div>
        </div>

        <div className="divider"></div>

        <ul className="space-y-1">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between">
              <span>
                {item.quantity}x {item.product_name}
              </span>
              <span>{item.price * item.quantity} TL</span>
            </li>
          ))}
        </ul>

        <div className="divider"></div>

        <div className="flex justify-between items-center">
          <span className="font-bold">Total: {order.total_price} TL</span>
          <div className="btn-group">
            <button
              className="btn btn-sm"
              onClick={() => onUpdateStatus(order.id, "preparing")}
              disabled={order.status === "preparing"}
            >
              Preparing
            </button>
            <button
              className="btn btn-sm"
              onClick={() => onUpdateStatus(order.id, "delivered")}
              disabled={order.status === "delivered"}
            >
              Delivered
            </button>
            <button
              className="btn btn-sm"
              onClick={() => onUpdateStatus(order.id, "paid")}
              disabled={order.status === "paid"}
            >
              Paid
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
