import { useEffect, useRef } from "react";
import "./ChatWindow.css";

import ChatBubble from "./ChatBubble";
import TypingIndicator from "./TypingIndicator";

export default function ChatWindow({
  messages,
  loading,
}) {
  const bottomRef = useRef(null);

  // Auto Scroll
  useEffect(() => {
    bottomRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  return (
    <div className="chat-window">

      <div className="chat-container">

        {messages.map((message) => (
          <ChatBubble
            key={message.id}
            message={message}
          />
        ))}

        {loading && <TypingIndicator />}

        <div ref={bottomRef} />

      </div>

    </div>
  );
}