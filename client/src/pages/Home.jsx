import Navbar from "../components/Navbar";
import UploadBox from "../components/UploadBox";
import Footer from "../components/Footer";
import "./Home.css";

function Home() {
  return (
    <>
      <Navbar />

      <main className="home">
        <h1>Find Similar Fashion Products</h1>

        <p>
          Upload a fashion product image and let AI recommend
          similar products instantly.
        </p>

        <UploadBox />
      </main>

      <Footer />
    </>
  );
}

export default Home;