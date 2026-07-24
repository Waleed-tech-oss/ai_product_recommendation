import { NavLink } from "react-router-dom";
import "./Navbar.css";

function Navbar() {
  return (
    <nav className="navbar">
      <div className="logo">
        🤖 AI Product Recommendation
      </div>

      <ul className="nav-links">
        <li>
          <NavLink
            to="/"
            className={({ isActive }) =>
              isActive ? "active-link" : ""
            }
          >
            Home
          </NavLink>
        </li>

        <li>
          <NavLink
            to="/shopping-assistant"
            className={({ isActive }) =>
              isActive ? "active-link" : ""
            }
          >
            AI Shopping
          </NavLink>
        </li>

        <li>
          <a href="#about">About</a>
        </li>
      </ul>
    </nav>
  );
}

export default Navbar;