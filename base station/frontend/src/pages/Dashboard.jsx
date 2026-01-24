import { useState, useEffect } from 'react';
import IssueMap2D from '../components/IssueMap2D';
import './Dashboard.css';

const API_BASE = 'http://localhost:5000';
const DEVICES_API = 'http://localhost:5001';

function Dashboard() {
  const [drones, setDrones] = useState([]);
  const [robots, setRobots] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [networkSummary, setNetworkSummary] = useState({
    dronesOnline: 0,
    robotsOnline: 0,
    activeTasks: 0,
    completedTasks: 0,
    failedTasks: 0
  });

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 3000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (!event.target.closest('.menu-container')) {
        setOpenMenus({});
      }
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  const fetchData = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/overview`);
      const data = await response.json();

      const dronesArray = Object.entries(data.drones || {})
        // Ensure only true drones (not robots) are shown
        .filter(([, drone]) => (drone?.role || '').toUpperCase() === 'DRONE')
        .map(([id, drone]) => ({
          id,
          ...drone
        }));
      const robotsArray = Object.entries(data.robots || {}).map(([id, robot]) => ({
        id,
        ...robot
      }));
      const tasksArray = Object.entries(data.tasks || {}).map(([id, task]) => ({
        id,
        ...task
      }));

      setDrones(dronesArray);
      setRobots(robotsArray);
      setTasks(tasksArray);

      setNetworkSummary({
        dronesOnline: dronesArray.length,
        robotsOnline: robotsArray.length,
        activeTasks: tasksArray.filter(t => t.status === 'CLAIMED').length,
        completedTasks: tasksArray.filter(t => t.status === 'DONE').length,
        failedTasks: 0
      });

      // Merge devices from lightweight server (TCP/UDP)
      try {
        const devRes = await fetch(`${DEVICES_API}/devices`);
        const devData = await devRes.json();
        const devices = devData.devices || [];

        const connDrones = devices
          .filter(d => (d.type || '').toLowerCase() === 'drone')
          .map(d => ({
            id: d.id,
            battery: null,
            status: 'CONNECTED...',
            last_seen: Date.now() / 1000,
            role: 'DRONE',
            position: d.position ? `(${d.position.x ?? '-'}, ${d.position.y ?? '-'}, ${d.position.z ?? '-'})` : null
          }));

        const connRobots = devices
          .filter(d => (d.type || '').toLowerCase() === 'robot')
          .map(d => ({
            id: d.id,
            battery: null,
            busy: false,
            current_task: null,
            position: d.position ? `(${d.position.x ?? '-'}, ${d.position.y ?? '-'}, ${d.position.z ?? '-'})` : null
          }));

        setDrones(prev => {
          const existingIds = new Set(prev.map(p => p.id));
          const merged = [...prev, ...connDrones.filter(cd => !existingIds.has(cd.id))];
          return merged;
        });

        setRobots(prev => {
          const existingIds = new Set(prev.map(p => p.id));
          const merged = [...prev, ...connRobots.filter(cr => !existingIds.has(cr.id))];
          return merged;
        });
      } catch (e) {
        // Ignore if devices API not available
      }
    } catch (error) {
      console.error('Error fetching data:', error);
    }
  };

  const getStatusColor = (drone) => {
    if (drone.battery < 20) return '#ef4444';
    if (drone.status === 'INSPECTING') return '#eab308';
    return '#22c55e';
  };

  const getRobotStatusColor = (robot) => {
    if (robot.battery < 20) return '#ef4444';
    if (robot.busy) return '#eab308';
    return '#22c55e';
  };

  const [openMenus, setOpenMenus] = useState({});

  const toggleMenu = (deviceId) => {
    setOpenMenus(prev => ({
      ...prev,
      [deviceId]: !prev[deviceId]
    }));
  };

  const handleBatteryLowSimulate = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/simulate-battery-low`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType
        })
      });
      
      const data = await response.json();
      if (data.success) {
        alert(`Battery low simulation sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending battery low simulation:', error);
      alert('Failed to send battery low simulation');
    }
  };

  const handleSimulateIssueOverheatedCircuit = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/simulate-issue-overheated-circuit`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType
        })
      });
      
      const data = await response.json();
      if (data.success) {
        alert(`Overheated circuit simulation sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending overheated circuit simulation:', error);
      alert('Failed to send overheated circuit simulation');
    }
  };

  const handleSimulateIssueA = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/simulate-issue-a`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType
        })
      });
      
      const data = await response.json();
      if (data.success) {
        alert(`Issue A simulation sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending issue A simulation:', error);
      alert('Failed to send issue A simulation');
    }
  };

  const handleSimulateIssueB = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/simulate-issue-b`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType
        })
      });
      
      const data = await response.json();
      if (data.success) {
        alert(`Issue B simulation sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending issue B simulation:', error);
      alert('Failed to send issue B simulation');
    }
  };

  const handleEngageDrone = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/drone-control`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType,
          command: 'ENGAGE'
        })
      });
      
      const data = await response.json();
      if (data.success) {
        // Log the command to backend
        await fetch(`${API_BASE}/api/log-command`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_id: deviceId,
            device_type: deviceType,
            command: 'ENGAGE'
          })
        }).catch(err => console.error('Failed to log command:', err));
        
        alert(`Engage command sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending engage command:', error);
      alert('Failed to send engage command');
    }
  };

  const handleGroundDrone = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/drone-control`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType,
          command: 'GROUND'
        })
      });
      
      const data = await response.json();
      if (data.success) {
        // Log the command to backend
        await fetch(`${API_BASE}/api/log-command`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            device_id: deviceId,
            device_type: deviceType,
            command: 'GROUND'
          })
        }).catch(err => console.error('Failed to log command:', err));
        
        alert(`Ground command sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending ground command:', error);
      alert('Failed to send ground command');
    }
  };

  const handleReturnHome = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/drone-control`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType,
          command: 'RETURN_HOME'
        })
      });
      
      const data = await response.json();
      if (data.success) {
        alert(`Return home command sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending return home command:', error);
      alert('Failed to send return home command');
    }
  };

  const handleStartDetection = async (deviceId, deviceType) => {
    try {
      const response = await fetch(`${API_BASE}/api/start-detection`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          device_id: deviceId,
          device_type: deviceType,
        })
      });

      const data = await response.json();
      if (data.success) {
        alert(`Start detection sent to ${deviceId}`);
      } else {
        alert(`Error: ${data.error}`);
      }
      setOpenMenus({});
    } catch (error) {
      console.error('Error sending start detection:', error);
      alert('Failed to send start detection');
    }
  };

  return (
    <div className="dashboard">
      <div className="top-section">
        <div className="panel drone-panel">
            <h2>Drone Status</h2>
            <div className="table-container">
              <table>
                <thead>
                  <tr>
                    <th>Drone ID</th>
                    <th>Status</th>
                    <th>Battery %</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {drones.map(drone => (
                    <tr key={drone.id} style={{ color: getStatusColor(drone) }}>
                      <td>{drone.id}</td>
                      <td>{drone.status || 'ACTIVE'}</td>
                      <td>{drone.battery ? drone.battery.toFixed(1) : 'N/A'}%</td>
                      <td>
                        <div className="menu-container" style={{ position: 'relative' }}>
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleMenu(drone.id);
                            }}
                            style={{
                              background: 'none',
                              border: 'none',
                              color: '#f1f5f9',
                              cursor: 'pointer',
                              fontSize: '1.2rem',
                              padding: '0.25rem 0.5rem'
                            }}
                          >
                            ⋮
                          </button>
                          {openMenus[drone.id] && (
                            <div
                              style={{
                                position: 'absolute',
                                right: 0,
                                top: '100%',
                                background: '#1e293b',
                                border: '1px solid rgba(148, 163, 184, 0.2)',
                                borderRadius: '4px',
                                padding: '0.5rem',
                                zIndex: 1000,
                                minWidth: '180px',
                                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
                              }}
                            >
                              <button
                                onClick={() => handleEngageDrone(drone.id, 'drone')}
                                style={{
                                  width: '100%',
                                  textAlign: 'left',
                                  background: 'none',
                                  border: 'none',
                                  color: '#22c55e',
                                  cursor: 'pointer',
                                  padding: '0.5rem',
                                  fontSize: '0.875rem',
                                  fontWeight: '600'
                                }}
                                onMouseEnter={(e) => e.target.style.background = 'rgba(34, 197, 94, 0.1)'}
                                onMouseLeave={(e) => e.target.style.background = 'none'}
                              >
                                ENGAGE
                              </button>
                              <button
                                onClick={() => handleGroundDrone(drone.id, 'drone')}
                                style={{
                                  width: '100%',
                                  textAlign: 'left',
                                  background: 'none',
                                  border: 'none',
                                  color: '#ef4444',
                                  cursor: 'pointer',
                                  padding: '0.5rem',
                                  fontSize: '0.875rem',
                                  fontWeight: '600'
                                }}
                                onMouseEnter={(e) => e.target.style.background = 'rgba(239, 68, 68, 0.1)'}
                                onMouseLeave={(e) => e.target.style.background = 'none'}
                              >
                                Disengage
                              </button>
                            </div>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
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
                {robots.map(robot => (
                  <tr key={robot.id} style={{ color: getRobotStatusColor(robot) }}>
                    <td>{robot.id}</td>
                    <td>{robot.busy ? 'BUSY' : 'IDLE'}</td>
                    <td>{robot.battery ? robot.battery.toFixed(1) : 'N/A'}%</td>
                    <td>
                      <div
                        style={{
                          color: robot.task_issue_type ? '#fbbf24' : '#22c55e',
                          fontWeight: '600',
                          minWidth: '150px'
                        }}
                        title={robot.task_issue_type ? `Issue: ${robot.task_issue_type}` : 'No task assigned'}
                      >
                        {robot.task_issue_type ? `${robot.task_issue_type.toUpperCase()}` : 'Ready'}
                      </div>
                    </td>
                    <td>
                      <div className="menu-container" style={{ position: 'relative' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleMenu(robot.id);
                          }}
                          style={{
                            background: 'none',
                            border: 'none',
                            color: '#f1f5f9',
                            cursor: 'pointer',
                            fontSize: '1.2rem',
                            padding: '0.25rem 0.5rem'
                          }}
                        >
                          ⋮
                        </button>
                        {openMenus[robot.id] && (
                          <div
                            style={{
                              position: 'absolute',
                              right: 0,
                              top: '100%',
                              background: '#1e293b',
                              border: '1px solid rgba(148, 163, 184, 0.2)',
                              borderRadius: '4px',
                              padding: '0.5rem',
                              zIndex: 1000,
                              minWidth: '180px',
                              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.3)'
                            }}
                          >
                            <button
                              onClick={() => handleEngageDrone(robot.id, 'robot')}
                              style={{
                                width: '100%',
                                textAlign: 'left',
                                background: 'none',
                                border: 'none',
                                color: '#22c55e',
                                cursor: 'pointer',
                                padding: '0.5rem',
                                fontSize: '0.875rem',
                                fontWeight: '600'
                              }}
                              onMouseEnter={(e) => e.target.style.background = 'rgba(34, 197, 94, 0.1)'}
                              onMouseLeave={(e) => e.target.style.background = 'none'}
                            >
                              Engage
                            </button>
                            <button
                              onClick={() => handleGroundDrone(robot.id, 'robot')}
                              style={{
                                width: '100%',
                                textAlign: 'left',
                                background: 'none',
                                border: 'none',
                                color: '#ef4444',
                                cursor: 'pointer',
                                padding: '0.5rem',
                                fontSize: '0.875rem',
                                fontWeight: '600'
                              }}
                              onMouseEnter={(e) => e.target.style.background = 'rgba(239, 68, 68, 0.1)'}
                              onMouseLeave={(e) => e.target.style.background = 'none'}
                            >
                              Disengage
                            </button>
                          </div>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      <div className="panel tower-panel">
        <h2>Operations Map</h2>
        <IssueMap2D />
      </div>
    </div>
    </div>
  );
}

export default Dashboard;
