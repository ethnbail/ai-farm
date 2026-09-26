# Farm performance

The renderer is lazy-loaded, client-only, with a staged text loading state. Procedural low-poly primitives avoid model downloads, large textures and font atlases. Geometry and a bounded material palette are reused; trees use instanced meshes. Normal Three.js frustum culling remains enabled. There is one filtered 1024px directional shadow map, no ambient-occlusion pass, bloom, audio or other post-processing. See the [React Three Fiber performance guide](https://r3f.docs.pmnd.rs/advanced/scaling-performance) for the underlying rendering techniques.

Desktop pixel ratio is capped at 1.5; simplified mode uses 1, disables shadows/antialiasing and reduces trees from 22 to 10 and crop props from 15 to 6. The camera fits viewport width independently of quality. Mobile keeps all seven functional buildings and mascots, rather than hiding backend capabilities. Offscreen/hidden canvases stop frame rendering; API state still reconciles.

## Monitoring and degradation

Four-second local sampling windows estimate FPS, frame interval, scene object count, render calls and triangles. The load metric measures FarmWorld mount to the first scene frame, including lazy module load—not network-only transfer time. Metrics are visible only in the development debug panel. No telemetry is sent externally. Lightweight FPS sampling also operates in production solely to select fallback.

After a 10-second warmup, three consecutive samples below 20 FPS switch to simplified rendering. Three further slow samples select the full 2D dashboard. The retry control can attempt 3D again. Frame gaps are capped for sampling so returning from a background tab cannot alone drive a sustained fallback.

## Observed local checks

Chrome on the development Mac, 1440×1100 desktop / 390×844 mobile viewport, mock idle backend:

| Measurement | Desktop | Simplified mobile viewport |
| --- | --- | --- |
| Final sampled FPS | 29 | 30 |
| Frame interval estimate | 35 ms | 33 ms |
| Scene objects | 270 | 261 |
| Render calls, including shadow work | 416 | 190 |
| Rendered triangles | 30,928 | 12,320 |

Mount-to-first-frame was 741 ms in this warm development-server run. Earlier separate samples before the final tag addition measured 56/59 FPS; local headless results vary with concurrent browser/test load. These are diagnostic samples, not a guaranteed 60-FPS benchmark. Physical MacBook Air, iOS Safari, Android and tablet testing remain recommended before broad rollout. The browser suite actually renders WebGL in Chrome; it does not replace the scene with an image mock.

Potential future optimization if device profiling requires it: instance more repeated architectural parts and remove desktop shadows before lowering functionality. Do not add heavy effects to conceal slow rendering. The full data-driven 2D fallback remains available.
