import "./Navbar.css";

function Navbar() {
  return (
    <nav className="navbar">
      <div className="logo">
        🤖 AI Product Recommendation
      </div>

      <ul className="nav-links">
        <li>Home</li>
        <li>About</li>
      </ul>
    </nav>
  );
}

export default Navbar;