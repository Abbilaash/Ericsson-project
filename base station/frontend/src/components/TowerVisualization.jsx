import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import './TowerVisualization.css';

function TowerVisualization({ drones, robots }) {
  const canvasRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const animationRef = useRef(null);
  const [hoveredEntity, setHoveredEntity] = useState(null);
  const [mousePosition, setMousePosition] = useState({ x: 0, y: 0 });
  const droneObjectsRef = useRef([]);
  const robotObjectsRef = useRef([]);

  useEffect(() => {
    if (!canvasRef.current) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0f172a);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(
      75,
      canvasRef.current.clientWidth / canvasRef.current.clientHeight,
      0.1,
      1000
    );
    camera.position.set(15, 20, 25);
    camera.lookAt(0, 10, 0);
    cameraRef.current = camera;

    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true
    });
    renderer.setSize(canvasRef.current.clientWidth, canvasRef.current.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    rendererRef.current = renderer;

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
    scene.add(ambientLight);

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
    directionalLight.position.set(10, 20, 10);
    scene.add(directionalLight);

    const towerGeometry = new THREE.CylinderGeometry(2, 3, 30, 8);
    const towerMaterial = new THREE.MeshPhongMaterial({
      color: 0x475569,
      emissive: 0x1e293b,
      shininess: 30
    });
    const tower = new THREE.Mesh(towerGeometry, towerMaterial);
    tower.position.y = 15;
    scene.add(tower);

    const platformGeometry = new THREE.CylinderGeometry(5, 5, 1, 16);
    const platformMaterial = new THREE.MeshPhongMaterial({
      color: 0x334155,
      emissive: 0x1e293b
    });
    const platform = new THREE.Mesh(platformGeometry, platformMaterial);
    platform.position.y = 0;
    scene.add(platform);

    const gridHelper = new THREE.GridHelper(40, 20, 0x334155, 0x1e293b);
    gridHelper.position.y = 0.01;
    scene.add(gridHelper);

    // Draw tower boundary (trace actual tower base outline - 8-sided octagon)
    const towerBaseRadius = 3;  // Bottom radius of tower
    const towerSegments = 8;    // Same as tower geometry
    const boundaryPoints = [];
    for (let i = 0; i <= towerSegments; i++) {
      const angle = (i / towerSegments) * Math.PI * 2;
      boundaryPoints.push(
        new THREE.Vector3(
          towerBaseRadius * Math.cos(angle),
          0.05,  // Just above ground
          towerBaseRadius * Math.sin(angle)
        )
      );
    }
    const boundaryGeometry = new THREE.BufferGeometry().setFromPoints(boundaryPoints);
    const boundaryMaterial = new THREE.LineBasicMaterial({ color: 0xe2e8f0, linewidth: 3 });
    const boundaryLine = new THREE.Line(boundaryGeometry, boundaryMaterial);
    scene.add(boundaryLine);

    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    const handleMouseMove = (event) => {
      const rect = canvasRef.current.getBoundingClientRect();
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);

      const allObjects = [...droneObjectsRef.current, ...robotObjectsRef.current];
      const intersects = raycaster.intersectObjects(allObjects);

      if (intersects.length > 0) {
        const hoveredObj = intersects[0].object;
        setHoveredEntity(hoveredObj.userData);
        setMousePosition({ x: event.clientX, y: event.clientY });
      } else {
        setHoveredEntity(null);
      }
    };

    canvasRef.current.addEventListener('mousemove', handleMouseMove);

    const handleResize = () => {
      if (!canvasRef.current) return;
      camera.aspect = canvasRef.current.clientWidth / canvasRef.current.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(canvasRef.current.clientWidth, canvasRef.current.clientHeight);
    };

    window.addEventListener('resize', handleResize);

    const animate = () => {
      animationRef.current = requestAnimationFrame(animate);

      camera.position.x = Math.cos(Date.now() * 0.0001) * 25;
      camera.position.z = Math.sin(Date.now() * 0.0001) * 25;
      camera.lookAt(0, 10, 0);

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
      window.removeEventListener('resize', handleResize);
      if (canvasRef.current) {
        canvasRef.current.removeEventListener('mousemove', handleMouseMove);
      }
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    if (!sceneRef.current) return;

    // Remove old drone objects
    droneObjectsRef.current.forEach(obj => sceneRef.current.remove(obj));
    droneObjectsRef.current = [];

    drones.forEach(drone => {
      // Get position from drone.position object (x, y, z) or use defaults
      const position = drone.position || {};
      const posX = position.x !== undefined ? Number(position.x) : 0;
      const posY = position.y !== undefined ? Number(position.y) : 0;
      const posZ = position.z !== undefined ? Number(position.z) : 10;

      // Skip if no valid position data
      if (position.x === undefined && position.y === undefined && position.z === undefined) {
        return;
      }

      const getColor = () => {
        const battery = drone.battery || 100;
        if (battery < 20) return 0xef4444; // Red for low battery
        if (drone.status === 'INSPECTING' || drone.status === 'ACTIVE') return 0x22c55e; // Green for active
        if (drone.status === 'BATTERY_LOW') return 0xef4444; // Red for battery low
        return 0x60a5fa; // Blue for idle
      };

      // Create smaller dot for drone (0.3 radius instead of 0.5)
      const droneGeometry = new THREE.SphereGeometry(0.3, 16, 16);
      const droneMaterial = new THREE.MeshPhongMaterial({
        color: getColor(),
        emissive: getColor(),
        emissiveIntensity: 0.6
      });
      const droneMesh = new THREE.Mesh(droneGeometry, droneMaterial);

      // Set position using actual coordinates (no scaling needed, use meters directly)
      droneMesh.position.set(posX, posZ, posY); // Three.js uses Y-up, so Z is height

      droneMesh.userData = {
        type: 'DRONE',
        deviceType: 'DRONE',
        id: drone.id,
        battery: drone.battery || 'N/A',
        status: drone.status || 'UNKNOWN',
        position: `(${posX.toFixed(2)}, ${posY.toFixed(2)}, ${posZ.toFixed(2)})`
      };

      sceneRef.current.add(droneMesh);
      droneObjectsRef.current.push(droneMesh);
    });

    // Remove old robot objects
    robotObjectsRef.current.forEach(obj => sceneRef.current.remove(obj));
    robotObjectsRef.current = [];

    robots.forEach(robot => {
      // Get position from robot.position object (x, y, z) or use defaults
      const position = robot.position || {};
      const posX = position.x !== undefined ? Number(position.x) : 0;
      const posY = position.y !== undefined ? Number(position.y) : 0;
      const posZ = position.z !== undefined ? Number(position.z) : 0;

      // Skip if no valid position data
      if (position.x === undefined && position.y === undefined && position.z === undefined) {
        return;
      }

      const getColor = () => {
        const battery = robot.battery || 100;
        if (battery < 20) return 0xef4444; // Red for low battery
        if (robot.busy) return 0xeab308; // Yellow for busy
        return 0x22c55e; // Green for idle
      };

      // Create smaller dot for robot (0.3 size box instead of 0.8)
      const robotGeometry = new THREE.BoxGeometry(0.3, 0.3, 0.3);
      const robotMaterial = new THREE.MeshPhongMaterial({
        color: getColor(),
        emissive: getColor(),
        emissiveIntensity: 0.6
      });
      const robotMesh = new THREE.Mesh(robotGeometry, robotMaterial);

      // Set position using actual coordinates
      robotMesh.position.set(posX, posZ, posY); // Three.js uses Y-up, so Z is height

      robotMesh.userData = {
        type: 'ROBOT',
        deviceType: 'ROBOT',
        id: robot.id,
        battery: robot.battery || 'N/A',
        status: robot.busy ? 'BUSY' : 'IDLE',
        taskId: robot.current_task,
        position: `(${posX.toFixed(2)}, ${posY.toFixed(2)}, ${posZ.toFixed(2)})`
      };

      sceneRef.current.add(robotMesh);
      robotObjectsRef.current.push(robotMesh);
    });
  }, [drones, robots]);

  return (
    <div className="tower-visualization">
      <canvas ref={canvasRef} />
      {hoveredEntity && (
        <div
          className="tooltip"
          style={{
            left: mousePosition.x + 10,
            top: mousePosition.y + 10
          }}
        >
          <div className="tooltip-header">
            {hoveredEntity.deviceType || hoveredEntity.type} - {hoveredEntity.id}
          </div>
          <div className="tooltip-content">
            <div><strong>Device Type:</strong> {hoveredEntity.deviceType || hoveredEntity.type}</div>
            <div><strong>Device ID:</strong> {hoveredEntity.id}</div>
            <div>Battery: {hoveredEntity.battery}%</div>
            <div>Status: {hoveredEntity.status}</div>
            {hoveredEntity.taskId && <div>Task: {hoveredEntity.taskId}</div>}
            <div>Position: {hoveredEntity.position}</div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TowerVisualization;
