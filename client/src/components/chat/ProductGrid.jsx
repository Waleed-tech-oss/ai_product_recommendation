import "./ProductGrid.css";
import ProductCard from "./ProductCard";

export default function ProductGrid({ products }) {
  return (
    <div className="product-grid">

      <h2 className="grid-title">
        Recommended Products
      </h2>

      <div className="products-list">

        {products.map((product) => (
          <ProductCard
            key={product._id}
            product={product}
          />
        ))}

      </div>

    </div>
  );
}