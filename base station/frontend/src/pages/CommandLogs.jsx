import { useState, useEffect } from 'react';
import './CommandLogs.css';

const API_BASE = 'http://192.168.226.132:5000';

function CommandLogs() {
  const [commands, setCommands] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCommandLogs();
    const interval = setInterval(fetchCommandLogs, 2000); // Poll every 2 seconds
    return () => clearInterval(interval);
  }, []);

  const fetchCommandLogs = async () => {
    try {
      console.log('[CommandLogs] Fetching from:', `${API_BASE}/api/command-logs`);
      const response = await fetch(`${API_BASE}/api/command-logs`);
      console.log('[CommandLogs] Response status:', response.status);
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }
      
      const data = await response.json();
      console.log('[CommandLogs] Received data:', data);
      
      if (data.success) {
        setCommands(data.commands || []);
        setError(null);
        console.log('[CommandLogs] Set commands:', data.commands?.length || 0);
      } else {
        setError('Failed to fetch command logs');
      }
      setLoading(false);
    } catch (err) {
      console.error('[CommandLogs] Error fetching command logs:', err);
      setError(`Failed to connect: ${err.message}`);
      setLoading(false);
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString();
  };

  const getCommandBadgeClass = (command) => {
    if (command === 'ENGAGE') return 'command-engage';
    if (command === 'GROUND') return 'command-ground';
    return 'command-other';
  };

  return (
    <div className="command-logs-page">
      <div className="command-logs-header">
        <h1>Drone Control Command Logs</h1>
        <div className="header-info">
          <div className="info-badge">
            <span className="info-label">Total Commands:</span>
            <span className="info-value">{commands.length}</span>
          </div>
          <div className="info-badge">
            <span className="info-label">Status:</span>
            <span className={`info-value ${error ? 'status-error' : 'status-active'}`}>
              {error ? 'Error' : 'Active'}
            </span>
          </div>
        </div>
      </div>

      {error && (
        <div className="error-banner">
          <span className="error-icon">⚠️</span>
          <span>{error}</span>
        </div>
      )}

      {loading && commands.length === 0 ? (
        <div className="loading-state">
          <div className="spinner"></div>
          <p>Loading command logs...</p>
        </div>
      ) : (
        <div className="commands-container">
          <table className="commands-table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Drone ID</th>
                <th>Command</th>
                <th>Base Station IP</th>
                <th>Device Type</th>
              </tr>
            </thead>
            <tbody>
              {commands.length === 0 ? (
                <tr>
                  <td colSpan="5" className="no-data">
                    No commands recorded yet. Click Engage or Disengage in the Dashboard to see commands here.
                  </td>
                </tr>
              ) : (
                commands.map((cmd, idx) => (
                  <tr key={idx} className="command-row">
                    <td className="timestamp-cell">{formatTimestamp(cmd.timestamp)}</td>
                    <td className="device-id-cell">
                      <span className="device-id">{cmd.device_id}</span>
                    </td>
                    <td className="command-cell">
                      <span className={`command-badge ${getCommandBadgeClass(cmd.command)}`}>
                        {cmd.command}
                      </span>
                    </td>
                    <td className="ip-cell">{cmd.base_station_ip}</td>
                    <td className="type-cell">
                      <span className="device-type-badge">{cmd.device_type || 'drone'}</span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      <div className="command-logs-footer">
        <p className="footer-note">
          Commands are displayed in real-time as they are sent from the base station.
          Auto-refreshes every 2 seconds.
        </p>
      </div>
    </div>
  );
}

export default CommandLogs;
