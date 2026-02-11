import CartItem from "./CartItem";

export default function Cart({ cart, total, onAdd, onRemove, onCheckout, onClose }) {
  return (
    <div className="drawer drawer-end drawer-open">
      <input type="checkbox" className="drawer-toggle" />
      <div className="drawer-side">
        <label className="drawer-overlay" onClick={onClose}></label>
        <div className="menu p-4 w-80 min-h-full bg-base-100 text-base-content">
          <h2 className="text-2xl font-bold mb-4">Cart</h2>

          {cart.length === 0 ? (
            <p className="text-center opacity-50">Cart is empty</p>
          ) : (
            <>
              <div className="space-y-2 flex-1">
                {cart.map((item) => (
                  <CartItem
                    key={item.product_id}
                    item={item}
                    onAdd={onAdd}
                    onRemove={onRemove}
                  />
                ))}
              </div>

              <div className="divider"></div>

              <div className="text-xl font-bold mb-4">
                Total: {total.toFixed(2)} TL
              </div>

              <button className="btn btn-primary w-full" onClick={onCheckout}>
                Checkout
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
