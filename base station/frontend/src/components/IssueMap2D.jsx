import { useEffect, useRef, useState } from 'react';
import './IssueMap2D.css';

const API_BASE = 'http://localhost:5000';

function IssueMap2D({ issues, tower, towerCenter }) {
  const canvasRef = useRef(null);
  const [hoveredEntity, setHoveredEntity] = useState(null);
  const [tooltip, setTooltip] = useState(null);
  const [detectedIssues, setDetectedIssues] = useState([]);
  const [devicesPositions, setDevicesPositions] = useState({});
  const entitiesRef = useRef([]);

  // Fetch real-time issues and device positions
  useEffect(() => {
    const fetchRealTimeData = async () => {
      try {
        // Fetch detected issues from backend
        const issuesRes = await fetch(`${API_BASE}/api/current-issues`);
        const issuesData = await issuesRes.json();
        if (issuesData.success) {
          const issueCount = (issuesData.issues || []).length;
          if (issueCount > 0) {
            console.log(`[IssueMap] ✓ ISSUE DETECTED: ${issueCount} issue(s) found`, issuesData.issues);
          }
          setDetectedIssues(issuesData.issues || []);
        }

        // Fetch device positions from backend
        const posRes = await fetch(`${API_BASE}/api/devices-positions`);
        const posData = await posRes.json();
        if (posData.success) {
          const deviceCount = Object.keys(posData.devices || {}).length;
          setDevicesPositions(posData.devices || {});
          if (deviceCount > 0) {
            console.log(`[IssueMap] Loaded ${deviceCount} devices:`, posData.devices);
          }
        }
      } catch (error) {
        console.error('[IssueMap] Error fetching real-time data:', error);
      }
    };

    // Fetch immediately and then every 500ms for immediate issue detection (near real-time)
    fetchRealTimeData();
    const interval = setInterval(fetchRealTimeData, 500);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    if (!canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();

    // Set canvas size
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Map dimensions (in virtual coordinates)
    const mapWidth = 250;
    const mapHeight = 200;
    const padding = 40;

    // Determine map center: use tower location if provided, otherwise use default center
    const mapCenterX = towerCenter ? towerCenter.x : 125;
    const mapCenterY = towerCenter ? towerCenter.y : 100;

    // Scale factors to convert virtual coordinates to canvas coordinates
    const scaleX = (canvas.width - 2 * padding) / mapWidth;
    const scaleY = (canvas.height - 2 * padding) / mapHeight;

    const toCanvasX = (x) => padding + (x - (mapCenterX - mapWidth / 2)) * scaleX;
    const toCanvasY = (y) => canvas.height - padding - (y - (mapCenterY - mapHeight / 2)) * scaleY;

    // Draw background
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    // Draw tower (optional)
    const hasTower = tower && typeof tower.x === 'number' && typeof tower.y === 'number' && typeof tower.r === 'number' && tower.r > 0;
    if (hasTower) {
      const { x: tx, y: ty, r: tr } = tower;
      const cx = toCanvasX(tx);
      const cy = toCanvasY(ty);
      const cr = tr * Math.min(scaleX, scaleY);

      // Draw inspection waypoints (20 points in circle)
      const numWaypoints = 20;
      ctx.fillStyle = '#fbbf24';
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1;
      // Waypoints should be 5 meters beyond the tower radius
      for (let i = 0; i < numWaypoints; i++) {
        const angle = (2 * Math.PI * i) / numWaypoints;
        const waypointRadius = tr + 5;
        const wx = tx + waypointRadius * Math.cos(angle);
        const wy = ty + waypointRadius * Math.sin(angle);
        const canvasWx = toCanvasX(wx);
        const canvasWy = toCanvasY(wy);
        
        // Draw small circles for waypoints
        ctx.beginPath();
        ctx.arc(canvasWx, canvasWy, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
      }

      // Tower center marker
      ctx.fillStyle = '#cbd5e1';
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = '#cbd5e1';
      ctx.font = '12px Arial';
      ctx.textAlign = 'left';
      ctx.fillText(`Tower center (${tx}, ${ty}) r=${tr}`, cx + 8, cy - 8);
    }

    // Draw grid
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    for (let x = 0; x <= mapWidth; x += 25) {
      const cx = toCanvasX(mapCenterX - mapWidth / 2 + x);
      ctx.beginPath();
      ctx.moveTo(cx, padding);
      ctx.lineTo(cx, canvas.height - padding);
      ctx.stroke();
    }
    for (let y = 0; y <= mapHeight; y += 25) {
      const cy = toCanvasY(mapCenterY - mapHeight / 2 + y);
      ctx.beginPath();
      ctx.moveTo(padding, cy);
      ctx.lineTo(canvas.width - padding, cy);
      ctx.stroke();
    }

    // Draw axis labels
    ctx.fillStyle = '#64748b';
    ctx.font = '12px Arial';
    ctx.textAlign = 'center';
    for (let x = 0; x <= mapWidth; x += 50) {
      const label = Math.round(mapCenterX - mapWidth / 2 + x);
      ctx.fillText(label, toCanvasX(mapCenterX - mapWidth / 2 + x), canvas.height - 20);
    }
    ctx.textAlign = 'right';
    for (let y = 0; y <= mapHeight; y += 50) {
      const label = Math.round(mapCenterY - mapHeight / 2 + y);
      ctx.fillText(label, padding - 10, toCanvasY(mapCenterY - mapHeight / 2 + y) + 4);
    }

    // Draw border
    ctx.strokeStyle = '#475569';
    ctx.lineWidth = 2;
    ctx.strokeRect(padding, padding, canvas.width - 2 * padding, canvas.height - 2 * padding);

    // Collect all entities for hover detection
    entitiesRef.current = [];

    // Draw issues from real detections (red squares)
    console.log(`[Canvas] ========== DRAWING ISSUES ==========`);
    console.log(`[Canvas] Total issues to draw: ${detectedIssues.length}`);
    console.log(`[Canvas] Issues array:`, detectedIssues);
    
    detectedIssues.forEach((issue, idx) => {
      const { coordinates, issue_type, timestamp, drone_id } = issue;
      console.log(`[Canvas] Issue ${idx + 1}:`, { issue_type, coordinates, drone_id });
      
      if (!coordinates || coordinates.x === undefined || coordinates.y === undefined) {
        console.error(`[Canvas] ✗ Issue ${idx + 1} has invalid coordinates:`, coordinates);
        return;
      }
      
      const cx = toCanvasX(coordinates.x);
      const cy = toCanvasY(coordinates.y);
      const size = 12;

      console.log(`[Canvas] Drawing red square at canvas position (${cx}, ${cy}) for virtual position (${coordinates.x}, ${coordinates.y})`);

      ctx.fillStyle = '#ef4444';
      ctx.fillRect(cx - size / 2, cy - size / 2, size, size);

      // Border
      ctx.strokeStyle = '#fca5a5';
      ctx.lineWidth = 2;
      ctx.strokeRect(cx - size / 2, cy - size / 2, size, size);

      entitiesRef.current.push({
        type: 'issue',
        issueType: issue_type,
        x: cx,
        y: cy,
        radius: size / 2,
        data: {
          type: 'Issue',
          issueType: issue_type.replace(/_/g, ' ').toUpperCase(),
          coordinates: `(${coordinates.x}, ${coordinates.y}, ${coordinates.z})`,
          'detected by': drone_id || 'Unknown',
          'detected at': new Date(timestamp * 1000).toLocaleTimeString()
        }
      });
    });
    console.log(`[Canvas] ========== FINISHED DRAWING ISSUES ==========`);

    // Handle mouse move for hover
    const handleMouseMove = (e) => {
      const rect = canvas.getBoundingClientRect();
      const mouseX = e.clientX - rect.left;
      const mouseY = e.clientY - rect.top;

      let found = false;
      for (const entity of entitiesRef.current) {
        const distance = Math.sqrt((mouseX - entity.x) ** 2 + (mouseY - entity.y) ** 2);
        if (distance <= entity.radius) {
          setHoveredEntity(entity.type);
          setTooltip({
            x: mouseX,
            y: mouseY,
            data: entity.data
          });
          found = true;
          break;
        }
      }

      if (!found) {
        setHoveredEntity(null);
        setTooltip(null);
      }
    };

    const handleMouseLeave = () => {
      setHoveredEntity(null);
      setTooltip(null);
    };

    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseleave', handleMouseLeave);

    return () => {
      canvas.removeEventListener('mousemove', handleMouseMove);
      canvas.removeEventListener('mouseleave', handleMouseLeave);
    };
  }, [detectedIssues, devicesPositions, tower, towerCenter]);

  return (
    <div className="issue-map-container">
      <canvas ref={canvasRef} className="issue-map-canvas" />

      {tooltip && (
        <div
          className="map-tooltip"
          style={{
            left: `${tooltip.x + 10}px`,
            top: `${tooltip.y + 10}px`
          }}
        >
          {Object.entries(tooltip.data).map(([key, value]) => (
            <div key={key} className="tooltip-row">
              <span className="tooltip-label">{key}:</span>
              <span className="tooltip-value">{value}</span>
            </div>
          ))}
        </div>
      )}

      <div className="map-legend">
        <div className="legend-item">
          <div className="legend-symbol issue-symbol"></div>
          <span>Issue (Red Square)</span>
        </div>
        <div className="legend-item">
          <div className="legend-symbol waypoint-symbol"></div>
          <span>Inspection waypoints</span>
        </div>
      </div>

    </div>
  );
}

export default IssueMap2D;
