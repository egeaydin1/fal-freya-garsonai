import ProductForm from "./ProductForm";
import ProductCard from "./ProductCard";

export default function ProductsList({
  products,
  onCreateProduct,
  onDeleteProduct,
}) {
  return (
    <div>
      <ProductForm onSubmit={onCreateProduct} />

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {products.map((product) => (
          <ProductCard
            key={product.id}
            product={product}
            onDelete={onDeleteProduct}
          />
        ))}
      </div>
    </div>
  );
}
