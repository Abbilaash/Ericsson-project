import { useMemo, useState } from 'react';
import { useOverviewData } from '../hooks/useOverviewData';
import './Dashboard.css';

const getStatusColor = (battery, status) => {
  if (battery !== undefined && battery !== null && battery < 20) return '#ef4444';
  if (status && status.toUpperCase() === 'INSPECTING') return '#eab308';
  return '#22c55e';
};

function Status() {
  const { drones, robots, loading, error } = useOverviewData();
  const [openMenuId, setOpenMenuId] = useState(null);

  const handleEngage = (deviceId) => {
    console.log(`Engaging device: ${deviceId}`);
    setOpenMenuId(null);
  };

  const handleDisengage = (deviceId) => {
    console.log(`Disengaging device: ${deviceId}`);
    setOpenMenuId(null);
  };

  const ActionMenu = ({ deviceId, taskId }) => (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      <button
        onClick={() => setOpenMenuId(openMenuId === deviceId ? null : deviceId)}
        style={{
          background: 'none',
          border: 'none',
          fontSize: '20px',
          cursor: 'pointer',
          padding: '0 8px',
        }}
      >
        ⋮
      </button>
      {openMenuId === deviceId && (
        <div
          style={{
            position: 'absolute',
            top: '30px',
            right: '0',
            backgroundColor: '#fff',
            border: '1px solid #ccc',
            borderRadius: '4px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.15)',
            zIndex: 1000,
            minWidth: '120px',
          }}
        >
          <button
            onClick={() => handleEngage(deviceId)}
            style={{
              display: 'block',
              width: '100%',
              padding: '8px 12px',
              border: 'none',
              background: 'transparent',
              textAlign: 'left',
              cursor: 'pointer',
              fontSize: '14px',
              color: '#22c55e',
              fontWeight: '500',
            }}
            onMouseEnter={(e) => (e.target.style.backgroundColor = '#f0f0f0')}
            onMouseLeave={(e) => (e.target.style.backgroundColor = 'transparent')}
          >
            ENGAGE
          </button>
          <button
            onClick={() => handleDisengage(deviceId)}
            style={{
              display: 'block',
              width: '100%',
              padding: '8px 12px',
              border: 'none',
              background: 'transparent',
              textAlign: 'left',
              cursor: 'pointer',
              fontSize: '14px',
              borderTop: '1px solid #eee',
              color: '#ef4444',
              fontWeight: '500',
            }}
            onMouseEnter={(e) => (e.target.style.backgroundColor = '#f0f0f0')}
            onMouseLeave={(e) => (e.target.style.backgroundColor = 'transparent')}
          >
            DISENGAGE
          </button>
        </div>
      )}
    </div>
  );

  const droneRows = useMemo(() => drones, [drones]);
  const robotRows = useMemo(() => robots, [robots]);

  return (
    <div className="dashboard">
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
                      <ActionMenu deviceId={drone.id} taskId={drone.task_id} />
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
                      <ActionMenu deviceId={robot.id} taskId={robot.task_id} />
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
