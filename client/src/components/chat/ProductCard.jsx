import "./ProductCard.css";

export default function ProductCard({ product }) {
  return (
    <div className="product-card">

      <div className="product-image">
        <img
          src={`http://127.0.0.1:8000/images/${product.image}`}
          alt={product.name}
        />
      </div>

      <div className="product-content">

        <h3>{product.name}</h3>

        <div className="product-info">

          <span className="category">
            {product.category}
          </span>

          <span className="price">
            Rs. {Number(product.price).toLocaleString()}
          </span>

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

        <button className="details-btn">
          View Details
        </button>

      </div>

    </div>
  );
}