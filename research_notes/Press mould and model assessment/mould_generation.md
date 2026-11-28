# Press mould generation: equation-playground (assessment of the code as a design for pressing clay into a resin-printed mould)

Method: read geometry.py, clay.py, app.py, README.md, tests; ran `geometry.build_all` (python -I) on 15 designs from docs/earrings and docs/fractals in two configs (A = app defaults: Full 3D two-sided, pins, margin 6.5; B = MouldOptions() dataclass defaults: flat back, no pins, margin 4.0), size 30 mm, px 0.05, n=800 samples, loop auto. Scratch scripts and raw JSON: /tmp/claude-0/-home-user-press-moulds/6460356d-7c49-5685-80ea-e29db7f086ce/scratchpad/ (run1.py, deep1-5.py, cl.py, out_*.json). All file refs are equation-playground/ files. No repo file modified. docs/earrings has no README (only earrings.json + png), so earring size is unknown; I used 30 mm for them (labelled). Machine: 4 cores, 16 GB, python 3.13, numpy 2.5.3.

## 1. How is the mould built, and what are the real default numbers?

### Takeaway
The mould is one grid solid: block top face is flat at z=T, the form heightmap H is subtracted as a cavity, plus gutter/vents/pockets/pin sockets cut into the face, chamfered bottom, mesh simplified to <=600k faces. Defaults: T = H.max + 3.0 mm wall (4.5 mm for a looped design), 20 deg draft, 4 mm zero-padding plus 4.0 mm (dataclass) or 6.5 mm (UI) margin, 3 pins 3.0 mm dia, 0.15 mm nominal clearance. A pair mould is about 93 x 54 x 4.5 mm and about 21 ml of resin per part.

### Cited Findings
- Form defaults: size 40 mm, strand 1.8 w x 1.2 h, draft 20 deg, px 0.05, loop od 5.0 / id 1.8 / h 1.5, relief 3.0 — geometry.py:24-38. App uses the same (app.py:247-264).
- Mould defaults: wall 3.0, margin 4.0, pad 4.0, land 0.8, gutter 1.6 w x 0.8 d, chamfer 0.5, pair True, gap 1.0, lid_t 5.0, vents 4, pockets True (pocket_land 0.6, w 0.6, min area 0.3 mm2), two_sided False, pins False, pin_d 3.0, pin_h 2.0, pin_clear 0.15 — geometry.py:44-63. UI differs: margin 6.5, two_sided True and pins True by default (app.py:268-282).
- Block thickness T = H.max() + wall (geometry.py:522). Cavity depth = H (Zb = T - Db, :537). Looped design H.max = 1.5 (loop_h) so T = 4.5; no loop gives T = 4.2 (measured, loop off). Floor under strands = T - 1.2 = 3.3 mm, under the loop 3.0.
- Strand profile: dome h*sqrt(1-q^2) capped by draft line (r-d)*tan(90-draft) — _profile, geometry.py:144-148. Walls are therefore 20 deg off the pull direction by construction.
- Face flatness: only gutter, vent, pocket and socket cells are lowered; everything else is exactly z=T (Zb=T-Db, Db=0 outside). Measured fraction of cells at exactly T: 57.5% for the Lissajous pair (A). Gutter ring is `0.8 < dist <= 2.4` mm from the form edge (geometry.py:444), so a 0.8 mm land at face level surrounds the cavity, which is what a blade shaves against.
- Vents: 4 per cavity by default, width VENT_W 1.2 mm, depth = gutter_d 0.8, straight to block edge, spread by angle (_place_vents geometry.py:455-502). Pair mode adds continuation strips through the 1.0 mm gap and a shared full-height channel at the gap centre when any vent points +x (:547-549). Requested vents achieved in all runs: 0,1,4,8,12 requested -> 0,1,4,8,12 placed (Sierpinski order 3, px 0.1).
- Pockets: enclosed background regions get a 0.8-deep pocket where an opening by a 0.6 mm disc at >0.6 mm from the form leaves >=0.3 mm2 (geometry.py:431-440). Measured: Sierpinski order 3 has 31 enclosed gaps but only 8 pockets; Snow crystal 7 gaps / 1 pocket; Ring gasket 15 / 6; Lattice 21 / 13.
- Pins: 3 pins at three block corners (the 4th corner empty), centred in the margin at margin/2 from each edge; third pin is pin_d+1.0 = 4.0 mm so the block cannot be closed backwards (geometry.py:553-563). Pins on the lid at mirrored x (:557). Pin tip chamfer 30 deg from axis, 0.4 mm (:505-510). Socket depth pin_h + 0.3 = 2.3 mm. If margin < pin_d + 1 + 2*clear + 2*PIN_WALL = 6.3 the margin is grown and a warning added (:525-528).
- Measured pin fit on Lissajous A (px 0.05, area-equivalent radius at 1 mm above socket floor): socket r 1.672, pin r 1.472 -> 0.199 mm radial clearance (nominal 0.15); big pin 0.202 mm. Socket floor 2.20 mm thick. Resin from big socket to block edge 1.05 mm, small sockets 1.55 mm. Pin tip 2.00 mm above lid face.
- Pair mode: left cavity L, right cavity is H[:, ::-1] (mirror), gap 1.0 mm (geometry.py:535-536). Two-sided top half = Dt[:, ::-1] (mirror of the whole block), pins mirrored in x, so flipping the lid about the vertical axis registers (verified by reading :557/:569/:584; not geometrically boolean-tested).
- Lid: Flat back + no pins = plain box lid_t (5.0) thick (geometry.py:577-581). Two-sided: lid = mirrored top-half cavity, thickness T + pin_h; lid_t has no effect in Full 3D (measured lid z-extent 6.5 = 4.5 + 2.0; flat+pins 7.0 = 5.0 + 2.0).
- Measured block sizes (px 0.05, size 30, config A): 85.6-93.4 x 49.8-56.1 x 4.5 mm (surface quilt 6.0 mm thick); config B 80.6-88.4 x 44.8-51.1. Resin A: mould 19.6-22.3 ml, lid 20.1-22.8 ml (about 42 ml per pair set); B: mould 16.6-19.1 ml, lid 5 mm box 19.6-22.6 ml.

