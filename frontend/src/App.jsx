import { Routes, Route, Navigate } from "react-router-dom";
import { useState } from "react";
import LoginPage from "./components/LoginPage";
import ManagerDashboard from "./pages/ManagerDashboard";
import Menu from "./pages/Menu";
import VoiceAI from "./pages/VoiceAI";

function App() {
  const [token, setToken] = useState(localStorage.getItem("token"));

  const handleLogin = (newToken, restaurantId, restaurantName) => {
    localStorage.setItem("token", newToken);
    localStorage.setItem("restaurantId", restaurantId);
    localStorage.setItem("restaurantName", restaurantName);
    setToken(newToken);
  };

  const handleLogout = () => {
    localStorage.clear();
    setToken(null);
  };

  return (
    <Routes>
      <Route path="/" element={<LoginPage onLogin={handleLogin} />} />
      <Route
        path="/panel"
        element={
          token ? (
            <ManagerDashboard onLogout={handleLogout} />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route path="/menu/:qrToken" element={<Menu />} />
      <Route path="/voice/:qrToken" element={<VoiceAI />} />
    </Routes>
  );
}

export default App;
