import { Route, Routes } from "react-router-dom";

import HealthCheck from "./pages/HealthCheck";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<HealthCheck />} />
    </Routes>
  );
}
