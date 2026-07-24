import { Bot, User } from "lucide-react";
import "./ChatBubble.css";

export default function ChatBubble({ message }) {
  const isUser = message.sender === "user";

  return (
    <div
      className={`flex items-end gap-3 ${
        isUser ? "justify-end" : "justify-start"
      }`}
    >
      {/* AI Avatar */}

      {!isUser && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-cyan-500 text-black shadow-lg">
          <Bot size={20} />
        </div>
      )}

      {/* Bubble */}

      <div
        className={`max-w-[75%] rounded-2xl px-5 py-4 shadow-lg ${
          isUser
            ? "rounded-br-md bg-cyan-500 text-black"
            : "rounded-bl-md border border-slate-700 bg-slate-800 text-white"
        }`}
      >
        <p className="whitespace-pre-wrap leading-7">
          {message.text}
        </p>

        <div
          className={`mt-3 text-xs ${
            isUser ? "text-slate-800" : "text-slate-400"
          }`}
        >
          {new Date().toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </div>
      </div>

      {/* User Avatar */}

      {isUser && (
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-slate-700 text-white shadow-lg">
          <User size={20} />
        </div>
      )}
    </div>
  );
}