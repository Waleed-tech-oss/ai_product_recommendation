import upload from "../middleware/upload.js";
import express from "express";

import {
  createProduct,
  getProducts,
} from "../controllers/product.controller.js";

const router = express.Router();

router.post("/", upload.single("image"), createProduct);
router.get("/", getProducts);

export default router;