import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import Status from './pages/Status';
import Operations from './pages/Operations';
import Logs from './pages/Logs';
import CommandLogs from './pages/CommandLogs';
import './App.css';

function Navigation() {
  const location = useLocation();

  return (
    <nav className="navigation">
      <div className="nav-brand">Drone & Robot Monitor</div>
      <div className="nav-links">
        <Link
          to="/"
          className={location.pathname === '/' ? 'nav-link active' : 'nav-link'}
        >
          Status
        </Link>
        <Link
          to="/operations"
          className={location.pathname === '/operations' ? 'nav-link active' : 'nav-link'}
        >
          Operations
        </Link>
        <Link
          to="/logs"
          className={location.pathname === '/logs' ? 'nav-link active' : 'nav-link'}
        >
          Logs
        </Link>
        <Link
          to="/command-logs"
          className={location.pathname === '/command-logs' ? 'nav-link active' : 'nav-link'}
        >
          Commands
        </Link>
      </div>
    </nav>
  );
}

function App() {
  return (
    <Router>
      <div className="app">
        <Navigation />
        <Routes>
          <Route path="/" element={<Status />} />
          <Route path="/operations" element={<Operations />} />
          <Route path="/logs" element={<Logs />} />
          <Route path="/command-logs" element={<CommandLogs />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
