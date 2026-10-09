import { createRoot } from "react-dom/client";
import App from "./App";
import "./App.css";

// No <StrictMode>: in development it mounts App twice, which opens a WebSocket
// and immediately kills it, filling the backend's terminal with handshake errors.
createRoot(document.getElementById("root")!).render(<App />);
