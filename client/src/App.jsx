import { Routes, Route } from "react-router-dom";

import Home from "./pages/Home";
import ShoppingAssistant from "./pages/ShoppingAssistant";

function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route
        path="/shopping-assistant"
        element={<ShoppingAssistant />}
      />
    </Routes>
  );
}

export default App;