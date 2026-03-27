import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { persistSessionTokenFromSearch } from "@/lib/sessionToken";

persistSessionTokenFromSearch(window.location.search);

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>
);
