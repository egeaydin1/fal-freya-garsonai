import { useState, useRef } from "react";

import { config } from "../config";
const API_BASE = config.API_BASE;

export default function ProductForm({ onSubmit, allergens = [] }) {
  const [newProduct, setNewProduct] = useState({
    name: "",
    description: "",
    price: "",
    category: "",
    image_url: "",
    allergen_ids: [],
  });
  const [imagePreview, setImagePreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);

  const handleImageChange = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    // Preview
    const reader = new FileReader();
    reader.onload = (ev) => setImagePreview(ev.target.result);
    reader.readAsDataURL(file);

    // Upload
    setUploading(true);
    try {
      const token = localStorage.getItem("token");
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_BASE}/api/menu/upload-image`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: formData,
      });
      const data = await res.json();
      if (data.image_url) {
        setNewProduct((prev) => ({ ...prev, image_url: data.image_url }));
      }
    } catch (err) {
      console.error("Upload failed:", err);
    } finally {
      setUploading(false);
    }
  };

  const toggleAllergen = (allergenId) => {
    setNewProduct((prev) => {
      const ids = prev.allergen_ids.includes(allergenId)
        ? prev.allergen_ids.filter((id) => id !== allergenId)
        : [...prev.allergen_ids, allergenId];
      return { ...prev, allergen_ids: ids };
    });
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit(newProduct);
    setNewProduct({
      name: "",
      description: "",
      price: "",
      category: "",
      image_url: "",
      allergen_ids: [],
    });
    setImagePreview(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  return (
    <form onSubmit={handleSubmit} className="card bg-base-100 p-4 mb-4">
      <h3 className="text-lg font-bold mb-2">Ürün Ekle</h3>

      {/* Image Upload */}
      <div className="mb-3">
        <label className="label">
          <span className="label-text font-semibold">Ürün Fotoğrafı</span>
        </label>
        <div className="flex items-center gap-4">
          {imagePreview ? (
            <div className="avatar">
              <div className="w-20 rounded-lg">
                <img src={imagePreview} alt="Preview" />
              </div>
            </div>
          ) : (
            <div className="w-20 h-20 rounded-lg bg-base-200 flex items-center justify-center text-3xl">
              📷
            </div>
          )}
          <div>
            <input
              type="file"
              ref={fileInputRef}
              accept="image/jpeg,image/png,image/webp,image/gif"
              className="file-input file-input-bordered file-input-sm w-full max-w-xs"
              onChange={handleImageChange}
            />
            {uploading && (
              <span className="loading loading-spinner loading-sm ml-2"></span>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
        <input
          type="text"
          placeholder="Ürün Adı"
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
          placeholder="Fiyat (₺)"
          className="input input-bordered"
          value={newProduct.price}
          onChange={(e) =>
            setNewProduct({ ...newProduct, price: e.target.value })
          }
          required
        />
        <input
          type="text"
          placeholder="Kategori"
          className="input input-bordered"
          value={newProduct.category}
          onChange={(e) =>
            setNewProduct({ ...newProduct, category: e.target.value })
          }
        />
        <textarea
          placeholder="Ürün Açıklaması"
          className="textarea textarea-bordered"
          value={newProduct.description}
          onChange={(e) =>
            setNewProduct({
              ...newProduct,
              description: e.target.value,
            })
          }
          rows={2}
        />
      </div>

      {/* Allergen Checkboxes */}
      {allergens.length > 0 && (
        <div className="mt-3">
          <label className="label">
            <span className="label-text font-semibold">Alerjenler</span>
          </label>
          <div className="flex flex-wrap gap-2">
            {allergens.map((allergen) => (
              <label
                key={allergen.id}
                className={`cursor-pointer flex items-center gap-1 px-3 py-1.5 rounded-full border text-sm transition-colors ${
                  newProduct.allergen_ids.includes(allergen.id)
                    ? "bg-error text-error-content border-error"
                    : "bg-base-200 border-base-300 hover:bg-base-300"
                }`}
              >
                <input
                  type="checkbox"
                  className="checkbox checkbox-xs hidden"
                  checked={newProduct.allergen_ids.includes(allergen.id)}
                  onChange={() => toggleAllergen(allergen.id)}
                />
                <span>{allergen.icon || "⚠️"}</span>
                <span>{allergen.name}</span>
              </label>
            ))}
          </div>
        </div>
      )}

      <button
        type="submit"
        className="btn btn-primary mt-3"
        disabled={uploading}
      >
        Ürün Ekle
      </button>
    </form>
  );
}
