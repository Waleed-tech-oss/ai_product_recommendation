import "./ProductSidebar.css";
import ProductGrid from "./ProductGrid";
import FilterChips from "./FilterChips";

export default function ProductSidebar({
  products,
  filters = {},
}) {
  return (
    <aside className="product-sidebar">

      <div className="sidebar-header">

        <h2>🛍 Recommended Products</h2>

        <p>
          {products.length > 0
            ? `${products.length} AI Ranked Recommendation${
                products.length > 1 ? "s" : ""
              }`
            : "Search naturally to discover products"}
        </p>

      </div>

      <div className="sidebar-content">

        <FilterChips filters={filters} />

        {products.length === 0 ? (
          <div className="empty-products">

            <div className="empty-icon">🛍</div>

            <h3>No Recommendations Yet</h3>

            <p>
              Start chatting with AI to discover products.
            </p>

          </div>
        ) : (
          <ProductGrid products={products} />
        )}

      </div>

    </aside>
  );
}