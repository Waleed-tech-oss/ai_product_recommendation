import "./ProductCard.css";

function ProductCard({ product }) {
  return (
    <div className="product-card">

      <img
        src={product.imageUrl}
        alt={product.name}
      />

      <div className="card-body">

        <h3>{product.name}</h3>

        <p>
          <strong>Category:</strong> {product.category}
        </p>

        <p>
          <strong>Price:</strong> Rs. {product.price}
        </p>

        <span className="match-badge">
          ⭐ {Math.round(product.score * 100)}% Match
        </span>

      </div>

    </div>
  );
}

export default ProductCard;