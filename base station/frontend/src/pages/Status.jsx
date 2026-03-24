import { useMemo, useState } from 'react';
import { useOverviewData } from '../hooks/useOverviewData';
import './Dashboard.css';

const API_BASE = 'http://localhost:5000';

const getStatusColor = (battery, status) => {
  if (battery !== undefined && battery !== null && battery < 20) return '#ef4444';
  if (status && status.toUpperCase() === 'INSPECTING') return '#eab308';
  return '#22c55e';
};

function Status() {
  const { drones, robots, loading, error } = useOverviewData();
  const [forgettingDeviceId, setForgettingDeviceId] = useState(null);
  const [resettingTasks, setResettingTasks] = useState(false);

  const handleForgetDevice = async (deviceId) => {
    const confirmed = window.confirm(`Forget device ${deviceId}?`);
    if (!confirmed) {
      return;
    }

    setForgettingDeviceId(deviceId);
    try {
      const response = await fetch(`${API_BASE}/api/forget-device`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ device_id: deviceId }),
      });
      const data = await response.json();

      if (!response.ok || !data.success) {
        alert(`Error: ${data.error || 'Failed to forget device'}`);
        return;
      }
    } catch (err) {
      console.error('Failed to forget device:', err);
      alert('Failed to forget device');
    } finally {
      setForgettingDeviceId(null);
    }
  };

  const handleResetTasks = async () => {
    const confirmed = window.confirm('Reset task-completed list and task tracking?');
    if (!confirmed) {
      return;
    }

    setResettingTasks(true);
    try {
      const response = await fetch(`${API_BASE}/api/reset-tasks`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      const data = await response.json();

      if (!response.ok || !data.success) {
        alert(`Error: ${data.error || 'Failed to reset tasks'}`);
        return;
      }

      alert('Task tracking reset successfully. Same task can be assigned again.');
    } catch (err) {
      console.error('Failed to reset tasks:', err);
      alert('Failed to reset tasks');
    } finally {
      setResettingTasks(false);
    }
  };

  const droneRows = useMemo(() => drones, [drones]);
  const robotRows = useMemo(() => robots, [robots]);

  return (
    <div className="dashboard">
      <div style={{ padding: '1rem 1.5rem 0 1.5rem' }}>
        <button
          onClick={handleResetTasks}
          disabled={resettingTasks}
          style={{
            background: 'rgba(14, 116, 144, 0.2)',
            border: '1px solid rgba(56, 189, 248, 0.45)',
            color: '#67e8f9',
            fontWeight: '700',
            letterSpacing: '0.02em',
            cursor: resettingTasks ? 'not-allowed' : 'pointer',
            borderRadius: '8px',
            padding: '0.5rem 0.9rem',
            opacity: resettingTasks ? 0.6 : 1,
          }}
        >
          {resettingTasks ? 'RESETTING TASKS...' : 'RESET TASK'}
        </button>
      </div>
      <div className="top-section">
        <div className="panel drone-panel">
          <h2>Drone Status</h2>
          {error && <div className="error">Failed to load: {error.message}</div>}
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Drone ID</th>
                  <th>Status</th>
                  <th>Battery %</th>
                  <th>Task</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {droneRows.map((drone) => (
                  <tr key={drone.id} style={{ color: getStatusColor(drone.battery, drone.status) }}>
                    <td>{drone.id}</td>
                    <td>{drone.status || 'ACTIVE'}</td>
                    <td>{drone.battery !== undefined && drone.battery !== null ? drone.battery : 'N/A'}%</td>
                    <td>{drone.task_id || 'None'}</td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        onClick={() => handleForgetDevice(drone.id)}
                        disabled={forgettingDeviceId === drone.id}
                        style={{
                          background: 'rgba(245, 158, 11, 0.15)',
                          border: '1px solid rgba(245, 158, 11, 0.45)',
                          color: '#fbbf24',
                          fontWeight: '600',
                          cursor: forgettingDeviceId === drone.id ? 'not-allowed' : 'pointer',
                          borderRadius: '6px',
                          padding: '0.35rem 0.7rem',
                          opacity: forgettingDeviceId === drone.id ? 0.6 : 1,
                        }}
                      >
                        {forgettingDeviceId === drone.id ? 'FORGETTING...' : 'FORGET'}
                      </button>
                    </td>
                  </tr>
                ))}
                {!loading && droneRows.length === 0 && (
                  <tr><td colSpan={5}>No drones</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="panel robot-panel">
          <h2>Robot Status</h2>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Robot ID</th>
                  <th>Status</th>
                  <th>Battery %</th>
                  <th>Task</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {robotRows.map((robot) => (
                  <tr key={robot.id} style={{ color: getStatusColor(robot.battery, robot.status) }}>
                    <td>{robot.id}</td>
                    <td>{robot.status || (robot.busy ? 'BUSY' : 'IDLE')}</td>
                    <td>{robot.battery !== undefined && robot.battery !== null ? robot.battery : 'N/A'}%</td>
                    <td>{robot.task_id || 'None'}</td>
                    <td style={{ textAlign: 'center' }}>
                      <button
                        onClick={() => handleForgetDevice(robot.id)}
                        disabled={forgettingDeviceId === robot.id}
                        style={{
                          background: 'rgba(245, 158, 11, 0.15)',
                          border: '1px solid rgba(245, 158, 11, 0.45)',
                          color: '#fbbf24',
                          fontWeight: '600',
                          cursor: forgettingDeviceId === robot.id ? 'not-allowed' : 'pointer',
                          borderRadius: '6px',
                          padding: '0.35rem 0.7rem',
                          opacity: forgettingDeviceId === robot.id ? 0.6 : 1,
                        }}
                      >
                        {forgettingDeviceId === robot.id ? 'FORGETTING...' : 'FORGET'}
                      </button>
                    </td>
                  </tr>
                ))}
                {!loading && robotRows.length === 0 && (
                  <tr><td colSpan={5}>No robots</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Status;
