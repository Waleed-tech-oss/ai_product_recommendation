import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
});

export async function sendMessage(sessionId, message) {
  const response = await API.post("/chat/search", {
    sessionId,
    message,
  });

  return response.data;
}

export async function getSuggestions(query) {
  const response = await API.get("/chat/suggestions", {
    params: {
      q: query,
    },
  });

  return response.data;
}