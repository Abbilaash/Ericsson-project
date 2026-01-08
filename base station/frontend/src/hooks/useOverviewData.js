import { useEffect, useState } from 'react';

const API_BASE = 'http://localhost:5000';

export function useOverviewData(refreshMs = 3000) {
  const [drones, setDrones] = useState([]);
  const [robots, setRobots] = useState([]);
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    let mounted = true;
    const fetchData = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/overview`);
        const data = await response.json();

        if (!mounted) return;

        const dronesArray = Object.entries(data.drones || {}).map(([id, drone]) => ({ id, ...drone }));
        const robotsArray = Object.entries(data.robots || {}).map(([id, robot]) => ({ id, ...robot }));
        const tasksArray = Object.entries(data.tasks || {}).map(([id, task]) => ({ id, ...task }));

        setDrones(dronesArray);
        setRobots(robotsArray);
        setTasks(tasksArray);
        setLoading(false);
        setError(null);
      } catch (err) {
        if (!mounted) return;
        setError(err);
        setLoading(false);
      }
    };

    fetchData();
    const interval = setInterval(fetchData, refreshMs);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [refreshMs]);

  return { drones, robots, tasks, loading, error };
}
