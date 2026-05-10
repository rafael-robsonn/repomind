import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

const LANG_COLORS = {
  python: 0x3776ab,
  javascript: 0xf7df1e,
  typescript: 0x3178c6,
  rust: 0xdea584,
  go: 0x00add8,
  java: 0xb07219,
  cpp: 0x9c33ff,
  c: 0x555555,
  ruby: 0xcc342d,
  unknown: 0x666666,
};

function computeLayout(nodes, edges, iterations = 100) {
  const positions = {};
  nodes.forEach((n, i) => {
    const phi = Math.acos(1 - (2 * (i + 0.5)) / nodes.length);
    const theta = Math.PI * (1 + Math.sqrt(5)) * (i + 0.5);
    positions[n.id] = {
      x: Math.cos(theta) * Math.sin(phi) * 30,
      y: Math.sin(theta) * Math.sin(phi) * 30,
      z: Math.cos(phi) * 30,
      vx: 0, vy: 0, vz: 0,
    };
  });

  const REPULSION = 50;
  const ATTRACTION = 0.02;
  const DAMPING = 0.85;
  const CENTER_GRAVITY = 0.005;

  for (let iter = 0; iter < iterations; iter++) {
    for (let i = 0; i < nodes.length; i++) {
      const a = positions[nodes[i].id];
      for (let j = i + 1; j < nodes.length; j++) {
        const b = positions[nodes[j].id];
        const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
        const distSq = dx * dx + dy * dy + dz * dz + 0.1;
        const dist = Math.sqrt(distSq);
        const force = REPULSION / distSq;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        const fz = (dz / dist) * force;
        a.vx += fx; a.vy += fy; a.vz += fz;
        b.vx -= fx; b.vy -= fy; b.vz -= fz;
      }
    }

    edges.forEach(e => {
      const a = positions[e.source];
      const b = positions[e.target];
      if (!a || !b) return;
      const dx = b.x - a.x, dy = b.y - a.y, dz = b.z - a.z;
      a.vx += dx * ATTRACTION; a.vy += dy * ATTRACTION; a.vz += dz * ATTRACTION;
      b.vx -= dx * ATTRACTION; b.vy -= dy * ATTRACTION; b.vz -= dz * ATTRACTION;
    });

    Object.values(positions).forEach(p => {
      p.vx -= p.x * CENTER_GRAVITY;
      p.vy -= p.y * CENTER_GRAVITY;
      p.vz -= p.z * CENTER_GRAVITY;
    });

    Object.values(positions).forEach(p => {
      p.x += p.vx; p.y += p.vy; p.z += p.vz;
      p.vx *= DAMPING; p.vy *= DAMPING; p.vz *= DAMPING;
    });
  }

  return positions;
}

