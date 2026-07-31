import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import MenuNavbar from "../components/MenuNavbar";
import MenuProductCard from "../components/MenuProductCard";
import Cart from "../components/Cart";

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
            : item,
        ),
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
            : item,
        ),
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
      },
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
    0,
  );

  return (
    <div className="min-h-screen bg-base-200">
      <MenuNavbar
        qrToken={qrToken}
        cartCount={cart.length}
        onVoiceClick={() => navigate(`/voice/${qrToken}`)}
        onCartClick={() => setShowCart(!showCart)}
      />

      <div className="container mx-auto p-4">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {products.map((product) => (
            <MenuProductCard
              key={product.id}
              product={product}
              onAdd={addToCart}
            />
          ))}
        </div>
      </div>

      {showCart && (
        <Cart
          cart={cart}
          total={total}
          onAdd={addToCart}
          onRemove={removeFromCart}
          onCheckout={checkout}
          onClose={() => setShowCart(false)}
        />
      )}
    </div>
  );
}
