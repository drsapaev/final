import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";

const rootEl = document.getElementById("root");
if (!rootEl) {
  const el = document.createElement("div");
  el.id = "root";
  document.body.appendChild(el);
  createRoot(el).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
} else {
  createRoot(rootEl).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}