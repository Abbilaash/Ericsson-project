import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import './TowerVisualization.css';

function TowerVisualization() {
  const canvasRef = useRef(null);
  const sceneRef = useRef(null);
  const cameraRef = useRef(null);
  const rendererRef = useRef(null);
  const animationRef = useRef(null);

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
      renderer.dispose();
    };
  }, []);

  useEffect(() => {
    if (!sceneRef.current) return;
    // No drone/robot rendering needed anymore
  }, []);

  return (
    <div className="tower-visualization">
      <canvas ref={canvasRef} />
    </div>
  );
}
