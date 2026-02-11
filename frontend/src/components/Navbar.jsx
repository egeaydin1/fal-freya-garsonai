export default function Navbar({ restaurantName, onLogout }) {
  return (
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
  );
}
