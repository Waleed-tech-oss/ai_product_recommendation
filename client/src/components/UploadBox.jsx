import { useState } from "react";
import API from "../services/api";
import ProductGrid from "./ProductGrid";
import "./UploadBox.css";

function UploadBox() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleUpload = async () => {
    
    if (!file) {
      alert("Please select an image");
      return;
      
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      setLoading(true);

      const { data } = await API.post("/recommend", formData);
         console.log("Recommend API Response:", data);
         setProducts(data.recommendations || []);
    } catch (error) {
      console.error(error);
      alert("Failed to get recommendations");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="upload-box">
        <h2>📤 Upload Product Image</h2>

        <p className="upload-text">
          Upload any product image and let AI find similar products from your Shopify store.
        </p>

        <input
  type="file"
  accept="image/*"
  onChange={(e) => {
    const selected = e.target.files[0];

    if (selected) {
      setFile(selected);
      setPreview(URL.createObjectURL(selected));
    }
  }}
/>

        {preview && (
  <img
    src={preview}
    alt="Preview"
    className="preview-image"
  />
)}



        {file && (
          <p className="file-name">
            <strong>Selected:</strong> {file.name}
          </p>
        )}

        <button onClick={handleUpload} disabled={loading}>
          {loading ? "Analyzing..." : "Recommend Product"}
        </button>
      </div>

      {products.length > 0 && <ProductGrid products={products} />}
    </>
  );
}

export default UploadBox;