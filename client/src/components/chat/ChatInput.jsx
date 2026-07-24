import { useState } from "react";
import "./ChatInput.css";
import { sendMessage } from "../../services/chatApi";

const SESSION_ID = crypto.randomUUID();

export default function ChatInput({
  messages,
  setMessages,
  setProducts,
  setFilters,
  loading,
  setLoading,
}) {
  const [text, setText] = useState("");

  async function handleSend() {
    if (!text.trim() || loading) return;

    const userMessage = {
      id: Date.now(),
      sender: "user",
      text,
    };

    setMessages((prev) => [...prev, userMessage]);

    const query = text;
    setText("");
    setLoading(true);

    try {
      const data = await sendMessage(SESSION_ID, query);

      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: "assistant",
          text:
            data.message ||
            `I found ${data.totalFilteredProducts} matching products.`,
        },
      ]);

      console.log(data);

      setProducts(data.recommendedProducts || []);
      setFilters(data.filters || {});

      console.log(data.filters);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 2,
          sender: "assistant",
          text: "Something went wrong.",
        },
      ]);

      console.error(err);
    }

    setLoading(false);
  }

  return (
    <div className="chat-input-wrapper">
      <div className="chat-input-container">

        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSend()}
          placeholder="Ask anything... (e.g. Show white shirts under Rs.5000)"
        />

        <button
          disabled={loading}
          onClick={handleSend}
        >
          {loading ? "..." : "Send"}
        </button>

      </div>
    </div>
  );
}