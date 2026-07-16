import Product from "../models/Product.js";

// Create Product
export const createProduct = async (req, res) => {
    try {

        const product = await Product.create({

            name: req.body.name,

            description: req.body.description,

            category: req.body.category,

            price: req.body.price,

            image: req.file
                ? `/uploads/${req.file.filename}`
                : ""

        });

        res.status(201).json({
            success: true,
            data: product
        });

    } catch (error) {

        res.status(500).json({
            success: false,
            message: error.message
        });

    }
};

// Get All Products
export const getProducts = async (req, res) => {
  try {
    const products = await Product.find();

    res.json({
      success: true,
      count: products.length,
      data: products,
    });
  } catch (error) {
    res.status(500).json({
      success: false,
      message: error.message,
    });
  }
};