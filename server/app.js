import express from "express";
import cors from "cors";
import path from "path";
import { fileURLToPath } from "url";

import productRoutes from "./routes/product.routes.js";
import recommendRoutes from "./routes/recommend.routes.js";

const app = express();

// Fix __dirname for ES Modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Middlewares
app.use(cors());
app.use(express.json());

// Serve uploaded images
app.use("/uploads", express.static(path.join(__dirname, "uploads")));

// Serve dataset images
app.use(
  "/images",
  express.static(path.join(__dirname, "dataset/images"))
);

// Home Route
app.get("/", (req, res) => {
  res.json({
    success: true,
    message: "AI Recommendation API Running...",
  });
});

// Routes
app.use("/api/products", productRoutes);
app.use("/api/recommend", recommendRoutes);

export default app;

























// import express from "express";
// import cors from "cors";
// import productRoutes from "./routes/product.routes.js";
// import recommendRoutes from "./routes/recommend.routes.js";

// const app = express();

// app.use(cors());
// app.use(express.json());

// app.get("/", (req, res) => {
//   res.json({
//     success: true,
//     message: "AI Recommendation API Running..."
//   });
// });
// app.use("/uploads", express.static("uploads"));

// app.use(
//     "/api/recommend",
//     recommendRoutes
// );
// // Product Routes
// app.use("/api/products", productRoutes);

// export default app;