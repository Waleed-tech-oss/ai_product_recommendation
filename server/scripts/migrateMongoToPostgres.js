import dotenv from "dotenv";
import mongoose from "mongoose";

import Product from "../models/Product.js";
import prisma from "../config/prisma.js";

dotenv.config();

async function migrate() {
  try {
    console.log("🔄 Connecting MongoDB...");

    await mongoose.connect(process.env.MONGO_URI);

    console.log("✅ MongoDB Connected");

    const products = await Product.find();

    console.log(`📦 Found ${products.length} products`);

    let migrated = 0;
    let skipped = 0;

    for (const product of products) {
      // Skip duplicate products
      const exists = await prisma.product.findFirst({
        where: {
          name: product.name,
          image: product.image,
        },
      });

      if (exists) {
        skipped++;
        continue;
      }

      await prisma.product.create({
        data: {
          name: product.name,
          description: product.description,
          category: product.category,
          subCategory: product.subCategory,
          articleType: product.articleType,
          gender: product.gender,
          color: product.color,
          season: product.season,
          usage: product.usage,
          image: product.image,
          price: product.price,
          embedding: product.embedding,
        },
      });

      migrated++;

      if (migrated % 50 === 0) {
        console.log(`✅ ${migrated} products migrated`);
      }
    }

    console.log("\n🎉 Migration Complete");
    console.log(`✅ Migrated : ${migrated}`);
    console.log(`⏭️ Skipped  : ${skipped}`);

    await mongoose.disconnect();
    await prisma.$disconnect();
  } catch (error) {
    console.error(error);
  }
}

migrate();