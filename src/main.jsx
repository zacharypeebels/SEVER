import React from "react";
import ReactDOM from "react-dom/client";
import SeverAlpha from "../sever-alpha.jsx";
import AuthGate from "./AuthGate.jsx";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <AuthGate>
      <SeverAlpha />
    </AuthGate>
  </React.StrictMode>
);
