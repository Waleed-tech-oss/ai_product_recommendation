import prisma from "../config/prisma.js";

// Create Product
export const createProductService = async (productData) => {
  return await prisma.product.create({
    data: productData,
  });
};

// Get All Products
export const getProductsService = async () => {
  return await prisma.product.findMany({
    orderBy: {
      createdAt: "desc",
    },
  });
};