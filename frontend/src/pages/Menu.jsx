import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";

export default function Menu() {
  const { qrToken } = useParams();
  const navigate = useNavigate();
  const [products, setProducts] = useState([]);
  const [cart, setCart] = useState([]);
  const [showCart, setShowCart] = useState(false);

  useEffect(() => {
    fetchMenu();
  }, [qrToken]);

  const fetchMenu = async () => {
    const res = await fetch(`http://localhost:8000/api/menu/${qrToken}`);
    if (res.ok) {
      const data = await res.json();
      setProducts(data);
    }
  };

  const addToCart = (product) => {
    const existing = cart.find((item) => item.product_id === product.id);
    if (existing) {
      setCart(
        cart.map((item) =>
          item.product_id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        )
      );
    } else {
      setCart([...cart, { product_id: product.id, quantity: 1, product }]);
    }
  };

  const removeFromCart = (productId) => {
    const existing = cart.find((item) => item.product_id === productId);
    if (existing && existing.quantity > 1) {
      setCart(
        cart.map((item) =>
          item.product_id === productId
            ? { ...item, quantity: item.quantity - 1 }
            : item
        )
      );
    } else {
      setCart(cart.filter((item) => item.product_id !== productId));
    }
  };

  const checkout = async () => {
    const items = cart.map((item) => ({
      product_id: item.product_id,
      quantity: item.quantity,
    }));

    const res = await fetch(
      `http://localhost:8000/api/menu/${qrToken}/checkout`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ items }),
      }
    );

    if (res.ok) {
      const data = await res.json();
      alert(`Order placed! Total: ${data.total} TL`);
      setCart([]);
      setShowCart(false);
    }
  };

  const total = cart.reduce(
    (sum, item) => sum + item.product.price * item.quantity,
    0
  );

  return (
    <div className="min-h-screen bg-base-200">
      <div className="navbar bg-base-100 shadow-lg">
        <div className="flex-1">
          <a className="btn btn-ghost text-xl">Menu</a>
        </div>
        <div className="flex-none gap-2">
          <button
            className="btn btn-primary"
            onClick={() => navigate(`/voice/${qrToken}`)}
          >
            🎤 Voice Order
          </button>
          <button
            className="btn btn-circle btn-ghost relative"
            onClick={() => setShowCart(!showCart)}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-6 w-6"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 11-4 0 2 2 0 014 0z"
              />
            </svg>
            {cart.length > 0 && (
              <span className="badge badge-sm badge-primary absolute -top-2 -right-2">
                {cart.length}
              </span>
            )}
          </button>
        </div>
      </div>

      <div className="container mx-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((product) => (
            <div key={product.id} className="card bg-base-100 shadow-xl">
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
                    onClick={() => addToCart(product)}
                  >
                    Add +
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {showCart && (
        <div className="drawer drawer-end drawer-open">
          <input type="checkbox" className="drawer-toggle" />
          <div className="drawer-side">
            <label className="drawer-overlay" onClick={() => setShowCart(false)}></label>
            <div className="menu p-4 w-80 min-h-full bg-base-100 text-base-content">
              <h2 className="text-2xl font-bold mb-4">Cart</h2>

              {cart.length === 0 ? (
                <p className="text-center opacity-50">Cart is empty</p>
              ) : (
                <>
                  <div className="space-y-2 flex-1">
                    {cart.map((item) => (
                      <div
                        key={item.product_id}
                        className="flex justify-between items-center p-2 bg-base-200 rounded"
                      >
                        <div className="flex-1">
                          <p className="font-bold">{item.product.name}</p>
                          <p className="text-sm opacity-70">
                            {item.product.price} TL x {item.quantity}
                          </p>
                        </div>
                        <div className="flex gap-2 items-center">
                          <button
                            className="btn btn-xs"
                            onClick={() => removeFromCart(item.product_id)}
                          >
                            -
                          </button>
                          <span>{item.quantity}</span>
                          <button
                            className="btn btn-xs"
                            onClick={() => addToCart(item.product)}
                          >
                            +
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="divider"></div>

                  <div className="text-xl font-bold mb-4">
                    Total: {total.toFixed(2)} TL
                  </div>

                  <button className="btn btn-primary w-full" onClick={checkout}>
                    Checkout
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
