import { useEffect, useState } from "react";
import "./ChatInput.css";
import {
  sendMessage,
  getSuggestions,
} from "../../services/chatApi";
import { Search } from "lucide-react";

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
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);


  useEffect(() => {

  if (text.trim().length < 2) {
    setSuggestions([]);
    setShowSuggestions(false);
    setSelectedIndex(-1);
    return;
  }

  const timer = setTimeout(async () => {

    try {

      const data = await getSuggestions(text);

      setSuggestions(data.suggestions || []);
      setShowSuggestions(true);
      setSelectedIndex(-1);

    } catch (err) {

      console.error(err);

    }

  }, 300);

  return () => clearTimeout(timer);

}, [text]);

function highlightMatch(text, query) {
  if (!query) return text;

  const index = text.toLowerCase().indexOf(query.toLowerCase());

  if (index === -1) return text;

  const before = text.slice(0, index);
  const match = text.slice(index, index + query.length);
  const after = text.slice(index + query.length);

  return (
    <>
      {before}
      <span className="highlight-text">{match}</span>
      {after}
    </>
  );
}



  async function handleSend(customText = text) {
    if (!customText.trim() || loading) return;

    setSuggestions([]);
    setShowSuggestions(false);
    setSelectedIndex(-1);


    const userMessage = {
      id: Date.now(),
      sender: "user",
      text: customText,
    };

    setMessages((prev) => [...prev, userMessage]);

    const query = customText;
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
          onKeyDown={(e) => {

  if (!showSuggestions) {
    if (e.key === "Enter") {
      handleSend();
    }
    return;
  }

  if (e.key === "ArrowDown") {
    e.preventDefault();

    setSelectedIndex((prev) =>
      prev < suggestions.length - 1 ? prev + 1 : prev
    );
  }

  else if (e.key === "ArrowUp") {
    e.preventDefault();

    setSelectedIndex((prev) =>
      prev > 0 ? prev - 1 : 0
    );
  }

  else if (e.key === "Enter") {
    e.preventDefault();

    if (selectedIndex >= 0) {
  const selected = suggestions[selectedIndex];

  setText(selected);
  setShowSuggestions(false);

  handleSend(selected);
} else {
      handleSend();
    }
  }
}}
          placeholder="Ask anything... (e.g. Show white shirts under Rs.5000)"
        />

        {showSuggestions && suggestions.length > 0 && (
  <div className="suggestions-dropdown">
    {suggestions.map((item, index) => (
      <div
        key={index}
        className={`suggestion-item ${
  selectedIndex === index ? "active-suggestion" : ""
}`}
        onClick={() => {
  setText(item);
  setShowSuggestions(false);

  handleSend(item);
}}
      >
        <Search size={16} />
        <span>{highlightMatch(item, text)}</span>
      </div>
    ))}
  </div>
)}

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