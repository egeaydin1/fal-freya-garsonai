import { useState, useEffect, useRef } from "react";
import Navbar from "../components/Navbar";
import Tabs from "../components/Tabs";
import TablesList from "../components/TablesList";
import ProductsList from "../components/ProductsList";
import OrdersList from "../components/OrdersList";

import { config } from "../config";

export default function ManagerDashboard({ onLogout }) {
  const [activeTab, setActiveTab] = useState("tables");
  const [tables, setTables] = useState([]);
  const [products, setProducts] = useState([]);
  const [orders, setOrders] = useState([]);
  const [allergens, setAllergens] = useState([]);
  const [dailyRevenue, setDailyRevenue] = useState(null);
  const wsRef = useRef(null);

  const token = localStorage.getItem("token");
  const restaurantName = localStorage.getItem("restaurantName");
  const restaurantId = localStorage.getItem("restaurantId");

  useEffect(() => {
    fetchTables();
    fetchProducts();
    fetchOrders();
    fetchAllergens();
    fetchDailyRevenue();
    
    // Request notification permission
    if ("Notification" in window && Notification.permission === "default") {
      Notification.requestPermission();
    }
    
    // Setup WebSocket connection
    if (restaurantId) {
      setupWebSocket();
    }
    
    return () => {
      // Cleanup WebSocket on unmount
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const setupWebSocket = () => {
    const ws = new WebSocket(`${config.WS_URL}/ws/restaurant/${restaurantId}`);
    
    ws.onopen = () => {
      console.log("WebSocket bağlantısı kuruldu");
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log("WebSocket mesajı alındı:", data);
      
      // Handle different message types
      if (data.type === "new_order") {
        // Refresh orders, tables and show notification
        fetchOrders();
        fetchTables();
        fetchDailyRevenue();
        showNotification(`Yeni sipariş! Masa ${data.table_number} - ${data.total_price.toFixed(2)} ₺`);
      } else if (data.type === "check_requested") {
        // Refresh tables to show check request
        fetchTables();
        showNotification(`Masa ${data.table_number} hesap istiyor!`);
      } else if (data.type === "order_update") {
        fetchOrders();
        fetchTables();
      }
    };
    
    ws.onerror = (error) => {
      console.error("WebSocket hatası:", error);
    };
    
    ws.onclose = () => {
      console.log("WebSocket bağlantısı kapandı");
      // Reconnect after 3 seconds
      setTimeout(() => {
        if (restaurantId) {
          setupWebSocket();
        }
      }, 3000);
    };
    
    wsRef.current = ws;
  };

  const showNotification = (message) => {
    // Create a browser notification if permitted
    if ("Notification" in window && Notification.permission === "granted") {
      new Notification("GarsonAI", { body: message });
    }
    // Also show alert (can be replaced with toast notification)
    // alert(message);
  };

  const fetchTables = async () => {
    const res = await fetch(`${config.API_BASE}/api/restaurant/tables`, {
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
    const res = await fetch(`${config.API_BASE}/api/menu/products`, {
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

  const fetchAllergens = async () => {
    const res = await fetch(`${config.API_BASE}/api/menu/allergens`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.status === 401) {
      onLogout();
      return;
    }
    if (res.ok) {
      const data = await res.json();
      setAllergens(data);
    }
  };

  const fetchOrders = async () => {
    const res = await fetch(`${config.API_BASE}/api/restaurant/orders`, {
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

  const fetchDailyRevenue = async () => {
    const res = await fetch(`${config.API_BASE}/api/restaurant/revenue/daily`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      const data = await res.json();
      setDailyRevenue(data);
    }
  };

  const createTable = async (tableNumber) => {
    const res = await fetch(`${config.API_BASE}/api/restaurant/tables`, {
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
      `${config.API_BASE}/api/restaurant/tables/${id}`,
      {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      },
    );

    if (res.ok) {
      fetchTables();
    }
  };

  const createAllergen = async (allergenData) => {
    const res = await fetch(`${config.API_BASE}/api/menu/allergens`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(allergenData),
    });
    if (res.ok) {
      fetchAllergens();
    }
  };

  const deleteAllergen = async (id) => {
    const res = await fetch(`${config.API_BASE}/api/menu/allergens/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    if (res.ok) {
      fetchAllergens();
      fetchProducts(); // refresh products since allergen refs may have changed
    }
  };

  const createProduct = async (productData) => {
    const res = await fetch(`${config.API_BASE}/api/menu/products`, {
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
    const res = await fetch(`${config.API_BASE}/api/menu/products/${id}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });

    if (res.ok) {
      fetchProducts();
    }
  };

  const updateOrderStatus = async (orderId, newStatus) => {
    const res = await fetch(
      `${config.API_BASE}/api/restaurant/orders/${orderId}/status`,
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
      fetchDailyRevenue();
    }
  };

  const markOrderPaid = async (orderId) => {
    const res = await fetch(
      `${config.API_BASE}/api/restaurant/orders/${orderId}/paid`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      },
    );

    if (res.ok) {
      fetchOrders();
      fetchTables();
      fetchDailyRevenue();
      alert("Ödeme alındı!");
    }
  };

  const payAllTable = async (tableId) => {
    if (!confirm("Bu masanın tüm siparişlerini ödenmiş olarak işaretlemek istiyor musunuz?")) return;
    const res = await fetch(
      `${config.API_BASE}/api/restaurant/tables/${tableId}/pay-all`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      },
    );
    if (res.ok) {
      const data = await res.json();
      fetchOrders();
      fetchTables();
      fetchDailyRevenue();
      alert(`Ödeme alındı! Toplam: ${data.total_paid.toFixed(2)} ₺ (${data.orders_count} sipariş)`);
    } else {
      const err = await res.json();
      alert(err.detail || "Ödeme işlemi başarısız!");
    }
  };

  return (
    <div className="min-h-screen bg-base-200">
      <Navbar restaurantName={restaurantName} onLogout={onLogout} />

      <div className="container mx-auto p-4">
        {/* Daily Revenue Summary */}
        {dailyRevenue && (
          <div className="stats shadow mb-4 w-full">
            <div className="stat">
              <div className="stat-title">Günlük Ciro</div>
              <div className="stat-value text-primary">
                {dailyRevenue.total_revenue.toFixed(2)} ₺
              </div>
              <div className="stat-desc">
                {dailyRevenue.total_orders} sipariş - Ortalama:{" "}
                {dailyRevenue.average_order.toFixed(2)} ₺
              </div>
            </div>
          </div>
        )}

        <Tabs activeTab={activeTab} setActiveTab={setActiveTab} />

        {activeTab === "tables" && (
          <TablesList
            tables={tables}
            onCreateTable={createTable}
            onDeleteTable={deleteTable}
            onPayAll={payAllTable}
          />
        )}

        {activeTab === "products" && (
          <ProductsList
            products={products}
            allergens={allergens}
            onCreateProduct={createProduct}
            onDeleteProduct={deleteProduct}
            onCreateAllergen={createAllergen}
            onDeleteAllergen={deleteAllergen}
          />
        )}

        {activeTab === "orders" && (
          <OrdersList 
            orders={orders} 
            onUpdateStatus={updateOrderStatus}
            onMarkPaid={markOrderPaid}
          />
        )}
      </div>
    </div>
  );
}