export default function GraphViz3D({ graph, highlightFiles = [], onNodeClick, height = 360 }) {
  const mountRef = useRef(null);
  const sceneRef = useRef({});
  const [hoveredNode, setHoveredNode] = useState(null);

  const highlightFilesRef = useRef(highlightFiles);
  useEffect(() => {
    highlightFilesRef.current = highlightFiles;
  }, [highlightFiles]);

  // Debug:
  useEffect(() => {
    if (highlightFiles && highlightFiles.length > 0 && graph?.nodes) {
      const normalize = (p) => (p || "").replace(/\\/g, "/").toLowerCase();
      const highlightSet = new Set(highlightFiles.map(normalize));
      const highlightBasenames = new Set(
        highlightFiles.map(p => normalize(p).split("/").pop())
      );

      const matches = graph.nodes.filter(n => {
        const nid = normalize(n.id);
        const basename = nid.split("/").pop();
        return highlightSet.has(nid)
          || highlightBasenames.has(basename)
          || [...highlightSet].some(h => nid.endsWith(h) || h.endsWith(nid));
      });
      console.log(`[GraphViz3D] highlightFiles:`, highlightFiles);
      console.log(`[GraphViz3D] matched ${matches.length}/${graph.nodes.length} nodes:`, matches.map(m => m.id));
      if (matches.length === 0 && graph.nodes.length > 0) {
        console.log(`[GraphViz3D] Sample graph node ids:`, graph.nodes.slice(0, 5).map(n => n.id));
      }
    }
  }, [highlightFiles, graph]);

  useEffect(() => {
    if (!graph || !graph.nodes || graph.nodes.length === 0) return;

    const mount = mountRef.current;
    const width = mount.clientWidth;

    // Scene setup
    const scene = new THREE.Scene();
    scene.fog = new THREE.FogExp2(0x070707, 0.012);

    const camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 2000);
    camera.position.set(0, 0, 90);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(window.devicePixelRatio);
    renderer.setSize(width, height);
    renderer.setClearColor(0x070707, 1);
    mount.appendChild(renderer.domElement);

    // Layout
    const positions = computeLayout(graph.nodes, graph.edges);

    const nodeMeshes = {};
    const nodeGroup = new THREE.Group();

    graph.nodes.forEach(node => {
      const pos = positions[node.id];
      const radius = Math.max(0.6, Math.min(2.5, Math.log(node.loc + 1) * 0.3));
      const color = LANG_COLORS[node.group] || LANG_COLORS.unknown;

      const geometry = new THREE.SphereGeometry(radius, 16, 16);
      const material = new THREE.MeshPhongMaterial({
        color,
        emissive: color,
        emissiveIntensity: 0.2,
        shininess: 80,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.position.set(pos.x, pos.y, pos.z);
      mesh.userData = { node, baseColor: color, baseEmissive: 0.2 };

      nodeGroup.add(mesh);
      nodeMeshes[node.id] = mesh;
    });
    scene.add(nodeGroup);

    const edgeGroup = new THREE.Group();
    graph.edges.forEach(edge => {
      const a = positions[edge.source];
      const b = positions[edge.target];
      if (!a || !b) return;

      const geometry = new THREE.BufferGeometry().setFromPoints([
        new THREE.Vector3(a.x, a.y, a.z),
        new THREE.Vector3(b.x, b.y, b.z),
      ]);
      const material = new THREE.LineBasicMaterial({
        color: 0x333333,
        transparent: true,
        opacity: 0.4,
      });
      const line = new THREE.Line(geometry, material);
      edgeGroup.add(line);
    });
    scene.add(edgeGroup);

    // ── Lights ──────────────────────────────────────────────────────
    scene.add(new THREE.AmbientLight(0x404040, 1.5));
    const accent = new THREE.PointLight(0xe8400c, 1, 200);
    accent.position.set(40, 40, 40);
    scene.add(accent);
    const fill = new THREE.PointLight(0x4a9eff, 0.6, 200);
    fill.position.set(-40, -20, 30);
    scene.add(fill);

    // ── Mouse interaction ───────────────────────────────────────────
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();
    let isDragging = false;
    let prevMouse = { x: 0, y: 0 };
    let rotation = { x: 0, y: 0 };
    let autoRotate = true;

    const handleMouseDown = (e) => {
      isDragging = true;
      autoRotate = false;
      prevMouse = { x: e.clientX, y: e.clientY };
    };
    const handleMouseUp = () => { isDragging = false; };
    const handleMouseMove = (e) => {
      const rect = mount.getBoundingClientRect();
      mouse.x = ((e.clientX - rect.left) / width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / height) * 2 + 1;

      if (isDragging) {
        rotation.y += (e.clientX - prevMouse.x) * 0.005;
        rotation.x += (e.clientY - prevMouse.y) * 0.005;
        prevMouse = { x: e.clientX, y: e.clientY };
      } else {
        // Hover
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(nodeGroup.children);
        if (hits.length > 0) {
          setHoveredNode(hits[0].object.userData.node);
          mount.style.cursor = "pointer";
        } else {
          setHoveredNode(null);
          mount.style.cursor = "grab";
        }
      }
    };
    const handleWheel = (e) => {
      e.preventDefault();
      camera.position.z += e.deltaY * 0.05;
      camera.position.z = Math.max(20, Math.min(200, camera.position.z));
    };
    const handleClick = (e) => {
      if (Math.abs(e.clientX - prevMouse.x) > 3) return;
      raycaster.setFromCamera(mouse, camera);
      const hits = raycaster.intersectObjects(nodeGroup.children);
      if (hits.length > 0 && onNodeClick) {
        onNodeClick(hits[0].object.userData.node);
      }
    };

    mount.addEventListener("mousedown", handleMouseDown);
    window.addEventListener("mouseup", handleMouseUp);
    mount.addEventListener("mousemove", handleMouseMove);
    mount.addEventListener("wheel", handleWheel, { passive: false });
    mount.addEventListener("click", handleClick);

    let animId;
    const animate = () => {
      if (autoRotate) rotation.y += 0.0018;
      nodeGroup.rotation.x = rotation.x;
      nodeGroup.rotation.y = rotation.y;
      edgeGroup.rotation.x = rotation.x;
      edgeGroup.rotation.y = rotation.y;

      const currentHighlights = highlightFilesRef.current || [];
      const time = Date.now() * 0.003;
      const normalize = (p) => (p || "").replace(/\\/g, "/").toLowerCase();
      const highlightSet = new Set(currentHighlights.map(normalize));
      const highlightBasenames = new Set(
        currentHighlights.map(p => normalize(p).split("/").pop()).filter(b => b && b.length > 3)
      );

      Object.entries(nodeMeshes).forEach(([id, mesh]) => {
        const normId = normalize(id);
        const idBasename = normId.split("/").pop();
        const isHighlighted = highlightSet.has(normId)
          || highlightBasenames.has(idBasename)
          || [...highlightSet].some(h => h && (normId.endsWith("/" + h) || h.endsWith("/" + normId)));

        if (isHighlighted) {
          mesh.material.emissive.setHex(0xe8400c);
          mesh.material.emissiveIntensity = 0.5 + Math.sin(time * 2) * 0.4;
          mesh.scale.setScalar(1.6 + Math.sin(time * 2) * 0.2);
        } else {
          mesh.material.emissive.setHex(mesh.userData.baseColor);
          mesh.material.emissiveIntensity = mesh.userData.baseEmissive;
          mesh.scale.setScalar(1);
        }
      });

      renderer.render(scene, camera);
      animId = requestAnimationFrame(animate);
    };
    animate();

    sceneRef.current = { renderer, mount, animId };

    const handleResize = () => {
      const w = mount.clientWidth;
      camera.aspect = w / height;
      camera.updateProjectionMatrix();
      renderer.setSize(w, height);
    };
    window.addEventListener("resize", handleResize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", handleResize);
      window.removeEventListener("mouseup", handleMouseUp);
      mount.removeEventListener("mousedown", handleMouseDown);
      mount.removeEventListener("mousemove", handleMouseMove);
      mount.removeEventListener("wheel", handleWheel);
      mount.removeEventListener("click", handleClick);
      if (renderer.domElement && mount.contains(renderer.domElement)) {
        mount.removeChild(renderer.domElement);
      }
      renderer.dispose();
    };
  }, [graph, height]);

  return (
    <div style={{ position: "relative", width: "100%", height }}>
      <div ref={mountRef} style={{ width: "100%", height: "100%", cursor: "grab" }} />

      {/* Legend */}
      <div style={{
        position: "absolute",
        top: 10, left: 10,
        background: "rgba(7,7,7,0.7)",
        backdropFilter: "blur(8px)",
        border: "1px solid #1a1a1a",
        borderRadius: 5,
        padding: "8px 10px",
        fontSize: 10,
        fontFamily: "'JetBrains Mono', monospace",
        color: "#888",
        pointerEvents: "none",
      }}>
        <div style={{ marginBottom: 4, color: "#666", letterSpacing: "0.08em" }}>LEGEND</div>
        {Object.entries(LANG_COLORS).slice(0, 5).map(([lang, color]) => (
          <div key={lang} style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 2 }}>
            <div style={{ width: 8, height: 8, borderRadius: "50%", background: `#${color.toString(16).padStart(6, '0')}` }} />
            <span>{lang}</span>
          </div>
        ))}
      </div>

      {/* Stats */}
      {graph && (
        <div style={{
          position: "absolute",
          top: 10, right: 10,
          background: "rgba(7,7,7,0.7)",
          backdropFilter: "blur(8px)",
          border: "1px solid #1a1a1a",
          borderRadius: 5,
          padding: "8px 12px",
          fontSize: 10,
          fontFamily: "'JetBrains Mono', monospace",
          color: "#888",
          pointerEvents: "none",
        }}>
          <div style={{ color: "#e8400c", letterSpacing: "0.08em", marginBottom: 4 }}>KNOWLEDGE GRAPH</div>
          <div>{graph.stats?.showing_nodes || graph.nodes.length} nodes</div>
          <div>{graph.stats?.showing_edges || graph.edges.length} edges</div>
          {graph.stats?.total_files && (
            <div style={{ color: "#444", marginTop: 4 }}>
              of {graph.stats.total_files} files total
            </div>
          )}
        </div>
      )}

      {/* Hover tooltip */}
      {hoveredNode && (
        <div style={{
          position: "absolute",
          bottom: 10, left: 10,
          background: "rgba(7,7,7,0.92)",
          backdropFilter: "blur(8px)",
          border: "1px solid #e8400c40",
          borderRadius: 5,
          padding: "8px 12px",
          fontSize: 11,
          fontFamily: "'JetBrains Mono', monospace",
          color: "#e0e0e0",
          pointerEvents: "none",
          maxWidth: "60%",
        }}>
          <div style={{ color: "#e8400c", marginBottom: 3 }}>{hoveredNode.label}</div>
          <div style={{ color: "#666", fontSize: 10 }}>{hoveredNode.path}</div>
          <div style={{ marginTop: 4, display: "flex", gap: 10, fontSize: 10, color: "#888" }}>
            <span>{hoveredNode.loc} LOC</span>
            <span>{hoveredNode.symbols} symbols</span>
            <span>↓{hoveredNode.in_degree} ↑{hoveredNode.out_degree}</span>
          </div>
        </div>
      )}

      {/* Hint */}
      <div style={{
        position: "absolute",
        bottom: 10, right: 10,
        fontSize: 9,
        color: "#444",
        fontFamily: "'JetBrains Mono', monospace",
        pointerEvents: "none",
      }}>
        DRAG · SCROLL · CLICK
      </div>
    </div>
  );
}
