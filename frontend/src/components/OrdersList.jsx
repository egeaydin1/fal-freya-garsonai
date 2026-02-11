import OrderCard from "./OrderCard";

export default function OrdersList({ orders, onUpdateStatus }) {
  return (
    <div className="space-y-4">
      {orders.map((order) => (
        <OrderCard
          key={order.id}
          order={order}
          onUpdateStatus={onUpdateStatus}
        />
      ))}

      {orders.length === 0 && (
        <div className="text-center opacity-50 py-8">No orders yet</div>
      )}
    </div>
  );
}
