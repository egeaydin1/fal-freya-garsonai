export default function Tabs({ activeTab, setActiveTab }) {
  return (
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
  );
}
