import { useEffect, useState } from "react";
import api from "./services/api";

function App() {
  const [status, setStatus] = useState("checking...");

  useEffect(() => {
    api
      .get("/health/")
      .then((res) => setStatus(res.data.status))
      .catch(() => setStatus("backend unreachable"));
  }, []);

  return (
    <main style={{ padding: "2rem" }}>
      <h1>CampusConnect</h1>
      <p>Backend status: {status}</p>
    </main>
  );
}

export default App;