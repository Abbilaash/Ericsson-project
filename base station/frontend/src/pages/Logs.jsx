import { useState, useEffect } from 'react';
import './Logs.css';

const API_BASE = 'http://localhost:5000';

function Logs() {
  const [logs, setLogs] = useState([]);
  const [filteredLogs, setFilteredLogs] = useState([]);
  const [expandedLog, setExpandedLog] = useState(null);
  const [clearing, setClearing] = useState(false);
  const [filters, setFilters] = useState({
    packetType: 'all',
    messageType: 'all',
    senderId: ''
  });

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    applyFilters();
  }, [logs, filters]);

  const fetchLogs = async () => {
    try {
      // Prefer new alias; falls back to legacy if needed
      const response = await fetch(`${API_BASE}/api/messages`).catch(() => fetch(`${API_BASE}/api/network-logs`));
      const data = await response.json();
      // Backend already sorts by timestamp (newest first), but ensure frontend maintains order
      // Use received_at if available, otherwise use timestamp
      const sortedLogs = (data.packets || []).sort((a, b) => {
        const timeA = a.received_at || a.timestamp || 0;
        const timeB = b.received_at || b.timestamp || 0;
        return timeB - timeA; // Descending order (newest first)
      });
      setLogs(sortedLogs);
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  const applyFilters = () => {
    let filtered = [...logs];

    if (filters.packetType !== 'all') {
      filtered = filtered.filter(log => log.packet_type === filters.packetType);
    }

    if (filters.messageType !== 'all') {
      filtered = filtered.filter(log => log.message_type === filters.messageType);
    }

    if (filters.senderId) {
      filtered = filtered.filter(log =>
        (log.sender_id || log.device_id || '').toLowerCase().includes(filters.senderId.toLowerCase())
      );
    }

    setFilteredLogs(filtered);
  };

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };

  const clearLogs = async () => {
    setClearing(true);
    try {
      await fetch(`${API_BASE}/api/clear-logs`, { method: 'POST' });
      setExpandedLog(null);
      await fetchLogs();
    } catch (error) {
      console.error('Error clearing logs:', error);
    } finally {
      setClearing(false);
    }
  };

  const toggleExpandLog = (logId) => {
    setExpandedLog(expandedLog === logId ? null : logId);
  };

  return (
    <div className="logs-page">
      <div className="logs-header">
        <h1>System Logs</h1>
        <div className="logs-header-actions">
          <div className="log-count">Total Logs: {filteredLogs.length}</div>
          <button
            className="clear-button"
            onClick={clearLogs}
            disabled={clearing}
          >
            {clearing ? 'Clearing...' : 'Clear Logs'}
          </button>
        </div>
      </div>

      <div className="filters">
        <div className="filter-group">
          <label>Packet Type:</label>
          <select
            value={filters.packetType}
            onChange={(e) => handleFilterChange('packetType', e.target.value)}
          >
            <option value="all">All</option>
            <option value="DISCOVERY">Discovery</option>
            <option value="MESSAGE">Message</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Message Type:</label>
          <select
            value={filters.messageType}
            onChange={(e) => handleFilterChange('messageType', e.target.value)}
          >
            <option value="all">All</option>
            <option value="REQUEST">Request</option>
            <option value="ACK">Acknowledgment</option>
            <option value="STATUS">Status</option>
          </select>
        </div>

        <div className="filter-group">
          <label>Device/Sender ID:</label>
          <input
            type="text"
            placeholder="Filter by device ID..."
            value={filters.senderId}
            onChange={(e) => handleFilterChange('senderId', e.target.value)}
          />
        </div>

        <button
          className="reset-button"
          onClick={() => setFilters({ packetType: 'all', messageType: 'all', senderId: '' })}
        >
          Reset Filters
        </button>
      </div>

      <div className="logs-container">
        <table className="logs-table">
          <thead>
            <tr>
              <th>Timestamp</th>
              <th>Sender/Device ID</th>
              <th>Packet Type</th>
              <th>Message Type</th>
              <th>Request Reason</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filteredLogs.map((log, idx) => (
              <>
                <tr key={idx} className="log-row">
                  <td>{(log.received_at || log.timestamp) ? new Date((log.received_at || log.timestamp) * 1000).toLocaleString() : 'N/A'}</td>
                  <td>{log.sender_id || log.device_id || 'N/A'}</td>
                  <td>
                    <span className={`role-badge ${(log.packet_type || '').toLowerCase()}`}>
                      {log.packet_type || 'UNKNOWN'}
                    </span>
                  </td>
                  <td>
                    <span className={`message-badge ${(log.message_type || '').toLowerCase()}`}>
                      {log.message_type || '-'}
                    </span>
                  </td>
                  <td>{log.request_reason || '-'}</td>
                  <td>
                    <button
                      className="expand-button"
                      onClick={() => toggleExpandLog(idx)}
                    >
                      {expandedLog === idx ? 'Hide' : 'Show'} JSON
                    </button>
                  </td>
                </tr>
                {expandedLog === idx && (
                  <tr className="expanded-row">
                    <td colSpan="6">
                      <div className="json-container">
                        <pre>{JSON.stringify(log, null, 2)}</pre>
                      </div>
                    </td>
                  </tr>
                )}
              </>
            ))}
          </tbody>
        </table>

        {filteredLogs.length === 0 && (
          <div className="no-logs">
            No logs found matching the current filters.
          </div>
        )}
      </div>
    </div>
  );
}

export default Logs;
