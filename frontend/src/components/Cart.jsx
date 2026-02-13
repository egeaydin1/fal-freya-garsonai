import { useState } from "react";
import CartItem from "./CartItem";

export default function Cart({ cart, total, onAdd, onRemove, onCheckout, onClose }) {
  const [isClosing, setIsClosing] = useState(false);

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(onClose, 350);
  };

  const handleCheckout = () => {
    onCheckout();
    handleClose();
  };

  return (
    <div className="fixed inset-0 z-[100]">
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black/40 backdrop-blur-sm ${isClosing ? "opacity-0" : "animate-overlay-in"}`}
        style={{ transition: "opacity 0.3s ease" }}
        onClick={handleClose}
      />

      {/* Bottom Sheet */}
      <div
        className={`absolute bottom-0 left-0 right-0 bg-base-100 rounded-t-3xl shadow-2xl max-h-[85vh] flex flex-col ${isClosing ? "translate-y-full" : "cart-drawer"}`}
        style={{ transition: isClosing ? "transform 0.35s cubic-bezier(.22,1,.36,1)" : undefined }}
      >
        {/* Handle bar */}
        <div className="flex justify-center pt-3 pb-1">
          <div className="w-10 h-1 bg-base-300 rounded-full" />
        </div>

        {/* Header */}
        <div className="flex justify-between items-center px-6 pb-4">
          <h2 className="text-2xl font-bold">Sepetim</h2>
          <button
            className="btn btn-ghost btn-sm btn-circle text-lg"
            onClick={handleClose}
          >
            ✕
          </button>
        </div>

        {/* Cart items */}
        {cart.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center py-12 opacity-50">
            <span className="text-5xl mb-3">🛒</span>
            <p className="text-lg">Sepetiniz boş</p>
          </div>
        ) : (
          <>
            <div className="flex-1 overflow-y-auto px-6 space-y-3 no-scrollbar stagger-children">
              {cart.map((item) => (
                <CartItem
                  key={item.product_id}
                  item={item}
                  onAdd={onAdd}
                  onRemove={onRemove}
                />
              ))}
            </div>

            {/* Total + Checkout */}
            <div className="p-6 border-t border-base-200 space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-base opacity-70">Toplam</span>
                <span className="text-2xl font-bold">{total.toFixed(2)} ₺</span>
              </div>
              <button
                className="btn btn-primary btn-lg w-full rounded-2xl text-lg"
                onClick={handleCheckout}
              >
                Siparişi Onayla
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
