import { useState } from "react";
import "./ShoppingAssistant.css";
import Navbar from "../components/Navbar";
import ChatWindow from "../components/chat/ChatWindow";
import ChatInput from "../components/chat/ChatInput";
import ProductSidebar from "../components/chat/ProductSidebar";

export default function ShoppingAssistant() {
  const [messages, setMessages] = useState([
    {
      id: 1,
      sender: "assistant",
      text: "👋 Hello! I'm your AI Shopping Assistant.\nTell me what product you're looking for.",
    },
  ]);

  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({});

  return (
    <>
<Navbar/>

<div className="shopping-page">

    <div className="shopping-wrapper">

        <header className="shopping-header">

            <h1>
                🤖 AI Shopping Assistant
            </h1>

            <p>
                Search products naturally using AI
            </p>

        </header>

        <div className="shopping-layout">

            <div className="chat-section">

                <ChatWindow
                    messages={messages}
                    loading={loading}
                />

                <ChatInput
                    messages={messages}
                    setMessages={setMessages}
                    setProducts={setProducts}
                    setFilters={setFilters}
                    loading={loading}
                    setLoading={setLoading}
                />

            </div>

            <div className="sidebar-section">

                <ProductSidebar
                    products={products}
                    filters={filters}
                />

            </div>

        </div>

    </div>

</div>

</>
  );
}