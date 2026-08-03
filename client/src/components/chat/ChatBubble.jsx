import { useMemo, useState } from "react";
import {
  Bot,
  Check,
  User,
} from "lucide-react";

import "./ChatBubble.css";
import "./ChatBubbleFeatures.css";
import "./ChatImageMessage.css";


function formatValue(
  field,
  value
) {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "Not available";
  }

  if (field === "price") {
    const numericValue = Number(value);

    return Number.isFinite(numericValue)
      ? `$${numericValue.toFixed(2)}`
      : String(value);
  }

  return String(value);
}


function ComparisonTable({
  comparison,
}) {
  const products =
    comparison?.products || [];
  const rows = comparison?.rows || [];
  const priceSummary =
    comparison?.priceSummary || {};
  const aiSummary =
    comparison?.aiSummary || null;

  if (products.length < 2) {
    return null;
  }

  const productMap = new Map(
    products.map((product) => [
      String(product.id),
      product,
    ])
  );

  return (
    <div className="comparison-panel">
      <div className="comparison-title">
        Product comparison
      </div>

      <div className="comparison-table-wrap">
        <table className="comparison-table">
          <thead>
            <tr>
              <th>Feature</th>

              {products.map(
                (product) => (
                  <th key={product.id}>
                    {product.title}
                  </th>
                )
              )}
            </tr>
          </thead>

          <tbody>
            {rows.map((row) => (
              <tr key={row.field}>
                <td>{row.label}</td>

                {products.map(
                  (product) => {
                    const matchingValue =
                      row.values?.find(
                        (item) =>
                          String(
                            item.productId
                          ) ===
                          String(product.id)
                      );

                    return (
                      <td
                        key={`${row.field}-${product.id}`}
                      >
                        {formatValue(
                          row.field,
                          matchingValue?.value
                        )}
                      </td>
                    );
                  }
                )}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="comparison-highlights">
        {priceSummary.cheapestProductTitle && (
          <p>
            <strong>
              Lower-priced:
            </strong>{" "}
            {
              priceSummary.cheapestProductTitle
            }
          </p>
        )}

        {priceSummary.mostExpensiveProductTitle && (
          <p>
            <strong>
              Higher-priced:
            </strong>{" "}
            {
              priceSummary
                .mostExpensiveProductTitle
            }
          </p>
        )}

        {priceSummary.priceDifference !==
          null &&
          priceSummary.priceDifference !==
            undefined && (
            <p>
              <strong>
                Price difference:
              </strong>{" "}
              $
              {Number(
                priceSummary.priceDifference
              ).toFixed(2)}
            </p>
          )}
      </div>

      {aiSummary && (
        <div className="comparison-summary">
          <p>{aiSummary.summary}</p>

          {Array.isArray(
            aiSummary.keyPoints
          ) &&
            aiSummary.keyPoints.length >
              0 && (
              <ul>
                {aiSummary.keyPoints.map(
                  (point, index) => (
                    <li key={index}>
                      {point}
                    </li>
                  )
                )}
              </ul>
            )}
        </div>
      )}

      {Array.isArray(
        comparison.missingFields
      ) &&
        comparison.missingFields.length >
          0 && (
          <p className="comparison-missing">
            Not currently available:{" "}
            {comparison.missingFields.join(
              ", "
            )}
          </p>
        )}

      {/* Prevent unused-variable warnings if
          a linter treats productMap strictly. */}
      {productMap.size < 0 && null}
    </div>
  );
}


function ClarificationOptions({
  options,
  onAction,
}) {
  if (!Array.isArray(options)) {
    return null;
  }

  const validOptions = options.filter(
    (option) =>
      option &&
      typeof option.message === "string" &&
      option.message.trim()
  );

  if (validOptions.length === 0) {
    return null;
  }

  return (
    <div className="clarification-options">
      {validOptions.map(
        (option, index) => (
          <button
            type="button"
            key={`${option.type || "option"}-${index}`}
            className="clarification-option"
            onClick={() =>
              onAction(option.message)
            }
          >
            <span>
              {option.label ||
                option.message}
            </span>

            <Check size={16} />
          </button>
        )
      )}
    </div>
  );
}


function ComparisonSuggestions({
  matchedProducts,
  unmatchedTargets,
  onAction,
}) {
  const initialTitles = useMemo(
    () =>
      (matchedProducts || [])
        .map((product) => product.title)
        .filter(Boolean),
    [matchedProducts]
  );

  const [
    selectedTitles,
    setSelectedTitles,
  ] = useState([]);

  if (
    !Array.isArray(unmatchedTargets) ||
    unmatchedTargets.length === 0
  ) {
    return null;
  }

  const toggleTitle = (title) => {
    setSelectedTitles((previous) =>
      previous.includes(title)
        ? previous.filter(
            (item) => item !== title
          )
        : [...previous, title]
    );
  };

  const finalTitles = Array.from(
    new Set([
      ...initialTitles,
      ...selectedTitles,
    ])
  );

  return (
    <div className="comparison-suggestions">
      {unmatchedTargets.map(
        (targetItem, targetIndex) => (
          <div
            className="comparison-suggestion-group"
            key={`${targetItem.target}-${targetIndex}`}
          >
            <p>
              Suggestions for{" "}
              <strong>
                {targetItem.target}
              </strong>
            </p>

            <div className="comparison-suggestion-buttons">
              {(targetItem.suggestions ||
                []).map(
                (title) => {
                  const selected =
                    selectedTitles.includes(
                      title
                    );

                  return (
                    <button
                      type="button"
                      key={title}
                      className={
                        selected
                          ? "comparison-suggestion selected"
                          : "comparison-suggestion"
                      }
                      onClick={() =>
                        toggleTitle(title)
                      }
                    >
                      {title}
                    </button>
                  );
                }
              )}
            </div>
          </div>
        )
      )}

      {finalTitles.length >= 2 && (
        <button
          type="button"
          className="compare-selected-button"
          onClick={() =>
            onAction(
              `Compare ${finalTitles.join(
                " and "
              )}`
            )
          }
        >
          Compare selected products
        </button>
      )}
    </div>
  );
}


export default function ChatBubble({
  message,
  onAction,
}) {
  const isUser =
    message.sender === "user";

  const displayedTime =
    message.timestamp ||
    Date.now();

  return (
    <div
      className={`flex items-end gap-3 ${
        isUser
          ? "justify-end"
          : "justify-start"
      }`}
    >
      {!isUser && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500 text-black shadow-lg">
          <Bot size={20} />
        </div>
      )}

      <div
        className={`max-w-[85%] rounded-2xl px-5 py-4 shadow-lg ${
          isUser
            ? "rounded-br-md bg-cyan-500 text-black"
            : "rounded-bl-md border border-slate-700 bg-slate-800 text-white"
        }`}
      >
        {message.imagePreview && (
          <img
            className="chat-message-image"
            src={message.imagePreview}
            alt="User uploaded product"
          />
        )}

        {!isUser && message.searchMode && (
          <div className="visual-search-badge">
            {message.searchMode === "image_text_hybrid"
              ? "Image + Text Hybrid Search"
              : message.searchMode === "image_with_filters"
                ? "Image + Filter Search"
                : "Visual Image Search"}
          </div>
        )}

        <p className="whitespace-pre-wrap leading-7">
          {message.text}
        </p>

        {!isUser &&
          Array.isArray(
            message.queryCorrections
          ) &&
          message.queryCorrections
            .length > 0 && (
            <div className="query-corrections">
              Interpreted as:{" "}
              {message.queryCorrections
                .map(
                  (correction) =>
                    `${correction.from} → ${correction.to}`
                )
                .join(", ")}
            </div>
          )}

        {!isUser && (
          <ClarificationOptions
            options={message.options}
            onAction={onAction}
          />
        )}

        {!isUser && (
          <ComparisonSuggestions
            matchedProducts={
              message.matchedProducts
            }
            unmatchedTargets={
              message.unmatchedTargets
            }
            onAction={onAction}
          />
        )}

        {!isUser &&
          message.comparison && (
            <ComparisonTable
              comparison={
                message.comparison
              }
            />
          )}

        <div
          className={`mt-3 text-xs ${
            isUser
              ? "text-slate-800"
              : "text-slate-400"
          }`}
        >
          {new Date(
            displayedTime
          ).toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>

      {isUser && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-700 text-white shadow-lg">
          <User size={20} />
        </div>
      )}
    </div>
  );
}
