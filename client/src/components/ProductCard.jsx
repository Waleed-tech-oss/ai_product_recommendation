import "./ProductCard.css";

function ProductCard({ product }) {
  return (
    <div className="product-card">

      <img
        src={product.image_url}
        alt={product.title}
        onError={(e) => {
          e.target.src =
            "https://placehold.co/400x400?text=No+Image";
        }}
      />

      <div className="card-body">

        <h3>{product.title}</h3>

        <p>
          <strong>Vendor:</strong> {product.vendor}
        </p>

        <p>
          <strong>Product Type:</strong> {product.product_type}
        </p>

        <p>
          <strong>Price:</strong> ${Number(product.price).toFixed(2)}
        </p>

        {product.score && (
          <span className="match-badge">
            ⭐ {Math.round(product.score * 100)}% Match
          </span>
        )}

        {product.explanation && (
          <div className="ai-box">

            <h4>🤖 AI Recommendation</h4>

            <p>{product.explanation.summary}</p>

            {product.explanation.reasons?.length > 0 && (
              <ul>
                {product.explanation.reasons.map((reason, index) => (
                  <li key={index}>{reason}</li>
                ))}
              </ul>
            )}

          </div>
        )}

      </div>

    </div>
  );
}

export default ProductCard;