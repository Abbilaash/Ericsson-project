import { useState, useEffect } from 'react';
import IssueMap2D from '../components/IssueMap2D';
import { useOverviewData } from '../hooks/useOverviewData';
import './Dashboard.css';

// Cookie management utilities
const setCookie = (name, value, days = 365) => {
  const expires = new Date();
  expires.setTime(expires.getTime() + days * 24 * 60 * 60 * 1000);
  document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
};

const getCookie = (name) => {
  const nameEQ = name + '=';
  const cookies = document.cookie.split(';');
  for (let cookie of cookies) {
    cookie = cookie.trim();
    if (cookie.indexOf(nameEQ) === 0) {
      return cookie.substring(nameEQ.length);
    }
  }
  return null;
};

const deleteCookie = (name) => {
  document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:00 UTC;path=/`;
};

function Operations() {
  const { drones, robots, tasks, loading, error } = useOverviewData();

  const [towerX, setTowerX] = useState('');
  const [towerY, setTowerY] = useState('');
  const [towerRadius, setTowerRadius] = useState('');
  const [storedTowerLocation, setStoredTowerLocation] = useState(null); // { x, y } - map center
  const [appliedTower, setAppliedTower] = useState(null); // { x, y, r } - for drawing

  // Load tower data from cookies on component mount
  useEffect(() => {
    const cookieX = getCookie('tower_x');
    const cookieY = getCookie('tower_y');
    const cookieR = getCookie('tower_radius');

    if (cookieX && cookieY && cookieR) {
      const x = parseFloat(cookieX);
      const y = parseFloat(cookieY);
      const r = parseFloat(cookieR);

      setTowerX(cookieX);
      setTowerY(cookieY);
      setTowerRadius(cookieR);
      setStoredTowerLocation({ x, y });
      setAppliedTower({ x, y, r });
      console.log(`[Tower] Restored from cookies: center=(${x}, ${y}), radius=${r}`);
    }
  }, []);

  const handleApplyTower = () => {
    const x = parseFloat(towerX);
    const y = parseFloat(towerY);
    const r = parseFloat(towerRadius);
    if (!Number.isNaN(x) && !Number.isNaN(y) && !Number.isNaN(r) && r > 0) {
      setStoredTowerLocation({ x, y }); // Store as map center
      setAppliedTower({ x, y, r }); // Draw tower
      // Save to cookies
      setCookie('tower_x', x.toString());
      setCookie('tower_y', y.toString());
      setCookie('tower_radius', r.toString());
      console.log(`[Tower] Applied and saved to cookies: center=(${x}, ${y}), radius=${r}`);
    } else {
      setStoredTowerLocation(null);
      setAppliedTower(null);
      console.log('[Tower] Cleared: invalid or empty inputs');
    }
  };

  const handleRemoveTower = () => {
    setTowerX('');
    setTowerY('');
    setTowerRadius('');
    setStoredTowerLocation(null);
    setAppliedTower(null);
    // Clear cookies
    deleteCookie('tower_x');
    deleteCookie('tower_y');
    deleteCookie('tower_radius');
    console.log('[Tower] Removed: tower location cleared and cookies deleted');
  };

  return (
    <div className="dashboard">
      <div className="panel tower-panel">
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
          <h2 style={{ margin: 0 }}>2D Issue Map</h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.875rem', color: '#94a3b8', fontWeight: '500' }}>X:</label>
              <input
                type="number"
                placeholder="125"
                value={towerX}
                onChange={(e) => setTowerX(e.target.value)}
                style={{
                  width: '70px',
                  padding: '0.4rem 0.6rem',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '4px',
                  color: '#e2e8f0',
                  fontSize: '0.875rem'
                }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.875rem', color: '#94a3b8', fontWeight: '500' }}>Y:</label>
              <input
                type="number"
                placeholder="100"
                value={towerY}
                onChange={(e) => setTowerY(e.target.value)}
                style={{
                  width: '70px',
                  padding: '0.4rem 0.6rem',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '4px',
                  color: '#e2e8f0',
                  fontSize: '0.875rem'
                }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <label style={{ fontSize: '0.875rem', color: '#94a3b8', fontWeight: '500' }}>R:</label>
              <input
                type="number"
                placeholder="30"
                min="0"
                value={towerRadius}
                onChange={(e) => setTowerRadius(e.target.value)}
                style={{
                  width: '70px',
                  padding: '0.4rem 0.6rem',
                  background: 'rgba(15, 23, 42, 0.6)',
                  border: '1px solid rgba(148, 163, 184, 0.3)',
                  borderRadius: '4px',
                  color: '#e2e8f0',
                  fontSize: '0.875rem'
                }}
              />
            </div>
            <button
              onClick={handleApplyTower}
              style={{
                padding: '0.4rem 1rem',
                background: 'rgba(96, 165, 250, 0.2)',
                border: '1px solid rgba(96, 165, 250, 0.3)',
                borderRadius: '4px',
                color: '#60a5fa',
                fontSize: '0.875rem',
                fontWeight: '600',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                e.target.style.background = 'rgba(96, 165, 250, 0.3)';
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'rgba(96, 165, 250, 0.2)';
              }}
            >
              Apply Tower
            </button>
            <button
              onClick={handleRemoveTower}
              style={{
                padding: '0.4rem 1rem',
                background: 'rgba(239, 68, 68, 0.2)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '4px',
                color: '#ef4444',
                fontSize: '0.875rem',
                fontWeight: '600',
                cursor: 'pointer',
                transition: 'all 0.2s'
              }}
              onMouseEnter={(e) => {
                e.target.style.background = 'rgba(239, 68, 68, 0.3)';
              }}
              onMouseLeave={(e) => {
                e.target.style.background = 'rgba(239, 68, 68, 0.2)';
              }}
            >
              Remove Tower
            </button>
          </div>
        </div>
        {error && <div className="error">Failed to load: {error.message}</div>}
        <IssueMap2D drones={drones} robots={robots} issues={tasks} tower={appliedTower} towerCenter={storedTowerLocation} />
      </div>

      <div className="panel task-panel" style={{ marginTop: '1rem' }}>
        <h2>Tasks</h2>
        <div className="table-container">
          <table>
            <thead>
              <tr>
                <th>Task ID</th>
                <th>Status</th>
                <th>Claimed By</th>
                <th>Time Detected</th>
              </tr>
            </thead>
            <tbody>
              {tasks.map((task) => (
                <tr key={task.id}>
                  <td>{task.id}</td>
                  <td>{task.status || 'UNKNOWN'}</td>
                  <td>{task.claimed_by || '-'}</td>
                  <td>{task.time_detected ? new Date(task.time_detected * 1000).toLocaleTimeString() : 'N/A'}</td>
                </tr>
              ))}
              {!loading && tasks.length === 0 && (
                <tr><td colSpan={4}>No tasks</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

export default Operations;
