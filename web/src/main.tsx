import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./design-system/src/fonts.css";
import "./design-system/src/tokens.css";
import "./design-system/src/components.css";
import "./app.css";
import { App } from "./App";
import { applyTheme, loadTheme } from "./theme";

// Antes de desenhar: sem isto, quem escolheu "escuro" veria um piscar claro ao abrir.
applyTheme(loadTheme());

const root = document.getElementById("root");
if (!root) throw new Error("elemento #root não encontrado em index.html");

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
