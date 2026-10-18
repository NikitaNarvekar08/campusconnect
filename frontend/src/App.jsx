import { useEffect, useState } from "react";
import { CheckCircle2, AlertCircle, Loader2 } from "lucide-react";
import api from "./services/api";

export default function App() {
  const [state, setState] = useState({ status: "loading", message: "" });

  useEffect(() => {
    api
      .get("/health/")
      .then((res) =>
        setState({
          status: "ok",
          message: `API ${res.data.status}, database ${res.data.database}`,
        })
      )
      .catch((err) => setState({ status: "error", message: err.message }));
  }, []);

  return (
    <main className="status-page">
      <section className="status-card">
        <h1>CampusConnect</h1>
        <p>Connection check: React to Django to PostgreSQL</p>

        {state.status === "loading" && (
          <div className="status-row">
            <Loader2 size={20} /> Checking backend...
          </div>
        )}
        {state.status === "ok" && (
          <div className="status-row ok">
            <CheckCircle2 size={20} /> {state.message}
          </div>
        )}
        {state.status === "error" && (
          <div className="status-row error">
            <AlertCircle size={20} /> {state.message}
          </div>
        )}
      </section>
    </main>
  );
}
