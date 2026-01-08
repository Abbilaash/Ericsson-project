import TowerVisualization from '../components/TowerVisualization';
import { useOverviewData } from '../hooks/useOverviewData';
import './Dashboard.css';

function Operations() {
  const { drones, robots, tasks, loading, error } = useOverviewData();

  return (
    <div className="dashboard">
      <div className="panel tower-panel">
        <h2>Tower Visualization</h2>
        {error && <div className="error">Failed to load: {error.message}</div>}
        <TowerVisualization drones={drones} robots={robots} />
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
