import { Outlet } from "react-router-dom";

import Navbar from "../components/Navbar";

export default function MainLayout() {
  return (
    <div className="app-shell">
      <Navbar />
      <main className="page container">
        <Outlet />
      </main>
      <footer className="footer">
        <div className="container">
          CampusConnect: buy, sell and reuse student essentials on your campus.
        </div>
      </footer>
    </div>
  );
}