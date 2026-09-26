# Farm assets and licenses

All scene-specific buildings, mascots, trees, fences, paths, pond, vegetables, parcels and signs are original procedural compositions authored in `frontend/src/components/farm/farm-scene.tsx`. They use box, sphere, cone, cylinder and roof geometry. No third-party GLTF, image, texture, audio, character, game asset, font download or AI-generated bitmap is included. Ordinary HTML/CSS supplies signs and interface typography using the project's existing system-font stack.

| Rendering dependency added | License | Purpose |
| --- | --- | --- |
| `three` | MIT | Geometry, materials, lighting, WebGL |
| `@react-three/fiber` | MIT | React renderer/frame lifecycle |
| `@react-three/drei` | MIT | HTML projections and constrained OrbitControls |
| `@types/three` (development) | MIT | Type declarations |

Versions and transitive licenses remain recorded in `frontend/package-lock.json` and the installed packages' LICENSE files. Direct resolved versions for this verification: Three 0.186.1, Fiber 9.8.1, Drei 10.7.9, types 0.186.0. Existing React 19 / Next 16 are retained. Fiber 9 is the React 19 line; see the [official Fiber introduction](https://r3f.docs.pmnd.rs/getting-started/introduction). Do not strip dependency license notices from distributed packages.

No external visual inspiration was copied. The ox, owl, raccoon, crow and mole are generic original animal designs. Screenshots are generated locally by browser tests and remain ignored test artifacts, not runtime assets.
