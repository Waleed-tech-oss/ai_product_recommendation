import "./ProductCard.css";

export default function ProductCard({
  product,
  onMoreLikeThis,
  loading,
}) {
  return (
    <div className="product-card">

      <div className="product-image">
        <img
          src={product.image_url}
          alt={product.title}
        />
      </div>

      <div className="product-content">

        <h3>{product.title}</h3>

        <div className="product-info">

          <span className="category">
            {product.product_type}
          </span>

          <span className="price">
            ${Number(product.price).toFixed(2)}
          </span>

          <p className="vendor">
               {product.vendor}
           </p>

        </div>

        {product.score && (

          <div className="match-section">

            <div className="match-header">

              <span>AI Match</span>

              <span>
                {(product.score * 100).toFixed(1)}%
              </span>

            </div>

            <div className="progress-bar">

              <div
                className="progress-fill"
                style={{
                  width: `${product.score * 100}%`,
                }}
              />

            </div>

          </div>

        )}

        {product.explanation && (

          <div className="ai-box">

            <h4>🤖 Why AI Recommended</h4>

            <p>{product.explanation.summary}</p>

            {product.explanation.reasons?.length > 0 && (

              <ul>

                {product.explanation.reasons.map((reason, index) => (
                  <li key={index}>
                    {reason}
                  </li>
                ))}

              </ul>

            )}

          </div>

        )}

        {/* More Like This Reason */}

        {product.reason && (

          <div className="ai-box">

            <h4>✨ Why Similar?</h4>

            <p>{product.reason}</p>

          </div>

        )}

        <div className="product-actions">

          <button className="details-btn">
            View Details
          </button>

          {/* <button
    className="more-like-btn"
    disabled={loading}
    onClick={() => onMoreLikeThis(product.id)}
>
    {loading ? "Loading..." : "🔍 More Like This"}
</button> */}

        </div>

      </div>

    </div>
  );
}