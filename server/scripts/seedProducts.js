import fs from "fs";
import path from "path";
import csv from "csv-parser";
import mongoose from "mongoose";
import dotenv from "dotenv";

import Product from "../models/Product.js";

dotenv.config();

await mongoose.connect(process.env.MONGO_URI);

console.log("✅ MongoDB Connected");

const products = [];

const LIMIT = 500;

fs.createReadStream("./dataset/styles.csv")
  .pipe(csv())
  .on("data", (row) => {

    if (products.length >= LIMIT) return;

    const imagePath = path.join(
      "dataset",
      "images",
      `${row.id}.jpg`
    );

    // Skip if image doesn't exist
    if (!fs.existsSync(imagePath)) return;

    products.push({

      name: row.productDisplayName,

      description: "",

      category: row.masterCategory,

      subCategory: row.subCategory,

      articleType: row.articleType,

      gender: row.gender,

      color: row.baseColour,

      season: row.season,

      usage: row.usage,

      price: Math.floor(Math.random() * 5000) + 500,

      image: `${row.id}.jpg`,

      embedding: []

    });

  })

  .on("end", async () => {

    console.log(`Found ${products.length} products`);

    try {

      await Product.deleteMany();

      await Product.insertMany(products);

      console.log("✅ Products Imported Successfully");

      mongoose.connection.close();

    } catch (error) {

      console.log(error);

    }

  });