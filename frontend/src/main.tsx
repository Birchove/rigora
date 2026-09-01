import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import App from "./App";
import "./styles/tokens.css";
import "./styles/global.css";

const root = document.getElementById("root");

if (root === null) {
  throw new Error("缺少 #root 挂载节点");
}

createRoot(root).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
