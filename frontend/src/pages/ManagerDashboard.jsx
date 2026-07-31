import { useState, useEffect } from "react";
import Navbar from "../components/Navbar";
import Tabs from "../components/Tabs";
import TablesList from "../components/TablesList";
import ProductsList from "../components/ProductsList";
import OrdersList from "../components/OrdersList";

export default function ManagerDashboard({ onLogout }) {
  const [activeTab, setActiveTab] = useState("tables");
  const [tables, setTables] = useState([]);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);

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
    if (res.status === 401) {
      onLogout();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      setTables(data);
    }
  };

  const fetchProducts = async () => {
    const res = await fetch("http://localhost:8000/api/menu/products", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      onLogout();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      setProducts(data);
    }
  };

  const fetchOrders = async () => {
    const res = await fetch("http://localhost:8000/api/restaurant/orders", {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      onLogout();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      setOrders(data);
    }
  };

  const createTable = async (tableNumber) => {
    const res = await fetch("http://localhost:8000/api/restaurant/tables", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ table_number: parseInt(tableNumber) }),
    });

    if (res.status === 401) {
      onLogout();
      return;
    }
    if (res.ok) {
      fetchTables();
    } else {
      const error = await res.json();
      alert(error.detail || "Failed to create table");
    }
  };

  const deleteTable = async (id) => {
    const res = await fetch(
      `http://localhost:8000/api/restaurant/tables/${id}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      },
    );

    if (res.ok) {
      fetchTables();
    }
  };

  const createProduct = async (productData) => {
    const res = await fetch("http://localhost:8000/api/menu/products", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...productData,
        price: parseFloat(productData.price),
      }),
    });

    if (res.status === 401) {
      onLogout();
      return;
    }
    if (res.ok) {
      fetchProducts();
    } else {
      const error = await res.json();
      alert(error.detail || "Failed to create product");
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
      },
    );

    if (res.ok) {
      fetchOrders();
    }
  };

  return (
    <div className="min-h-screen bg-base-200">
      <Navbar restaurantName={restaurantName} onLogout={onLogout} />

      <div className="container mx-auto p-4">
        <Tabs activeTab={activeTab} setActiveTab={setActiveTab} />

        {activeTab === "tables" && (
          <TablesList
            tables={tables}
            onCreateTable={createTable}
            onDeleteTable={deleteTable}
          />
        )}

        {activeTab === "products" && (
          <ProductsList
            products={products}
            onCreateProduct={createProduct}
            onDeleteProduct={deleteProduct}
          />
        )}

        {activeTab === "orders" && (
          <OrdersList orders={orders} onUpdateStatus={updateOrderStatus} />
        )}
      </div>
    </div>
  );
}
