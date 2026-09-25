import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

async function start() {
  if (import.meta.env.VITE_TRANSPORT === "streamlit") {
    const { initStreamlitBridge } = await import("./streamlitBridge.js");
    initStreamlitBridge();
  }

  ReactDOM.createRoot(document.getElementById("root")).render(
    <React.StrictMode>
      <App />
    </React.StrictMode>
  );
}

start();
