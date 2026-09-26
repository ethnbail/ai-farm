"use client";

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Html, OrbitControls } from "@react-three/drei";
import { useEffect, useLayoutEffect, useMemo, useRef } from "react";
import * as THREE from "three";
import type { OrbitControls as Controls } from "three-stdlib";
import {
  areas,
  buildings,
  type Area,
  type FarmState,
  type Motions,
} from "@/lib/farm-state";

// One bounded shared geometry/material library. No textures, model downloads or fonts.
const geometry = {
  box: new THREE.BoxGeometry(1, 1, 1),
  sphere: new THREE.SphereGeometry(0.5, 12, 8),
  cone: new THREE.ConeGeometry(0.5, 1, 7),
  cylinder: new THREE.CylinderGeometry(0.5, 0.5, 1, 12),
  roof: new THREE.ConeGeometry(0.72, 1, 4),
};
const materials = new Map<string, THREE.MeshStandardMaterial>();
function material(color: string) {
  if (!materials.has(color))
    materials.set(
      color,
      new THREE.MeshStandardMaterial({
        color,
        roughness: 0.95,
        flatShading: true,
      }),
    );
  return materials.get(color)!;
}
type Vector = [number, number, number];
function Part({
  p = [0, 0, 0],
  s = [1, 1, 1],
  r = [0, 0, 0],
  color = "#eee1c9",
  shape = "box",
}: {
  p?: Vector;
  s?: Vector;
  r?: Vector;
  color?: string;
  shape?: keyof typeof geometry;
}) {
  return (
    <mesh
      position={p}
      scale={s}
      rotation={r}
      geometry={geometry[shape]}
      material={material(color)}
      castShadow
      receiveShadow
      dispose={null}
    />
  );
}

export interface SceneMetrics {
  fps: number;
  frameMs: number;
  objects: number;
  calls: number;
  triangles: number;
  loadMs: number;
}
interface Props {
  states: Record<Area, FarmState>;
  motions: Motions;
  selected: Area | null;
  reset: number;
  onSelect: (area: Area) => void;
  regime: string;
  simplified: boolean;
  active: boolean;
  onFailure: (reason: string) => void;
  onReady: () => void;
  onMetrics: (metrics: SceneMetrics) => void;
  packages: boolean;
  labelPortal: React.RefObject<HTMLDivElement>;
}

