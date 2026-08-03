import {
  useEffect,
  useRef,
  useState,
} from "react";
import {
  ImagePlus,
  Search,
  X,
} from "lucide-react";

import "./ChatInput.css";
import "./ChatImageUpload.css";

import {
  getSuggestions,
} from "../../services/chatApi";


const ALLOWED_IMAGE_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
];

const MAX_IMAGE_BYTES =
  8 * 1024 * 1024;


export default function ChatInput({
  onSend,
  onImageSend,
  loading,
}) {
  const [text, setText] = useState("");
  const [
    suggestions,
    setSuggestions,
  ] = useState([]);
  const [
    showSuggestions,
    setShowSuggestions,
  ] = useState(false);
  const [
    selectedIndex,
    setSelectedIndex,
  ] = useState(-1);
  const [
    selectedImage,
    setSelectedImage,
  ] = useState(null);
  const [
    imagePreview,
    setImagePreview,
  ] = useState("");
  const [
    imageError,
    setImageError,
  ] = useState("");

  const fileInputRef = useRef(null);

  useEffect(() => {
    const query = text.trim();

    // Autocomplete is useful for normal text chat,
    // but distracting during an image-guided search.
    if (
      selectedImage ||
      query.length < 2
    ) {
      setSuggestions([]);
      setShowSuggestions(false);
      setSelectedIndex(-1);
      return undefined;
    }

    const timer = setTimeout(
      async () => {
        try {
          const data =
            await getSuggestions(query);

          setSuggestions(
            data.suggestions || []
          );
          setShowSuggestions(true);
          setSelectedIndex(-1);
        } catch (error) {
          console.error(
            "Suggestion error:",
            error
          );
          setSuggestions([]);
          setShowSuggestions(false);
        }
      },
      300
    );

    return () => clearTimeout(timer);
  }, [text, selectedImage]);

  useEffect(
    () => () => {
      if (imagePreview) {
        URL.revokeObjectURL(
          imagePreview
        );
      }
    },
    [imagePreview]
  );

  function clearSelectedImage() {
    if (imagePreview) {
      URL.revokeObjectURL(
        imagePreview
      );
    }

    setSelectedImage(null);
    setImagePreview("");
    setImageError("");

    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  }

  function handleImageSelection(
    event
  ) {
    const file =
      event.target.files?.[0];

    if (!file) {
      return;
    }

    if (
      !ALLOWED_IMAGE_TYPES.includes(
        file.type
      )
    ) {
      setImageError(
        "Only JPG, PNG, and WEBP images are supported."
      );
      event.target.value = "";
      return;
    }

    if (file.size > MAX_IMAGE_BYTES) {
      setImageError(
        "Image must be smaller than 8 MB."
      );
      event.target.value = "";
      return;
    }

    if (imagePreview) {
      URL.revokeObjectURL(
        imagePreview
      );
    }

    setSelectedImage(file);
    setImagePreview(
      URL.createObjectURL(file)
    );
    setImageError("");
    setSuggestions([]);
    setShowSuggestions(false);
  }

  function highlightMatch(
    suggestionText,
    query
  ) {
    if (!query) {
      return suggestionText;
    }

    const index = suggestionText
      .toLowerCase()
      .indexOf(query.toLowerCase());

    if (index === -1) {
      return suggestionText;
    }

    const before =
      suggestionText.slice(0, index);
    const match = suggestionText.slice(
      index,
      index + query.length
    );
    const after = suggestionText.slice(
      index + query.length
    );

    return (
      <>
        {before}
        <span className="highlight-text">
          {match}
        </span>
        {after}
      </>
    );
  }

  async function handleSend(
    customText = null
  ) {
    const textToSend =
      typeof customText === "string"
        ? customText.trim()
        : text.trim();

    if (
      (!textToSend && !selectedImage)
      || loading
    ) {
      return;
    }

    setSuggestions([]);
    setShowSuggestions(false);
    setSelectedIndex(-1);

    if (selectedImage) {
      const imageFile = selectedImage;

      // Keep the object URL alive until the parent has
      // converted the file into a stable chat preview.
      await onImageSend(
        textToSend,
        imageFile
      );

      clearSelectedImage();
    } else {
      await onSend(textToSend);
    }

    setText("");
  }

  function handleKeyDown(event) {
    if (!showSuggestions) {
      if (event.key === "Enter") {
        event.preventDefault();
        handleSend();
      }

      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();

      setSelectedIndex((previous) =>
        previous <
        suggestions.length - 1
          ? previous + 1
          : previous
      );

      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();

      setSelectedIndex((previous) =>
        previous > 0
          ? previous - 1
          : 0
      );

      return;
    }

    if (event.key === "Escape") {
      setShowSuggestions(false);
      setSelectedIndex(-1);
      return;
    }

    if (event.key === "Enter") {
      event.preventDefault();

      if (
        selectedIndex >= 0 &&
        suggestions[selectedIndex]
      ) {
        handleSend(
          suggestions[selectedIndex]
        );
      } else {
        handleSend();
      }
    }
  }

  return (
    <div className="chat-input-wrapper">
      {imagePreview && (
        <div className="chat-image-preview">
          <img
            src={imagePreview}
            alt="Selected upload"
          />

          <div className="chat-image-preview-info">
            <strong>
              {selectedImage?.name}
            </strong>

            <span>
              Add optional text for hybrid search
            </span>
          </div>

          <button
            type="button"
            className="remove-chat-image"
            onClick={
              clearSelectedImage
            }
            disabled={loading}
            aria-label="Remove selected image"
          >
            <X size={18} />
          </button>
        </div>
      )}

      {imageError && (
        <p className="chat-image-error">
          {imageError}
        </p>
      )}

      <div className="chat-input-container">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          className="hidden-image-input"
          onChange={
            handleImageSelection
          }
          disabled={loading}
        />

        <button
          type="button"
          className="image-upload-button"
          onClick={() =>
            fileInputRef.current?.click()
          }
          disabled={loading}
          title="Upload product image"
          aria-label="Upload product image"
        >
          <ImagePlus size={20} />
        </button>

        <input
          value={text}
          onChange={(event) =>
            setText(event.target.value)
          }
          onKeyDown={handleKeyDown}
          placeholder={
            selectedImage
              ? (
                  "Optional: is jaisa black product " +
                  "under $100 dikhao"
                )
              : (
                  "Ask anything... " +
                  "(e.g. Show white shirts under Rs.5000)"
                )
          }
          disabled={loading}
        />

        {showSuggestions &&
          suggestions.length > 0 && (
            <div className="suggestions-dropdown">
              {suggestions.map(
                (item, index) => (
                  <button
                    type="button"
                    key={`${item}-${index}`}
                    className={`suggestion-item ${
                      selectedIndex ===
                      index
                        ? "active-suggestion"
                        : ""
                    }`}
                    onMouseDown={(
                      event
                    ) => {
                      event.preventDefault();
                    }}
                    onClick={() =>
                      handleSend(item)
                    }
                  >
                    <Search size={16} />

                    <span>
                      {highlightMatch(
                        item,
                        text
                      )}
                    </span>
                  </button>
                )
              )}
            </div>
          )}

        <button
          type="button"
          disabled={
            loading ||
            (
              !text.trim()
              && !selectedImage
            )
          }
          onClick={() => handleSend()}
        >
          {loading ? "..." : "Send"}
        </button>
      </div>
    </div>
  );
}
