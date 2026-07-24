import axios from "axios";
import FormData from "form-data";
import fs from "fs";

export const getRecommendations = async (imagePath) => {

    const form = new FormData();

    form.append(
        "file",
        fs.createReadStream(imagePath)
    );

    const response = await axios.post(

        "http://127.0.0.1:8000/recommend",

        form,

        {
            headers: form.getHeaders()
        }

    );

    return response.data;
};