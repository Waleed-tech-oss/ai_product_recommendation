import axios from "axios";


const API = axios.create({
  baseURL:
    import.meta.env.VITE_AI_API_URL ||
    "http://127.0.0.1:8000",
});


export async function sendMessage(
  sessionId,
  message
) {
  const response = await API.post(
    "/chat/search",
    {
      sessionId,
      message,
    }
  );

  return response.data;
}


export async function sendImageMessage(
  sessionId,
  message,
  imageFile
) {
  if (!(imageFile instanceof File)) {
    throw new Error(
      "A valid image file is required."
    );
  }

  const formData = new FormData();

  formData.append(
    "sessionId",
    sessionId
  );
  formData.append(
    "message",
    message || ""
  );
  formData.append(
    "image",
    imageFile
  );

  const response = await API.post(
    "/chat/image-search",
    formData,
    {
      timeout: 120000,
    }
  );

  return response.data;
}


export async function getSuggestions(
  query
) {
  const response = await API.get(
    "/chat/suggestions",
    {
      params: {
        q: query,
      },
    }
  );

  return response.data;
}
