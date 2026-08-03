import Navbar from "../components/Navbar";
import UploadBox from "../components/UploadBox";
import Footer from "../components/Footer";
import "./Home.css";

function Home() {
  return (
    <>
      <Navbar />

      <main className="home">
        <h1>AI Shopify Product Recommendation</h1>

        <p>
           Upload a product image and discover visually similar
  Shopify products using AI.
        </p>

        <UploadBox />
      </main>

      <Footer />
    </>
  );
}

export default Home;