import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./design-system/src/fonts.css";
import "./design-system/src/tokens.css";
import "./design-system/src/components.css";
import "./app.css";
import { App } from "./App";

const root = document.getElementById("root");
if (!root) throw new Error("elemento #root não encontrado em index.html");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
