import mongoose from "mongoose";

const productSchema = new mongoose.Schema(
  {
    name: {
      type: String,
      required: true,
      trim: true,
    },

    description: {
      type: String,
      default: "",
    },

    category: {
      type: String,
      default: "",
    },

    subCategory: {
      type: String,
      default: "",
    },

    articleType: {
      type: String,
      default: "",
    },

    gender: {
      type: String,
      default: "",
    },

    color: {
      type: String,
      default: "",
    },

    season: {
      type: String,
      default: "",
    },

    usage: {
      type: String,
      default: "",
    },

    image: {
      type: String,
      default: "",
    },

    price: {
      type: Number,
      required: true,
      default: 0,
    },

    embedding: {
      type: [Number],
      default: [],
    },
  },
  {
    timestamps: true,
  }
);

const Product = mongoose.model("Product", productSchema);

export default Product;