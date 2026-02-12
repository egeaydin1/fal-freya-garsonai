import StatusBadge from "./StatusBadge";

export default function OrderCard({ order, onUpdateStatus, onMarkPaid }) {
  return (
    <div className="card bg-base-100 shadow-xl">
      <div className="card-body">
        <div className="flex justify-between items-center">
          <h2 className="card-title">
            Masa {order.table_number} - Sipariş #{order.id}
          </h2>
          <StatusBadge status={order.status} />
        </div>

        <div className="divider"></div>

        <ul className="space-y-1">
          {order.items.map((item) => (
            <li key={item.id} className="flex justify-between">
              <span>
                {item.quantity}x {item.product_name}
              </span>
              <span>{(item.price * item.quantity).toFixed(2)} ₺</span>
            </li>
          ))}
        </ul>

        <div className="divider"></div>

        <div className="flex justify-between items-center">
          <span className="font-bold">Toplam: {order.total_price.toFixed(2)} ₺</span>
          <div className="btn-group">
            {order.status !== "paid" && (
              <>
                <button
                  className="btn btn-sm"
                  onClick={() => onUpdateStatus(order.id, "preparing")}
                  disabled={order.status === "preparing"}
                >
                  Hazırlanıyor
                </button>
                <button
                  className="btn btn-sm"
                  onClick={() => onUpdateStatus(order.id, "delivered")}
                  disabled={order.status === "delivered"}
                >
                  Teslim Edildi
                </button>
                <button
                  className="btn btn-sm btn-success"
                  onClick={() => onMarkPaid(order.id)}
                >
                  ✓ Ödendi
                </button>
              </>
            )}
            {order.status === "paid" && (
              <span className="text-success font-bold">✓ Ödeme Alındı</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
