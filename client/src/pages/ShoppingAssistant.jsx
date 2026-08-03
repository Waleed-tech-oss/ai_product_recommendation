import { useState } from "react";
import axios from "axios";

import "./ShoppingAssistant.css";

import Navbar from "../components/Navbar";
import ChatWindow from "../components/chat/ChatWindow";
import ChatInput from "../components/chat/ChatInput";
import ProductSidebar from "../components/chat/ProductSidebar";

import {
  sendImageMessage,
  sendMessage,
} from "../services/chatApi";


function fileToDataUrl(file) {
  return new Promise(
    (resolve, reject) => {
      const reader = new FileReader();

      reader.onload = () =>
        resolve(reader.result);

      reader.onerror = () =>
        reject(
          new Error(
            "Image preview could not be generated."
          )
        );

      reader.readAsDataURL(file);
    }
  );
}


function createAssistantMessage(data) {
  return {
    id: crypto.randomUUID(),
    sender: "assistant",
    text:
      data.message ||
      `I found ${
        data.totalFilteredProducts ?? 0
      } matching products.`,
    timestamp: Date.now(),

    intent: data.intent,
    clarificationType:
      data.clarificationType,
    options: Array.isArray(data.options)
      ? data.options
      : [],

    comparison: data.comparison || null,
    comparisonTargets:
      data.comparisonTargets || [],
    matchedProducts:
      data.matchedProducts || [],
    unmatchedTargets:
      data.unmatchedTargets || [],

    queryCorrections:
      data.queryCorrections || [],
    normalizedQuery:
      data.normalizedQuery || null,
    responseLanguage:
      data.responseLanguage || "english",

    searchMode:
      data.searchMode || null,
    rankingWeights:
      data.rankingWeights || null,
    imageMetadata:
      data.imageMetadata || null,
  };
}


function getApiErrorMessage(
  error
) {
  return (
    error?.response?.data?.detail ||
    error?.message ||
    "Something went wrong while processing your request."
  );
}


export default function ShoppingAssistant() {
  const [sessionId] = useState(
    () => crypto.randomUUID()
  );

  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      sender: "assistant",
      text:
        "👋 Hello! I'm your AI Shopping Assistant.\n" +
        "Tell me what product you're looking for, " +
        "or upload a product image.",
      timestamp: Date.now(),
    },
  ]);

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({});

  function applyBackendResponse(
    data
  ) {
    setMessages((previous) => [
      ...previous,
      createAssistantMessage(data),
    ]);

    if (
      Array.isArray(
        data.recommendedProducts
      )
    ) {
      setProducts(
        data.recommendedProducts
      );
    }

    setFilters(data.filters || {});

    console.log(
      "Chat response:",
      data
    );
  }

  // ------------------------------------------
  // Normal text chat
  // ------------------------------------------

  const handleSend = async (
    rawText
  ) => {
    const query =
      typeof rawText === "string"
        ? rawText.trim()
        : "";

    if (!query || loading) {
      return;
    }

    setMessages((previous) => [
      ...previous,
      {
        id: crypto.randomUUID(),
        sender: "user",
        text: query,
        timestamp: Date.now(),
      },
    ]);

    setLoading(true);

    try {
      const data = await sendMessage(
        sessionId,
        query
      );

      applyBackendResponse(data);
    } catch (error) {
      console.error(
        "Chat request failed:",
        error
      );

      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          sender: "assistant",
          text: getApiErrorMessage(
            error
          ),
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // ------------------------------------------
  // Image-only / image-text hybrid chat
  // ------------------------------------------

  const handleImageSend = async (
    rawText,
    imageFile
  ) => {
    if (
      !(imageFile instanceof File)
      || loading
    ) {
      return;
    }

    const query =
      typeof rawText === "string"
        ? rawText.trim()
        : "";

    let stableImagePreview = "";

    try {
      stableImagePreview =
        await fileToDataUrl(
          imageFile
        );
    } catch (error) {
      console.error(
        "Image preview error:",
        error
      );
    }

    setMessages((previous) => [
      ...previous,
      {
        id: crypto.randomUUID(),
        sender: "user",
        text:
          query ||
          "Find products visually similar to this image.",
        imagePreview:
          stableImagePreview,
        timestamp: Date.now(),
      },
    ]);

    setLoading(true);

    try {
      const data =
        await sendImageMessage(
          sessionId,
          query,
          imageFile
        );

      applyBackendResponse(data);
    } catch (error) {
      console.error(
        "Image search failed:",
        error
      );

      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          sender: "assistant",
          text: getApiErrorMessage(
            error
          ),
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  // ------------------------------------------
  // More Like This
  // ------------------------------------------

  const handleMoreLikeThis = async (
    productId
  ) => {
    try {
      setLoading(true);

      const response = await axios.post(
        "http://127.0.0.1:8000/more-like-this",
        {
          productId,
        }
      );

      setProducts(
        response.data
          .recommendedProducts || []
      );
    } catch (error) {
      console.error(
        "More Like This Error:",
        error
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <Navbar />

      <div className="shopping-page">
        <div className="shopping-wrapper">
          <header className="shopping-header">
            <h1>
              🤖 AI Shopping Assistant
            </h1>

            <p>
              Search naturally with text
              or a product image
            </p>
          </header>

          <div className="shopping-layout">
            <div className="chat-section">
              <ChatWindow
                messages={messages}
                loading={loading}
                onAction={handleSend}
              />

              <ChatInput
                onSend={handleSend}
                onImageSend={
                  handleImageSend
                }
                loading={loading}
              />
            </div>

            <div className="sidebar-section">
              <ProductSidebar
                products={products}
                filters={filters}
                onMoreLikeThis={
                  handleMoreLikeThis
                }
                loading={loading}
              />
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