function Mascot({
  kind,
  state,
  motion,
  origin,
}: {
  kind: Area;
  state: FarmState;
  motion: Motions[Area];
  origin: Vector;
}) {
  const ref = useRef<THREE.Group>(null);
  const crow = kind === "shadow",
    owl = kind === "agentB",
    ox = kind === "agentA",
    raccoon = kind === "marketplace";
  const body = crow
    ? "#46505a"
    : owl
      ? "#d1b384"
      : ox
        ? "#b78362"
        : raccoon
          ? "#8a9390"
          : "#a88d70";
  useFrame(({ clock }) => {
    if (!ref.current) return;
    const t = clock.elapsedTime;
    const busy = ["SCANNING", "ANALYZING", "TRADE_ACTIVE"].includes(state);
    let x = busy ? Math.sin(t * 1.3) * 0.22 : Math.sin(t * 0.3) * 0.04;
    let y = 0.68 + Math.sin(t * (busy ? 5 : 1.3)) * (busy ? 0.07 : 0.015);
    let z = busy ? -0.3 : 0;
    if (state === "SUCCESS") y += Math.abs(Math.sin(t * 3)) * 0.24;
    if (state === "REJECTED") z = 0.35;
    if (crow && motion?.target) {
      const progress = THREE.MathUtils.clamp(
        (Date.now() - motion.started) / (motion.until - motion.started),
        0,
        1,
      );
      const trip = Math.sin(progress * Math.PI) * 0.7;
      const destination = buildings[motion.target].position;
      x += (destination[0] - origin[0]) * trip;
      z += (destination[2] - origin[2]) * trip;
      y += trip * 1.2;
    }
    ref.current.position.set(x, y, z);
    ref.current.rotation.z =
      state === "LOSS" ? -0.16 : busy ? Math.sin(t * 2) * 0.05 : 0;
  });
  return (
    <group position={[0.9, 0, 2.1]} scale={ox ? 0.9 : 0.8}>
      <group ref={ref} position={[0, 0.68, 0]}>
        <Part shape="sphere" color={body} s={[0.85, 1.05, 0.65]} />
        <Part
          shape="sphere"
          p={[0, 0.55, 0.09]}
          s={[0.82, 0.72, 0.75]}
          color={body}
        />
        <Part
          shape="sphere"
          p={[0, -0.05, 0.24]}
          s={[0.62, 0.7, 0.27]}
          color={crow ? "#62717d" : "#efe0bd"}
        />
        {[-1, 1].map((side) => (
          <group key={side}>
            <Part
              p={[side * 0.23, -0.57, 0]}
              s={[0.17, 0.23, 0.25]}
              color="#4d4d43"
            />
            <Part
              shape="sphere"
              p={[side * 0.42, 0.06, 0]}
              s={[0.18, 0.6, 0.37]}
              r={[0, 0, side * 0.25]}
              color={body}
            />
            <Part
              shape="sphere"
              p={[side * 0.2, 0.61, 0.41]}
              s={[owl ? 0.34 : 0.23, owl ? 0.36 : 0.26, 0.12]}
              color={raccoon ? "#454e50" : "#f8f0d9"}
            />
            <Part
              shape="sphere"
              p={[side * 0.2, 0.61, 0.48]}
              s={[0.09, 0.13, 0.07]}
              color="#303c38"
            />
            {ox && (
              <Part
                shape="cone"
                p={[side * 0.4, 0.98, 0.03]}
                s={[0.19, 0.48, 0.2]}
                r={[0, 0, side * -0.5]}
                color="#f2ddb5"
              />
            )}
            {raccoon && (
              <Part
                shape="sphere"
                p={[side * 0.3, 0.97, 0]}
                s={[0.25, 0.3, 0.2]}
                color="#56615f"
              />
            )}
          </group>
        ))}
        <Part
          shape={ox ? "sphere" : "cone"}
          p={[0, 0.42, 0.48]}
          s={ox ? [0.48, 0.3, 0.26] : [0.2, 0.26, 0.28]}
          r={[Math.PI / 2, 0, 0]}
          color={ox ? "#e4bd99" : "#c7924f"}
        />
        {kind === "research" && (
          <>
            <Part p={[0, 1, 0]} s={[0.9, 0.08, 0.7]} color="#607760" />
            <Part p={[0, 1.11, 0]} s={[0.45, 0.2, 0.4]} color="#607760" />
            <Part
              p={[0, -0.05, 0.55]}
              s={[0.6, 0.1, 0.35]}
              r={[0.3, 0, 0]}
              color="#b4664e"
            />
          </>
        )}
        {raccoon && (
          <>
            <Part
              shape="sphere"
              p={[0.25, -0.1, -0.6]}
              s={[0.3, 0.35, 1]}
              r={[0, -0.3, 0]}
              color="#59635f"
            />
            {state === "ANALYZING" && (
              <Part p={[0, -0.06, 0.66]} s={[0.6, 0.5, 0.48]} color="#c69b60" />
            )}
          </>
        )}
      </group>
    </group>
  );
}

