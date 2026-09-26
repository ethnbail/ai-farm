# Accessibility and fallback

Seven ordinary HTML buttons below the canvas offer the same building selection as 3D clicks and floating labels. Each names the building and shows its state as text; color alone is never the status channel. Pointer, touch, Enter and Space can select buildings. Controls have visible focus treatment. A selected detail panel receives focus; Escape/Close returns focus to the opener. Panels are nonmodal and do not trap keyboard navigation. Mobile uses a scrollable bottom sheet. Existing skip link and full detail routes remain available.

The paper-only safety bar stays visible while scrolling: PAPER TRADING / Simulated accounts only / No real money. The canvas region has a descriptive accessible name and directs users to equivalent HTML controls. Treasury describes totals as display-only and keeps independent execution accounts separate. The live connection has textual status and a last-heartbeat time. API failure warnings distinguish retained figures from current confirmations.

Both the user **Reduced motion** setting and OS `prefers-reduced-motion` choose the complete, existing 2D Dashboard. The OS preference cannot be accidentally overridden by the checkbox. The user can also explicitly switch to 2D, persisted in local storage; if storage is unavailable, the current-session controls still work. No sound, autoplay media, flashing effects or mandatory mouse interaction is added.

WebGL preflight failure, context loss, render exceptions and sustained low performance show a specific fallback notice and the real dashboard. The fallback retains portfolios, research, marketplace, details, live events and all Phase 1–3 routes. Financial data does not depend on successful GPU rendering.

Automated coverage includes keyboard focus/return, 390px layout with no horizontal overflow, bottom-sheet interaction, persisted 2D preference, system reduced motion, unavailable WebGL and actual WebGL context loss. Human screen-reader, color-contrast audit and physical touchscreen checks remain advisable; automated checks are not a WCAG certification.
