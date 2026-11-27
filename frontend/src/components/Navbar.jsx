import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Bell, ChevronDown, Heart, MapPin, Recycle, Search } from "lucide-react";

export default function Navbar() {
  const [query, setQuery] = useState("");
  const navigate = useNavigate();

  function handleSearch(event) {
    event.preventDefault();
    const text = query.trim();
    navigate(text ? `/?search=${encodeURIComponent(text)}` : "/");
  }

  return (
    <header className="navbar">
      <div className="navbar__inner container">
        <Link to="/" className="brand" aria-label="CampusConnect home">
          <span className="brand__mark">
            <Recycle size={20} />
          </span>
          <span className="brand__name">CampusConnect</span>
        </Link>

        <div className="campus-pill">
          <span className="campus-pill__label">Campus</span>
          <span className="campus-pill__value">
            <MapPin size={16} />
            All campuses
            <ChevronDown size={16} />
          </span>
        </div>

        <form className="search" onSubmit={handleSearch} role="search">
          <Search size={18} />
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search textbooks, calculators, lab coats..."
            aria-label="Search listings"
          />
        </form>

        <div className="navbar__actions">
          <Link to="/wishlist" className="icon-btn" aria-label="Wishlist">
            <Heart size={21} />
          </Link>
          <Link to="/requests" className="icon-btn" aria-label="Notifications">
            <Bell size={21} />
          </Link>
          <Link to="/login" className="btn btn--ghost btn--sm">
            Log in
          </Link>
          <Link to="/register" className="btn btn--primary btn--sm">
            Register
          </Link>
        </div>
      </div>
    </header>
  );
}