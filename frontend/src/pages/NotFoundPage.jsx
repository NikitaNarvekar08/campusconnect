import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <section className="card stack">
      <h1 className="page-title">Page not found</h1>
      <p className="muted">The page you are looking for does not exist yet.</p>
      <Link to="/" className="btn btn--primary">
        Back to the marketplace
      </Link>
    </section>
  );
}