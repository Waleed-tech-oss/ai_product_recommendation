import express from "express";

import multer from "multer";

import { recommendProducts }
from "../controllers/recommend.controller.js";

const router = express.Router();

const upload = multer({
    dest: "uploads/"
});

router.post(
    "/",
    upload.single("file"),
    recommendProducts
);

export default router;