function Building({
  area,
  state,
  motion,
  selected,
  onSelect,
  labelPortal,
}: {
  area: Area;
  state: FarmState;
  motion: Motions[Area];
  selected: boolean;
  onSelect: Props["onSelect"];
  labelPortal: Props["labelPortal"];
}) {
  const b = buildings[area];
  const gate = useRef<THREE.Group>(null);
  const priceTag = useRef<THREE.Group>(null);
  const reacting = [
    "SCANNING",
    "ANALYZING",
    "TRADE_ACTIVE",
    "SUCCESS",
  ].includes(state);
  const dim = ["DATA_STALE", "OFFLINE"].includes(state);
  const lamp = dim
    ? "#7b8174"
    : state === "REJECTED" || state === "LOSS"
      ? "#ba7958"
      : reacting
        ? "#f0cc75"
        : "#e7dbb6";
  useFrame((_, dt) => {
    if (priceTag.current) {
      const progress = motion
        ? THREE.MathUtils.clamp(
            (Date.now() - motion.started) / (motion.until - motion.started),
            0,
            1,
          )
        : 0;
      priceTag.current.rotation.y =
        motion?.event === "price_drop_detected"
          ? Math.sin(progress * Math.PI) * Math.PI
          : 0;
    }
    if (gate.current)
      gate.current.rotation.z = THREE.MathUtils.damp(
        gate.current.rotation.z,
        state === "REJECTED" ? 0 : 1.3,
        5,
        dt,
      );
  });
  return (
    <group position={b.position}>
      <group
        onClick={(e) => {
          e.stopPropagation();
          onSelect(area);
        }}
        onPointerOver={(e) => {
          e.stopPropagation();
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={() => {
          document.body.style.cursor = "auto";
        }}
      >
        <Part
          p={[0, 0.12, 0]}
          s={[3.5, 0.25, 3.1]}
          color={selected ? "#e5bd71" : "#b8ad88"}
        />
        {area === "analytics" ? (
          <>
            <Part shape="cone" p={[0, 1.5, 0]} s={[2, 3, 2]} color="#d6c8a5" />
            <Part
              shape="roof"
              p={[0, 3, 0]}
              s={[1.8, 0.9, 1.8]}
              r={[0, Math.PI / 4, 0]}
              color="#768574"
            />
          </>
        ) : area === "shadow" ? (
          <>
            <Part p={[0, 0.8, 0]} s={[1.7, 1.4, 1.5]} color="#7b8582" />
            <Part
              shape="roof"
              p={[0, 1.8, 0]}
              s={[2.2, 0.6, 2]}
              r={[0, Math.PI / 4, 0]}
              color="#485e60"
            />
            <Part p={[1, 0.7, 1.5]} s={[0.12, 1.4, 0.12]} color="#75664c" />
            <Part p={[1, 1.4, 1.5]} s={[1, 0.12, 0.12]} color="#75664c" />
          </>
        ) : (
          <>
            <Part
              p={[0, 1.1, 0]}
              s={[2.8, 2, 2.4]}
              color={dim ? "#a3a394" : b.color}
            />
            <Part
              shape="roof"
              p={[0, 2.6, 0]}
              s={[3.3, 1.25, 3]}
              r={[0, Math.PI / 4, 0]}
              color={
                area === "agentA"
                  ? "#714b41"
                  : area === "marketplace"
                    ? "#718570"
                    : "#5b7470"
              }
            />
            <Part
              p={[-0.45, 0.7, 1.23]}
              s={[0.75, 1.25, 0.08]}
              color="#586550"
            />
            <Part
              p={[-0.45, 0.74, 1.29]}
              s={[0.05, 1.2, 0.03]}
              color="#e6d8b7"
            />
            <Part p={[0.74, 1.35, 1.24]} s={[0.68, 0.7, 0.1]} color="#f0e2c1" />
            <Part p={[0.74, 1.35, 1.3]} s={[0.48, 0.5, 0.04]} color={lamp} />
            <Part p={[1.4, 1.2, 0]} s={[0.05, 0.55, 0.6]} color={lamp} />
            {area === "agentA" && (
              <>
                <Part
                  p={[-0.8, 1.2, 1.3]}
                  s={[0.08, 2, 0.08]}
                  color="#ecdabc"
                />
                <Part p={[0, 1.2, 1.3]} s={[0.08, 2, 0.08]} color="#ecdabc" />
              </>
            )}
            {area === "agentB" && (
              <>
                <Part
                  shape="sphere"
                  p={[0, 3.05, 0]}
                  s={[1.9, 1.35, 1.9]}
                  color="#c6c9b2"
                />
                <Part
                  shape="cylinder"
                  p={[0.6, 3.45, 0.25]}
                  s={[0.35, 1.3, 0.35]}
                  r={[0, 0, -1]}
                  color="#566d66"
                />
              </>
            )}
            {area === "treasury" && (
              <>
                <Part
                  shape="cylinder"
                  p={[-1.8, 1.5, -0.4]}
                  s={[1.15, 2.8, 1.15]}
                  color="#c2b18d"
                />
                <Part
                  shape="cone"
                  p={[-1.8, 3.1, -0.4]}
                  s={[1.4, 0.55, 1.4]}
                  color="#708477"
                />
                <Part
                  p={[0.8, 2.9, -0.6]}
                  s={[0.4, 1.2, 0.4]}
                  color="#a47b60"
                />
              </>
            )}
            {area === "marketplace" && (
              <>
                <Part
                  p={[0, 1.6, 1.8]}
                  s={[3, 0.16, 1.3]}
                  r={[-0.12, 0, 0]}
                  color="#ece0b9"
                />
                {[-1.25, 1.25].map((x) => (
                  <Part
                    key={x}
                    p={[x, 0.8, 2.1]}
                    s={[0.1, 1.6, 0.1]}
                    color="#816c49"
                  />
                ))}
                <Part p={[0, 0.45, 1.8]} s={[2.5, 0.8, 0.6]} color="#9f8155" />
              </>
            )}
          </>
        )}
        <Part p={[1.55, 0.66, 1.55]} s={[0.12, 1.3, 0.12]} color="#75664c" />
        <Part
          shape="sphere"
          p={[1.55, 1.4, 1.55]}
          s={[0.35, 0.4, 0.35]}
          color={lamp}
        />
      </group>
      {(area === "agentA" || area === "agentB") && (
        <group position={[-1.35, 0.6, 2.1]}>
          <Part s={[0.12, 1.2, 0.12]} color="#8a7455" />
          <group ref={gate}>
            <Part
              p={[0.5, 0, 0]}
              s={[1, 0.12, 0.15]}
              color={state === "REJECTED" ? "#b7684d" : "#e6d3aa"}
            />
          </group>
        </group>
      )}
      {area === "marketplace" && (
        <group ref={priceTag} position={[-0.8, 1.3, 2.2]}>
          <Part
            s={[0.7, 0.45, 0.08]}
            color={
              motion?.event === "price_drop_detected" ? "#e6bd66" : "#f0e4c5"
            }
          />
          <Part p={[0, 0, 0.05]} s={[0.35, 0.05, 0.02]} color="#655d46" />
        </group>
      )}
      {motion?.event === "trade_closed" && (
        <Part
          shape="sphere"
          p={[0, 3.4, 0]}
          s={[0.24, 0.24, 0.24]}
          color="#e0c788"
        />
      )}
      {!["treasury", "analytics"].includes(area) && (
        <Mascot kind={area} state={state} motion={motion} origin={b.position} />
      )}
      {state === "SUCCESS" &&
        [0, 1, 2].map((i) => (
          <Part
            key={i}
            shape="roof"
            p={[-0.8 + i * 0.8, 3.7 + (i % 2) * 0.3, 0]}
            s={[0.17, 0.25, 0.17]}
            color="#e0b64f"
          />
        ))}
      <Html
        portal={labelPortal}
        position={[
          0,
          area === "agentB" ? 4 : area === "analytics" ? 4 : 3.5,
          0,
        ]}
        center
        zIndexRange={[8, 1]}
      >
        <button
          className={`farm-label ${selected ? "selected" : ""}`}
          onClick={() => onSelect(area)}
          aria-label={`Focus ${b.name}`}
        >
          <span>{b.name}</span>
          <small>{state.replaceAll("_", " ")}</small>
        </button>
      </Html>
    </group>
  );
}

function Trees({ reduced }: { reduced: boolean }) {
  const trunks = useRef<THREE.InstancedMesh>(null),
    crowns = useRef<THREE.InstancedMesh>(null);
  const points = useMemo(
    () =>
      Array.from({ length: reduced ? 10 : 22 }, (_, i) => {
        const angle = (i / (reduced ? 10 : 22)) * Math.PI * 2;
        return [
          Math.cos(angle) * 12.6,
          Math.sin(angle) * 9.4,
          1.3 + (i % 3) * 0.35,
        ];
      }),
    [reduced],
  );
  useLayoutEffect(() => {
    const object = new THREE.Object3D();
    points.forEach(([x, z, height], i) => {
      object.position.set(x, 0.65, z);
      object.scale.set(0.2, 1.3, 0.2);
      object.updateMatrix();
      trunks.current?.setMatrixAt(i, object.matrix);
      object.position.set(x, 1.4 + height / 2, z);
      object.scale.set(1.5, height + 1, 1.5);
      object.updateMatrix();
      crowns.current?.setMatrixAt(i, object.matrix);
    });
    if (trunks.current) trunks.current.instanceMatrix.needsUpdate = true;
    if (crowns.current) crowns.current.instanceMatrix.needsUpdate = true;
  }, [points]);
  return (
    <>
      <instancedMesh
        ref={trunks}
        args={[geometry.cylinder, material("#897152"), points.length]}
        castShadow
        dispose={null}
      />
      <instancedMesh
        ref={crowns}
        args={[geometry.cone, material("#7e9468"), points.length]}
        castShadow
        dispose={null}
      />
    </>
  );
}

function Environment({
  regime,
  simplified,
  packages,
}: Pick<Props, "regime" | "simplified" | "packages">) {
  const blades = useRef<THREE.Group>(null);
  useFrame((_, dt) => {
    if (blades.current)
      blades.current.rotation.z +=
        Math.min(dt, 0.05) *
        (regime === "HIGH_VOLATILITY"
          ? 0.42
          : regime === "LOW_VOLATILITY"
            ? 0.07
            : 0.17);
  });
  return (
    <>
      <Part
        shape="cylinder"
        p={[0, -0.6, 0]}
        s={[29, 1.1, 23]}
        color="#b6a17d"
      />
      <Part
        shape="cylinder"
        p={[0, -0.07, 0]}
        s={[28.6, 0.22, 22.6]}
        color="#aab58a"
      />
      <Part
        shape="cylinder"
        p={[0, 0.055, 0]}
        s={[8, 0.02, 7]}
        color="#dcc8a4"
      />
      {areas
        .filter((a) => a !== "treasury")
        .map((area) => {
          const [x, , z] = buildings[area].position;
          return (
            <Part
              key={area}
              p={[x / 2, 0.07, z / 2]}
              s={[1.2, 0.05, Math.hypot(x, z)]}
              r={[0, Math.atan2(x, z), 0]}
              color="#dcc8a4"
            />
          );
        })}
      <Part
        shape="cylinder"
        p={[-3, 0.06, 6.6]}
        s={[5, 0.12, 2.8]}
        color="#d7c8a1"
      />
      <Part
        shape="cylinder"
        p={[-3, 0.14, 6.6]}
        s={[4.5, 0.06, 2.4]}
        color="#87aaa5"
      />
      {[0, 1, 2].map((i) => (
        <Part
          key={i}
          p={[-7 + i * 0.75, 0.17, 6.3]}
          s={[0.45, 0.15, 2.4]}
          color="#876e50"
        />
      ))}
      {Array.from({ length: simplified ? 6 : 15 }, (_, i) => (
        <Part
          key={i}
          shape="sphere"
          p={[-7 + (i % 3) * 0.75, 0.37, 5.4 + Math.floor(i / 3) * 0.45]}
          s={[0.4, 0.4, 0.4]}
          color={i % 2 ? "#728459" : "#d0a36b"}
        />
      ))}
      {[-9, -6, -3, 0, 3, 6, 9].map((x) => (
        <group key={x}>
          <Part p={[x, 0.45, 8.8]} s={[0.15, 0.9, 0.15]} color="#ecddba" />
          <Part p={[x + 1.5, 0.62, 8.8]} s={[3, 0.12, 0.12]} color="#ecddba" />
          <Part p={[x + 1.5, 0.3, 8.8]} s={[3, 0.12, 0.12]} color="#ecddba" />
        </group>
      ))}
      <Trees reduced={simplified} />
      <group position={[0.3, 2.5, -5.9]} ref={blades}>
        {[0, 1, 2, 3].map((i) => (
          <group key={i} rotation={[0, 0, (i * Math.PI) / 2]}>
            <Part p={[0, 0.9, 0]} s={[0.3, 1.8, 0.12]} color="#f0e4c5" />
            <Part p={[0.15, 1, 0]} s={[0.5, 0.8, 0.08]} color="#d0b886" />
          </group>
        ))}
        <Part shape="sphere" s={[0.4, 0.4, 0.4]} color="#766950" />
      </group>
      {packages && (
        <group position={[8.1, 0.4, 5.1]}>
          <Part s={[0.7, 0.7, 0.7]} color="#b98d56" />
          <Part s={[0.12, 0.72, 0.72]} color="#ecdbaf" />
        </group>
      )}
    </>
  );
}

function CameraRig({
  selected,
  reset,
  simplified,
}: Pick<Props, "selected" | "reset" | "simplified">) {
  const ref = useRef<Controls>(null);
  const destination = useRef(new THREE.Vector3(0, 0, 0));
  const moving = useRef(true);
  const width = useThree((state) => state.size.width);
  const overviewZoom = Math.min(27, width / 34);
  useEffect(() => {
    destination.current.set(
      ...(selected ? buildings[selected].position : ([0, 0, 0] as Vector)),
    );
    moving.current = true;
  }, [selected, reset, width]);
  useFrame(({ camera }, delta) => {
    if (!ref.current) return;
    if (!moving.current) {
      ref.current.target.clamp(
        new THREE.Vector3(-10, 0, -8),
        new THREE.Vector3(10, 2, 8),
      );
      return;
    }
    const target = destination.current;
    ref.current.target.lerp(target, 1 - Math.exp(-delta * 3));
    const offset = new THREE.Vector3(19, 22, 26).multiplyScalar(
      selected ? 0.68 : 1,
    );
    camera.position.lerp(offset.add(target), 1 - Math.exp(-delta * 3));
    if (camera instanceof THREE.OrthographicCamera) {
      camera.zoom = THREE.MathUtils.damp(
        camera.zoom,
        overviewZoom * (selected ? 1.5 : 1),
        3,
        delta,
      );
      camera.updateProjectionMatrix();
    }
    ref.current.update();
    if (
      ref.current.target.distanceTo(target) < 0.005 &&
      camera.position.distanceTo(offset) < 0.02
    )
      moving.current = false;
  });
  return (
    <OrbitControls
      ref={ref}
      makeDefault
      enablePan={!simplified}
      enableZoom
      minZoom={8}
      maxZoom={55}
      minPolarAngle={0.4}
      maxPolarAngle={1.15}
      minAzimuthAngle={-0.8}
      maxAzimuthAngle={1.2}
      onStart={() => {
        moving.current = false;
      }}
    />
  );
}

function Monitor({
  onFailure,
  onReady,
  onMetrics,
}: Pick<Props, "onFailure" | "onReady" | "onMetrics">) {
  const { gl, scene } = useThree();
  const start = useRef(0),
    elapsed = useRef(0),
    frames = useRef(0),
    ready = useRef(false);
  const loadMs = useRef(0);
  useEffect(() => {
    start.current = performance.now();
    const failed = (e: Event) => {
      e.preventDefault();
      onFailure("WebGL context lost. Your live 2D dashboard is available.");
    };
    gl.domElement.addEventListener("webglcontextlost", failed);
    return () => gl.domElement.removeEventListener("webglcontextlost", failed);
  }, [gl, onFailure]);
  useFrame((_, delta) => {
    if (!ready.current) {
      ready.current = true;
      loadMs.current = Math.round(performance.now() - start.current);
      onReady();
    }
    if (document.hidden) return;
    elapsed.current += Math.min(delta, 1);
    frames.current++;
    if (elapsed.current >= 4) {
      let objects = 0;
      scene.traverse(() => objects++);
      onMetrics({
        fps: Math.round(frames.current / elapsed.current),
        frameMs: Math.round((elapsed.current / frames.current) * 1000),
        objects,
        calls: gl.info.render.calls,
        triangles: gl.info.render.triangles,
        loadMs: loadMs.current,
      });
      frames.current = 0;
      elapsed.current = 0;
    }
  });
  return null;
}

export default function FarmScene(props: Props) {
  const cool = ["BEAR_TREND", "RISK_OFF"].includes(props.regime);
  return (
    <Canvas
      orthographic
      camera={{
        position: [19, 22, 26],
        zoom: props.simplified ? 19 : 27,
        near: 0.1,
        far: 150,
      }}
      shadows={props.simplified ? false : { type: THREE.PCFShadowMap }}
      dpr={props.simplified ? 1 : [1, 1.5]}
      gl={{ antialias: !props.simplified, powerPreference: "low-power" }}
      frameloop={props.active ? "always" : "never"}
      fallback={<p>WebGL unavailable. Select 2D mode.</p>}
    >
      <color attach="background" args={[cool ? "#d8dfd5" : "#e6dfcb"]} />
      <fog attach="fog" args={[cool ? "#d8dfd5" : "#e6dfcb", 45, 90]} />
      <ambientLight intensity={1.25} />
      <hemisphereLight args={["#fff3d6", "#779074", 1.2]} />
      <directionalLight
        position={[-8, 18, 6]}
        intensity={cool ? 1.6 : 2.4}
        color="#ffedc6"
        castShadow={!props.simplified}
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
        shadow-camera-left={-18}
        shadow-camera-right={18}
        shadow-camera-top={18}
        shadow-camera-bottom={-18}
        shadow-bias={-0.0008}
      />
      <Environment
        regime={props.regime}
        simplified={props.simplified}
        packages={props.packages}
      />
      {areas.map((area) => (
        <Building
          key={area}
          area={area}
          state={props.states[area]}
          motion={props.motions[area]}
          selected={props.selected === area}
          onSelect={props.onSelect}
          labelPortal={props.labelPortal}
        />
      ))}
      <CameraRig
        selected={props.selected}
        reset={props.reset}
        simplified={props.simplified}
      />
      <Monitor
        onFailure={props.onFailure}
        onReady={props.onReady}
        onMetrics={props.onMetrics}
      />
    </Canvas>
  );
}
