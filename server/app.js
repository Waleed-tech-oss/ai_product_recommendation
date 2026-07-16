import express from "express";
import cors from "cors";
import productRoutes from "./routes/product.routes.js";

const app = express();

app.use(cors());
app.use(express.json());

app.get("/", (req, res) => {
  res.json({
    success: true,
    message: "AI Recommendation API Running..."
  });
});
app.use("/uploads", express.static("uploads"));

// Product Routes
app.use("/api/products", productRoutes);

export default app;