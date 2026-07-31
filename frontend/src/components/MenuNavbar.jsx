export default function MenuNavbar({
  qrToken,
  cartCount,
  onVoiceClick,
  onCartClick,
}) {
  return (
    <div className="navbar bg-base-100 shadow-lg">
      <div className="flex-1">
        <a className="btn btn-ghost text-xl">Menu</a>
      </div>
      <div className="flex-none gap-2">
        <button className="btn btn-primary" onClick={onVoiceClick}>
          🎤 Voice Order
        </button>
        <button
          className="btn btn-circle btn-ghost relative"
          onClick={onCartClick}
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
          {cartCount > 0 && (
            <span className="badge badge-sm badge-primary absolute -top-2 -right-2">
              {cartCount}
            </span>
          )}
        </button>
      </div>
    </div>
  );
}
