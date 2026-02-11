// API service for frontend
const API_BASE = "http://localhost:8000";

export const api = {
  // Auth
  register: async (name, email, password) => {
    const res = await fetch(`${API_BASE}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, email, password }),
    });
    return res.json();
  },

  login: async (email, password) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    return res.json();
  },

  // Restaurant (requires token)
  getTables: async (token) => {
    const res = await fetch(`${API_BASE}/api/restaurant/tables`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.json();
  },

  createTable: async (token, tableNumber) => {
    const res = await fetch(`${API_BASE}/api/restaurant/tables`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ table_number: tableNumber }),
    });
    return res.json();
  },

  deleteTable: async (token, tableId) => {
    const res = await fetch(`${API_BASE}/api/restaurant/tables/${tableId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.json();
  },

  getOrders: async (token) => {
    const res = await fetch(`${API_BASE}/api/restaurant/orders`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.json();
  },

  updateOrderStatus: async (token, orderId, status) => {
    const res = await fetch(
      `${API_BASE}/api/restaurant/orders/${orderId}/status`,
      {
        method: "PATCH",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ status }),
      }
    );
    return res.json();
  },

  // Menu
  getProducts: async (token) => {
    const res = await fetch(`${API_BASE}/api/menu/products`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.json();
  },

  createProduct: async (token, product) => {
    const res = await fetch(`${API_BASE}/api/menu/products`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(product),
    });
    return res.json();
  },

  deleteProduct: async (token, productId) => {
    const res = await fetch(`${API_BASE}/api/menu/products/${productId}`, {
      method: "DELETE",
      headers: { Authorization: `Bearer ${token}` },
    });
    return res.json();
  },

  // Public menu
  getMenuByQR: async (qrToken) => {
    const res = await fetch(`${API_BASE}/api/menu/${qrToken}`);
    return res.json();
  },

  checkout: async (qrToken, items) => {
    const res = await fetch(`${API_BASE}/api/menu/${qrToken}/checkout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ items }),
    });
    return res.json();
  },

  // WebSocket voice connection
  connectVoice: (qrToken) => {
    return new WebSocket(`ws://localhost:8000/ws/voice/${qrToken}`);
  },
};