### Inferences
- A 4.5 mm resin plate with 1.5 mm cavity relief is thin for hand pressing / rolling; floor under the loop is 3.0 mm, socket floors 2.2 mm (inferred; no test of mechanical strength).
- UI help says "Pins need 6.3 or more" but the code silently grows the margin, so the UI warning text and code behaviour differ slightly (cosmetic).

### Gaps
- Real printer behaviour (peel, warp, cure shrink) and clay release were not testable here.

## 2. Undercuts and demoulding: is release guaranteed?

### Takeaway
For ordinary strand/surface forms release along z is guaranteed by construction (heightmap = single-valued, 20 deg wall cap), including crossing strands and two-sided pieces. It is NOT guaranteed in three cases: draft slider at 0-5 deg (no warning), loop shift negative (sunk loop hole cuts a vertical wall into strands), and any user-set zero draft. There are no ejection aids or release-agent guidance.

### Cited Findings
- Module docstring claims "no undercuts by construction" — geometry.py:3-4. True because the cavity is Zb = T - H, a function of (x,y) (geometry.py:537), and `_profile` caps slope at (r-d)*tan(90-draft).
- Measured steepest neighbour-pixel step across all 15 builds (heightmap): 20.0 deg from vertical (= draft) for every curve design, auto loop; 0 pixel steps steeper than the draft line (steep_frac 0.0 in run1 outputs). Includes trefoil (earrings 2), Lissajous 3:2 (14), swirl (19), and fractals 1, 5, 9, 16, 17, 18, 19.
- Crossing strands (trefoil, Lissajous, figure eight, Lissajous clover): strand distance is the min over all polyline points via KD-tree (curve_heightmap geometry.py:269-271), so a crossing is a merged flat-topped junction, same height 1.2 mm, no over/under weave. No undercut, but also no woven look (design limitation, not a bug).
- Hanging loop auto placement keeps the hole tangent to the form so nothing is cut: draft min 20.0 deg and bodies=1 for 14/14 curve designs, tilt 0.0 (check output).
- BUG reproduced: `loop_shift_mm = -2` (sink the loop into the form) zeroes the hole disc regardless of what it overlaps (geometry.py:236-237). Result: steepest wall 2.4 deg from vertical, i.e. essentially 0 draft, for all 14 curve designs tested (trefoil, Lissajous, heart, hoop, ...). A 1.2 mm tall strand is cut by a vertical cylinder. No warning is raised.
- Draft slider accepts 0-45 (app.py:251). draft=0 builds clean with no warning (deep5: "draft 0 ... warn []"). Draft 45 builds, thickness drops (block 3.9 mm) because the dome cap lowers H.max for narrow strands.
- Two-sided: top half is the same cavity mirrored (geometry.py:569, 584), so each half drafts upward off its own side; the piece is parted at its midplane. Hole post meets post at the face (inferred). Misregistration 0.2 mm (measured radial pin clearance) gives a stepped parting line on the piece (inferred).
- No ejection feature: no push-out holes, no pry notches, no flexible wall; clay piece with 2.4-3.0 mm total thickness must be lifted out of a rigid resin cavity by hand. README and app contain no release-agent text (grep "release|talc|undercut" matches only the docstring). External guidance for printed press moulds: a light dusting of cornstarch, cling film, nylon or water; too much cornstarch stops fine detail bonding — [MakerWorld press-mould listings via search summary](https://makerworld.com/models/2510177); [Hackaday slab casting](https://hackaday.com/2023/12/20/slab-casting-a-new-way-to-combine-3d-printing-and-ceramics) (plastic moulds can't wick water like plaster); [polymer clay mould-release guide](https://thebluebottletree.com/?p=3048705).
- Printer layer steps: cavity walls at 70 deg from horizontal printed face up give 0.05 mm Z steps over about 0.018 mm run (computed: 0.05/tan70); mild mechanical key (inferred).

### Inferences
- Release risk is dominated by surface finish of the cavity (layer lines, uncured residue) and clay stickiness, not geometry, for default settings.
- A hard-coded minimum draft (say 5 deg) and a loop-shift guard would close the two geometric holes.

### Gaps
- No physical pressing/demoulding trial was possible (no printer/clay).
- Slice-orientation, support-need and cupping behaviour not simulated.

## 3. Printability for SLA/DLP (measured numbers)

### Takeaway
Meshes are watertight and single-body in 29/30 builds; mesh size is capped at 600k faces (30 MB binary STL per part, 20 MB form). Build costs 9-18 s and 2.1-2.9 GB at size 30/px 0.05, scaling steeply with size and pixel; px 0.02 (UI minimum) crashes with std::bad_alloc under a 13 GB limit. One surface design produced a 185 MB un-simplified lid. The resin-wall check is quantised and misreports gaps by up to +0.2 mm.

### Cited Findings
- Per-design table (size 30, px 0.05; A = two-sided+pins+margin 6.5, B = flat back default). Build s / peak RSS MB / mould faces / STL MB (mould, lid) / watertight (form, mould, lid) / min resin wall / enclosed gaps / warnings:
  - Lissajous 3:2: A 17.3 s 2789 MB 600000 30/30 TTT gap 0.70 8 gaps; B 9.6 s 2247 MB lid 0.0 MB(box)
  - Figure eight: A 16.3 s 2755 MB, gap 1.27; B 9.4 s
  - Heart: A 14.4 s 2614 MB, gap 1.82; B 8.8 s
  - Swirl: A 17.0 s 2873 MB, gap 0.55 -> WARN resin wall 0.55 < 0.6; B 9.8 s same warn
  - Hoop: A 18.0 s 2850 MB gap 1.82; B 9.2 s
  - Trefoil: A 16.3 s 2667 MB gap 1.82; B 9.9 s
  - Rose in rose in rose: A 15.7 s 2836 MB gap 1.47
  - Lissajous clover: A 16.4 s gap 0.70
  - Sierpinski triangle (implicit): A 15.5 s, gap 1.47, 13 gaps/13 pockets
  - Ring gasket: A 17.1 s, gap 0.55 WARN, 15 gaps/6 pockets
  - Two-scale lattice: A 17.7 s 2875 MB, gap 0.70, 21 gaps/13 pockets
  - Koch snowflake: A 16.5 s, gap 0.70
  - Fractal quilt (surface): A 30.8 s 3743 MB, gap 2.12; lid 185 MB (see below); B 9.4 s
  - Sierpinski order 3: A 18.5 s 2905 MB, gap 0.55 WARN, 31 gaps/8 pockets
  - Snow crystal: A 16.7 s, gap 0.93, 7 gaps/1 pocket
  Peak RSS includes the python process (about 2.0-2.9 GB regardless of design).
- Grid faces before simplification: 4.22M at 93 x 56 mm px 0.05 -> 600k (7x reduction) (run1 `grid_faces_mould`). Simplified volume vs exact grid solid differs by 0.0-0.2 mm3 out of about 22,000 mm3 (<0.001%). Top-surface vertices of the simplified mould/lid all lie within the 3x3 neighbourhood envelope of the grid heights (max excess 0.002 mm, deep4). Mean edge length 0.37-0.39 mm. So simplification does not visibly cost accuracy on tested designs (vertex-only test; interpolation between vertices not tested).
- Weak acceptance test: `_finish` accepts if volume within 1% of the volume (geometry.py:365). 1% of a 22,000 mm3 mould is 220 mm3, about 30% of a 700 mm3 cavity, so the test could pass a badly eroded cavity (inferred; actual error was 0.1 mm3).
- STL size: binary 84 + 50 bytes per face: form 20 MB (400k faces cap, FORM_FACES), mould 30 MB, lid 30 MB; zip contains all three plus json.
- FINDING: lid not simplified for the surface quilt in Full 3D: `_finish` ran fast_simplification on 3,702,250 faces, both targets (600k, 900k) came back non-watertight (volume correct), so it fell back to the original 3.70M faces: lid STL about 185 MB, 4.7 s extra (deep3). `check()` only tests form and mould watertightness (geometry.py:692-697), so no warning at all for the lid.
- Scaling at earrings 14, config A: size 40 px 0.05: 20.8 s, 3.7 GB, block 113 x 64 mm; size 60 px 0.05: 37.5 s, 6.0 GB, block 153 x 83 x 4.5 mm (resin 51 + 52 ml); size 30 px 0.03: 42.7 s, 6.6 GB, 11.4M grid faces; size 30 px 0.1: 6.7 s, 1.2 GB; size 30 px 0.02: MemoryError std::bad_alloc (13 GB cap). UI allows px down to 0.02 and size up to 200 (app.py:250,254). The app catches Exception for "Build failed" but a real OOM kill of the streamlit server cannot be caught (inferred). UI spinner text "draft about 5 s, final 10-25 s" matches measured 6.7 s and 15-21 s.
- Resolution: px 0.05 equals the common XY pixel of 4K mono LCD printers (about 0.05 mm; user-stated figure); features smaller than 1 px (0.05 mm) are not representable. Min strand edge feature check threshold 1.0 mm (MIN_FEATURE) and resin-wall 0.6 mm (MIN_GAP) (geometry.py:16).
- Measurement bug in `_thinnest`/`check` (deep1): at px 0.05 check subsamples to 0.1 mm (geometry.py:649-653) and reports in steps of about 0.2 mm. Synthetic gap sweep (true -> reported): 0.3 -> 0.5, 0.4 -> 0.5, 0.5 -> 0.7, 0.55 -> 0.7, 0.6 -> 0.7, 0.65 -> 0.93, 0.7 -> 0.93, 1.0 -> 1.14. So true gaps of 0.5-0.6 mm pass the < 0.6 warning (false negatives) and gaps of 0.3-0.4 are shown as 0.5.
- Design-dependent flip of the warning: same design reports different minima with size/px: Swirl size 30: px 0.1 -> 0.30, 0.05 -> 0.55, 0.03 -> 0.45; size 40: 0.55, 0.30, 0.45. Ring gasket size 30: 0.7 / 0.55 / 0.49; size 40: 0.3 / 0.3 / 0.27. The docs README numbers (earrings Swirl 0.30; fractals check at px 0.1) therefore do not match px 0.05 builds (Lissajous clover 0.70 in both; Sierpinski order 3 0.55 in both).
- Thin-wall relevance: resin walls here are posts between strands rising from the plate to the face (supported on one end), width measured at the cavity rim; with 20 deg draft they widen by about 0.87 mm toward the cavity floor at 1.2 mm depth (computed 2*1.2*tan20). A 0.55 mm rim ridge is fragile when pressed/shaved (inferred).
- Vents/gutter geometry: gutter-depth network (Lissajous A) is one 589 mm2 connected region touching the block edge, giving air an exit; total gutter+vent volume about 1070 mm3 capacity vs piece 705 mm3 (capacity, not fill).
- Printing orientation: not specified anywhere in README/app. Mould block (flat bottom, chamfered 0.5 mm) is evidently designed to print flat on the plate with the cavity face up (inferred from `_grid_solid` bottom chamfer, geometry.py:320-340); a 93 x 54 mm flat plate will have a large peel area (inferred: tilt/support advice absent).
- Two-sided with pins unchecked: builds without warning but top half has no registration (deep5 "2sided nopins ... warn []").

### Inferences
- Chamfer 0.5 mm bottom edge reduces elephant-foot; chamfer must be > 0 or mesh invalid (geometry.py:94).
- Memory model ~1.4 KB per grid cell; 100 mm at px 0.05 would need about 9 GB, 200 mm about 29 GB (extrapolated, not run).

### Gaps
- Real resin use includes supports, rafts and wash waste; not computed. Cost section uses mould+lid volume only (app.py:465).
- No slicer/printer tests; bed-size fit is printer specific.

## 4. Bugs, edge cases and design weaknesses (evidence list, 12 findings)

### Takeaway
Twelve concrete issues, most important: quantised thin-wall check (false negatives), un-simplified 185 MB lid with no lid check, sunk-loop vertical wall, no shrinkage compensation, polymer-clay density used for ceramic clay.

### Cited Findings
1. Resin-wall check quantised, +0.1-0.2 mm optimistic; gaps of 0.5-0.6 mm pass (geometry.py:649-653, 632). Evidence deep1 table above.
2. Warning flips with size/px for the same design (Swirl 0.30/0.55/0.45) — check is resolution dependent.
3. Lid simplification failure falls back silently to 3.7M faces, 185 MB STL (geometry.py:356-367); check() skips lid watertight (geometry.py:692-697).
4. Sunk loop (`loop_shift_mm < 0`) cuts a 0-draft wall: 2.4 deg from vertical measured on 14/14 designs (geometry.py:236-237); no check on draft after loop.
5. Draft 0-5 deg allowed, no warning (app.py:251; deep5 draft 0 clean).
6. Loop angle mode: auto-by-angle 0 deg (right) reports `hangs tilted -90 deg` warning only; no clash check with form (expected, informational).
7. Vents never cross strands: they are limited to `out & dist > land` (geometry.py:461-468), so vents-through-thin-strands cannot occur (tested negative). However vents do not reach enclosed gaps, and many enclosed gaps have no pocket (Sierpinski 3: 31 gaps, 8 pockets).
8. Shared pair channel: any +x vent adds a 1.2 x 0.8 mm channel spanning the whole block height at the gap centre, linking both cavities' gutters and both edges (geometry.py:547-549). Overflow clay from L can flow to R (inferred); it also bisects the block face.
9. `lid_t` is ignored in Full 3D mode (lid = T + pin_h); UI shows the slider regardless (app.py:271).
10. Pins only on 3 corners; no registration if pins off in two-sided mode and no warning (deep5).
11. Wall slider min 1.0: wall 1.0 mm gives 2.5 mm block with no warning unless pins (socket floor 0.2 < 1.0 mm warning only with pins) (deep5).
12. Memory: px 0.02 → MemoryError; 0.03 at size 30 uses 6.6 GB, 43 s; no guard on px*size product (app.py:250,254).
13. Clay density 1.7 g/cm3 labelled "polymer clay" (clay.py:6) and used for every clay; app caption says weigh a ball (app.py:463). Cost section: resin ml excludes supports/waste.
14. Clay balls: two-sided Lissajous needs 5 balls of 6.8 mm for 811 mm3; surface quilt two-sided hits the 12-ball cap: 12 x 7.7 mm balls + warning; ball-zone error up to 11% on Lissajous two-sided (clay.py run, size 30 px 0.1). Hoop flat 3 x 4.9 mm balls, 0.31 g.

### Inferences
- Items 1-3 and 4 are the highest-risk correctness issues for a user relying on the Check report.

### Gaps
- Behaviour of auto-loop on very asymmetric forms (e.g. loop landing in a deep notch) tested only on the 14 designs above.

## 5. Missing features (shrinkage, release, registration, plates, ergonomics)

### Takeaway
No shrinkage scaling exists anywhere; no release-agent text; one block per mould pair; no tool for hand pressing. Earthenware total shrinkage is roughly 5-10% depending on source, so a 30 mm design would fire to about 27-28.5 mm and the 1.8 mm hole to about 1.6-1.7 mm.

### Cited Findings
- grep for "shrink" in *.py and README.md: no matches (only the word in docs/fractals/README.md in an unrelated sentence "Do not shrink them below 30 mm"). No scale-for-shrinkage option in FormOptions (geometry.py:24-38) or the UI.
- Shrinkage figures: Digitalfire says earthenware fires down about 3-4% or less dry-to-fired (not total) — [Digitalfire](https://digitalfire.com/glossary/firing%20shrinkage); Valentine Clays gives earthenware 5-10% — [Valentine Clays](https://valentineclays.co.uk/pages/shrinkage-rates); Lakeside Pottery test: about 5% drying plus 5.5% glaze fire, about 11% total, and 8-12% typical total — [Lakeside Pottery](https://lakesidepottery.com/HTML%20Text/Tips/Clay%20drying%20and%20firing%20process.htm). Digitalfire warns that dry and fired percentages cannot be added directly (6.25 + 6.66 gives 12.5% total, not 12.9) — [Digitalfire](https://digitalfire.com/glossary/firing%20shrinkage). Sources use different baselines; check your clay body data sheet.
- Compensation factor = 1/(1-s): 5% -> x1.053, 8% -> x1.087, 10% -> x1.111 (arithmetic). Effects at size 30 mm: 10% means the pressed form must be 33.3 mm; the mould block grows about 5-8 mm in X (inferred from 93.4 mm at 30 mm, 113 mm at 40 mm).
- Registration: pins on three corners only (above). No keys at mid-length; with 0.2 mm measured radial clearance the lateral registration error up to 0.2 mm (inferred).
- Multi-cavity plates: the only multi-cavity is pair L + mirror R (geometry.py:530-536); no n-up, no mixed designs, no "bigger base" option other than `margin`.
- Base plate option (base_mm) only changes the positive form STL, not the mould (geometry.py:375-377).
- Hand-press ergonomics: no handles, no pressing-plate/lid rim, blade-shaving flat face yes; no spacer/stop to set clay thickness; no ejector.

### Inferences
- Without compensation, hanging hole shrinks from 1.8 mm to about 1.6 mm at 10%, tight for 0.7-0.8 mm wire (inferred); loop wall thickness and strand width shrink the same.

### Gaps
- Specific shrinkage of the user's clay body not given; polymer clay does not shrink (inferred, not sourced).

## 6. Prioritised recommendations (impact vs effort)

### Takeaway
Fix the trust issues in Check first (cheap), add shrinkage scale and release guidance (high impact, low effort), then guardrails and a stronger lid check.

### Cited Findings (ordered)
1. Add `shrink_pct` option scaling size_mm by 1/(1-s) and show fired size in Check: high impact, about 10 lines (FormOptions + build_all).
2. Replace `_thinnest` quantisation: compute at full px (or EDT radius directly, local thickness map) and warn on 2*r < 0.6 + one pixel; effort low-medium. Emit location of the thinnest wall.
3. Add lid watertight + face-count checks in `check()` and a warning when simplification fell back (>1M faces); effort low.
4. Guardrail draft: warn below 3-5 deg; post-loop draft test (steepest step > tan(90-draft)); block negative loop shift or smooth the hole cut; effort low.
5. Add release-agent / pressing guidance (cornstarch, thin film, shave with blade, slow lift) to README + Check; effort trivial.
6. Memory/time guard: refuse px*size combos above about 6M cells or warn; effort low.
7. Enclosed-gap pockets: lower pocket_min or add vent holes for thin gaps; effort medium.
8. Make `lid_t` hidden in Full 3D; unify pin warning text with actual behaviour; effort trivial.
9. Clay: clay-body density selector (earthenware vs polymer) and shrink-corrected cavity; effort low.
10. Longer term: more pins/keys, multi-cavity n-up plate, push-out notch, printing-orientation note (tilt 30-45 deg) and thicker default plate option (6 mm); effort medium-high.

### Inferences
- Items 1-4 make the Check report trustworthy; the remainder are polish.

### Gaps
- Effort estimates are inferred from reading code, not implemented.
