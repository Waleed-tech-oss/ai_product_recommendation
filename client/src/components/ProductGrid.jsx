import ProductCard from "./ProductCard";
import "./ProductGrid.css";

function ProductGrid({ products }) {

  return (
    <div className="product-section">

      <h2>Recommended Products</h2>

      <div className="product-grid">

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

export default ProductGrid;