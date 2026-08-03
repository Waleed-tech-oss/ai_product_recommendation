import "./ProductCard.css";
import "./ProductCardHybrid.css";


function formatPrice(price) {
  const numericPrice = Number(price);

  return Number.isFinite(numericPrice)
    ? `$${numericPrice.toFixed(2)}`
    : "Price unavailable";
}


function percentage(score) {
  const numericScore = Number(score);

  if (!Number.isFinite(numericScore)) {
    return null;
  }

  return `${(
    Math.max(0, numericScore)
    * 100
  ).toFixed(1)}%`;
}


export default function ProductCard({
  product,
  onMoreLikeThis,
  loading,
}) {
  const overallMatch =
    percentage(product.score);
  const visualMatch =
    percentage(product.imageScore);
  const textMatch =
    percentage(product.textScore);

  return (
    <div className="product-card">
      <div className="product-image">
        <img
          src={product.image_url}
          alt={product.title}
          onError={(event) => {
            event.currentTarget.style.display =
              "none";
          }}
        />
      </div>

      <div className="product-content">
        <h3>{product.title}</h3>

        <div className="product-info">
          <span className="category">
            {product.product_type ||
              "Product"}
          </span>

          <span className="price">
            {formatPrice(
              product.price
            )}
          </span>

          {product.vendor && (
            <p className="vendor">
              {product.vendor}
            </p>
          )}
        </div>

        {overallMatch && (
          <div className="match-section">
            <div className="match-header">
              <span>AI Match</span>
              <span>
                {overallMatch}
              </span>
            </div>

            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{
                  width: overallMatch,
                }}
              />
            </div>
          </div>
        )}

        {(visualMatch ||
          textMatch) && (
          <div className="hybrid-score-grid">
            {visualMatch && (
              <div>
                <span>
                  Visual match
                </span>
                <strong>
                  {visualMatch}
                </strong>
              </div>
            )}

            {textMatch && (
              <div>
                <span>
                  Text match
                </span>
                <strong>
                  {textMatch}
                </strong>
              </div>
            )}
          </div>
        )}

        {product.explanation && (
          <div className="ai-box">
            <h4>
              🤖 Why AI Recommended
            </h4>

            <p>
              {
                product.explanation
                  .summary
              }
            </p>

            {product.explanation
              .reasons?.length > 0 && (
              <ul>
                {product.explanation
                  .reasons.map(
                    (reason, index) => (
                      <li key={index}>
                        {reason}
                      </li>
                    )
                  )}
              </ul>
            )}
          </div>
        )}

        {product.reason && (
          <div className="ai-box">
            <h4>
              ✨ Why Similar?
            </h4>

            <p>{product.reason}</p>
          </div>
        )}

        <div className="product-actions">
          <button className="details-btn">
            View Details
          </button>
        </div>
      </div>
    </div>
  );
}
