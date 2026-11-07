/**
 * OmniDev Desktop - React Entry Point
 */

import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import { initializeDesktop } from "./services/desktop";
import "./styles/app.css";

const container = document.getElementById("root");
const root = createRoot(container);
root.render(<div style={{ padding: 40 }}>Starting your workspace…</div>);
initializeDesktop()
  .catch((error) => {
    window.omnidevStartupError = error.message;
  })
  .finally(() => root.render(<App />));
