import { useEffect, useState } from "react";
import { ArrowRight } from "lucide-react";

import api from "../services/api";

export default function HomePage() {
  const [apiStatus, setApiStatus] = useState("checking");

  useEffect(() => {
    api
      .get("/health/")
      .then(() => setApiStatus("connected"))
      .catch(() => setApiStatus("unreachable"));
  }, []);

  return (
    <section className="card stack">
      <span className={`status-pill status-pill--${apiStatus}`}>API {apiStatus}</span>
      <h1 className="page-title">Give Your Campus Essentials a Second Life.</h1>
      <p className="muted">
        The app shell is ready. The marketplace page replaces this placeholder in the next steps.
      </p>
      <div className="row">
        <button type="button" className="btn btn--primary">
          Explore Marketplace <ArrowRight size={18} />
        </button>
        <button type="button" className="btn btn--outline">
          Sell Your Item
        </button>
        <button type="button" className="btn btn--accent">
          Accent button
        </button>
      </div>
      <div className="row">
        <span className="badge badge--new">New</span>
        <span className="badge badge--like_new">Like New</span>
        <span className="badge badge--good">Good</span>
        <span className="badge badge--fair">Fair</span>
      </div>
    </section>
  );
}