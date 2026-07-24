import { getRecommendations } from "../services/ai.service.js";

export const recommendProducts = async (req, res) => {
  try {
    const recommendations = await getRecommendations(req.file.path);

    // Add image URL for React
    const updatedRecommendations = recommendations.map((product) => ({
      ...product,
      imageUrl: `http://localhost:5000/images/${product.image}`,
    }));

    res.json({
      success: true,
      recommendations: updatedRecommendations,
    });
  } catch (error) {
    console.error(error);

    res.status(500).json({
      success: false,
      message: error.message,
    });
  }
};




























// import { getRecommendations } from "../services/ai.service.js";

// export const recommendProducts = async (req, res) => {

//     try {

//         const recommendations =
//             await getRecommendations(req.file.path);

//         res.json({
//             success: true,
//             recommendations
//         });

//     } catch (error) {

//         console.log(error);

//         res.status(500).json({
//             success: false,
//             message: error.message
//         });

//     }

// };