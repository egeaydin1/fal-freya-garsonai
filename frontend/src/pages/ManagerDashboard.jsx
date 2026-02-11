import { useState, useEffect } from "react";

export default function ManagerDashboard({ onLogout }) {
  const [activeTab, setActiveTab] = useState("tables");
  const [tables, setTables] = useState([]);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [newTableNumber, setNewTableNumber] = useState("");
  const [newProduct, setNewProduct] = useState({
    name: "",
    description: "",
    price: "",
    category: "",
  });

  const token = localStorage.getItem("token");
  const restaurantName = localStorage.getItem("restaurantName");

  useEffect(() => {
    fetchTables();
    fetchProducts();
    fetchOrders();
  }, []);

  const fetchTables = async () => {
    const res = await fetch("http://localhost:8000/api/restaurant/tables", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setTables(data);
    }
  };

  const fetchProducts = async () => {
    const res = await fetch("http://localhost:8000/api/menu/products", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setProducts(data);
    }
  };

  const fetchOrders = async () => {
    const res = await fetch("http://localhost:8000/api/restaurant/orders", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setOrders(data);
    }
  };

  const createTable = async (e) => {
    e.preventDefault();
    const res = await fetch("http://localhost:8000/api/restaurant/tables", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ table_number: parseInt(newTableNumber) }),
    });

    if (res.ok) {
      setNewTableNumber("");
      fetchTables();
    }
  };

  const deleteTable = async (id) => {
    const res = await fetch(
      `http://localhost:8000/api/restaurant/tables/${id}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }
    );

    if (res.ok) {
      fetchTables();
    }
  };

  const createProduct = async (e) => {
    e.preventDefault();
    const res = await fetch("http://localhost:8000/api/menu/products", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...newProduct,
        price: parseFloat(newProduct.price),
      }),
    });

    if (res.ok) {
      setNewProduct({ name: "", description: "", price: "", category: "" });
      fetchProducts();
    }
  };

  const deleteProduct = async (id) => {
    const res = await fetch(`http://localhost:8000/api/menu/products/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.ok) {
      fetchProducts();
    }
  };

  const updateOrderStatus = async (orderId, newStatus) => {
    const res = await fetch(
      `http://localhost:8000/api/restaurant/orders/${orderId}/status`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status: newStatus }),
      }
    );

    if (res.ok) {
      fetchOrders();
    }
  };

  const copyQR = (token) => {
    const url = `${window.location.origin}/menu/${token}`;
    navigator.clipboard.writeText(url);
    alert("QR link copied!");
  };

  return (
    <div className="min-h-screen bg-base-200">
      <div className="navbar bg-base-100 shadow-lg">
        <div className="flex-1">
          <a className="btn btn-ghost text-xl">{restaurantName}</a>
        </div>
        <div className="flex-none">
          <button className="btn btn-ghost" onClick={onLogout}>
            Logout
          </button>
        </div>
      </div>

      <div className="container mx-auto p-4">
        <div className="tabs tabs-boxed mb-4">
          <a
            className={`tab ${activeTab === "tables" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("tables")}
          >
            Tables
          </a>
          <a
            className={`tab ${activeTab === "products" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("products")}
          >
            Menu
          </a>
          <a
            className={`tab ${activeTab === "orders" ? "tab-active" : ""}`}
            onClick={() => setActiveTab("orders")}
          >
            Orders
          </a>
        </div>

        {activeTab === "tables" && (
          <div>
            <form onSubmit={createTable} className="card bg-base-100 p-4 mb-4">
              <h3 className="text-lg font-bold mb-2">Add Table</h3>
              <div className="flex gap-2">
                <input
                  type="number"
                  placeholder="Table Number"
                  className="input input-bordered flex-1"
                  value={newTableNumber}
                  onChange={(e) => setNewTableNumber(e.target.value)}
                  required
                />
                <button type="submit" className="btn btn-primary">
                  Add
                </button>
              </div>
            </form>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {tables.map((table) => (
                <div key={table.id} className="card bg-base-100 shadow-xl">
                  <div className="card-body">
                    <h2 className="card-title">Table {table.table_number}</h2>
                    <div className="text-xs opacity-70 truncate">
                      {table.qr_token}
                    </div>
                    <div className="card-actions justify-end mt-2">
                      <button
                        className="btn btn-sm btn-primary"
                        onClick={() => copyQR(table.qr_token)}
                      >
                        Copy Link
                      </button>
                      <button
                        className="btn btn-sm btn-error"
                        onClick={() => deleteTable(table.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "products" && (
          <div>
            <form
              onSubmit={createProduct}
              className="card bg-base-100 p-4 mb-4"
            >
              <h3 className="text-lg font-bold mb-2">Add Product</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                <input
                  type="text"
                  placeholder="Name"
                  className="input input-bordered"
                  value={newProduct.name}
                  onChange={(e) =>
                    setNewProduct({ ...newProduct, name: e.target.value })
                  }
                  required
                />
                <input
                  type="number"
                  step="0.01"
                  placeholder="Price"
                  className="input input-bordered"
                  value={newProduct.price}
                  onChange={(e) =>
                    setNewProduct({ ...newProduct, price: e.target.value })
                  }
                  required
                />
                <input
                  type="text"
                  placeholder="Category"
                  className="input input-bordered"
                  value={newProduct.category}
                  onChange={(e) =>
                    setNewProduct({ ...newProduct, category: e.target.value })
                  }
                />
                <input
                  type="text"
                  placeholder="Description"
                  className="input input-bordered"
                  value={newProduct.description}
                  onChange={(e) =>
                    setNewProduct({
                      ...newProduct,
                      description: e.target.value,
                    })
                  }
                />
              </div>
              <button type="submit" className="btn btn-primary mt-2">
                Add Product
              </button>
            </form>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {products.map((product) => (
                <div key={product.id} className="card bg-base-100 shadow-xl">
                  <div className="card-body">
                    <h2 className="card-title">{product.name}</h2>
                    <p className="text-sm opacity-70">{product.description}</p>
                    <p className="text-lg font-bold">{product.price} TL</p>
                    <div className="badge badge-outline">{product.category}</div>
                    <div className="card-actions justify-end">
                      <button
                        className="btn btn-sm btn-error"
                        onClick={() => deleteProduct(product.id)}
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === "orders" && (
          <div className="space-y-4">
            {orders.map((order) => (
              <div key={order.id} className="card bg-base-100 shadow-xl">
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
                        onClick={() =>
                          updateOrderStatus(order.id, "preparing")
                        }
                        disabled={order.status === "preparing"}
                      >
                        Preparing
                      </button>
                      <button
                        className="btn btn-sm"
                        onClick={() =>
                          updateOrderStatus(order.id, "delivered")
                        }
                        disabled={order.status === "delivered"}
                      >
                        Delivered
                      </button>
                      <button
                        className="btn btn-sm"
                        onClick={() => updateOrderStatus(order.id, "paid")}
                        disabled={order.status === "paid"}
                      >
                        Paid
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}

            {orders.length === 0 && (
              <div className="text-center opacity-50 py-8">No orders yet</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
