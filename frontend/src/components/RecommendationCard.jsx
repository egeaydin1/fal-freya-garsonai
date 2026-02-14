import { useState, useEffect } from "react";

import { config } from "../config";
const API_BASE = config.API_BASE;

/**
 * Apple-style animated recommendation popup
 * Cascade reveal: photo → name → description → allergens → price → buttons
 */
export default function RecommendationPopup({ product, onAdd, onClose }) {
  const [step, setStep] = useState(0);
  const [isClosing, setIsClosing] = useState(false);

  useEffect(() => {
    if (!product) return;
    setStep(0);
    // Cascade reveal: each element appears 200ms after the previous
    const timers = [
      setTimeout(() => setStep(1), 100),   // photo
      setTimeout(() => setStep(2), 400),   // name
      setTimeout(() => setStep(3), 650),   // description
      setTimeout(() => setStep(4), 900),   // allergens + price
      setTimeout(() => setStep(5), 1150),  // buttons
    ];
    return () => timers.forEach(clearTimeout);
  }, [product]);

  if (!product) return null;

  const imageUrl = product.image_url
    ? product.image_url.startsWith("http")
      ? product.image_url
      : `${API_BASE}${product.image_url}`
    : null;

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(onClose, 350);
  };

  const handleAdd = () => {
    onAdd(product);
    handleClose();
  };

  return (
    <div className="fixed inset-0 z-[90] flex items-end sm:items-center justify-center">
      {/* Backdrop */}
      <div
        className={`absolute inset-0 bg-black/50 backdrop-blur-md ${isClosing ? "opacity-0" : "animate-overlay-in"}`}
        style={{ transition: "opacity 0.3s ease" }}
        onClick={handleClose}
      />

      {/* Card */}
      <div
        className={`relative w-full max-w-md mx-4 mb-4 sm:mb-0 bg-base-100 rounded-3xl shadow-2xl overflow-hidden ${
          isClosing ? "scale-90 opacity-0" : "animate-pop-bounce"
        }`}
        style={{ transition: isClosing ? "all 0.35s cubic-bezier(.22,1,.36,1)" : undefined }}
      >
        {/* Close button */}
        <button
          className="absolute top-4 right-4 z-10 btn btn-ghost btn-sm btn-circle bg-base-100/80 backdrop-blur"
          onClick={handleClose}
        >
          ✕
        </button>

        {/* Badge */}
        <div className="absolute top-4 left-4 z-10">
          <span className="badge badge-primary gap-1 shadow-lg animate-slide-down">
            ✨ Öneri
          </span>
        </div>

        {/* Photo */}
        <div className={`transition-all duration-700 ease-out ${step >= 1 ? "opacity-100 scale-100" : "opacity-0 scale-105"}`}>
          {imageUrl ? (
            <div className="h-56 overflow-hidden">
              <img
                src={imageUrl}
                alt={product.name}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-x-0 bottom-0 h-32 bg-gradient-to-t from-base-100 to-transparent pointer-events-none" style={{ top: "auto", bottom: 0, position: "relative", marginTop: "-8rem" }} />
            </div>
          ) : (
            <div className="h-40 bg-gradient-to-br from-primary/20 to-secondary/20 flex items-center justify-center">
              <span className="text-7xl animate-breathe">🍽️</span>
            </div>
          )}
        </div>

        <div className="px-6 pb-6 -mt-4 relative z-10">
          {/* Name */}
          <div className={`transition-all duration-500 ease-out ${step >= 2 ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>
            <h3 className="text-2xl font-bold mb-1">{product.name}</h3>
          </div>

          {/* Description */}
          <div className={`transition-all duration-500 ease-out ${step >= 3 ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>
            {product.description && (
              <p className="text-base opacity-70 mb-3 leading-relaxed">{product.description}</p>
            )}
            {product.reason && (
              <div className="flex items-start gap-2 p-3 bg-primary/10 rounded-2xl mb-3">
                <span className="text-lg">💡</span>
                <p className="text-sm opacity-80">{product.reason}</p>
              </div>
            )}
          </div>

          {/* Allergens + Price */}
          <div className={`transition-all duration-500 ease-out ${step >= 4 ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>
            {product.allergens && product.allergens.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mb-3">
                {product.allergens.map((a) => (
                  <span key={a.id} className="badge badge-warning badge-sm gap-1">
                    {a.icon || "⚠️"} {a.name}
                  </span>
                ))}
              </div>
            )}
            <div className="text-3xl font-bold text-primary mb-4">
              {product.price?.toFixed?.(2) || product.price} ₺
            </div>
          </div>

          {/* Buttons */}
          <div className={`flex gap-3 transition-all duration-500 ease-out ${step >= 5 ? "opacity-100 translate-y-0" : "opacity-0 translate-y-4"}`}>
            <button
              className="btn btn-outline flex-1 rounded-2xl"
              onClick={handleClose}
            >
              Kapat
            </button>
            <button
              className="btn btn-primary flex-1 rounded-2xl"
              onClick={handleAdd}
            >
              Sepete Ekle
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
