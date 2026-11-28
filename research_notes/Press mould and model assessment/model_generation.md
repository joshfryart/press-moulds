# Model generation in equation-playground (equation -> curve/surface -> 3D form mesh)

Conventions: "[geometry.py:144]" etc. are links to local files under file:///home/user/press-moulds/equation-playground/. All numbers marked MEASURED were produced by running the code (python -I, scratch scripts in /tmp/claude-0/-home-user-press-moulds/6460356d-7c49-5685-80ea-e29db7f086ce/scratchpad/t1..t9.py; machine: 4 cores, 16 GB, no GPU; numpy 2.5.3, scipy 1.18.1, sympy 1.14, trimesh 5.2.2). Items marked INFERRED were not run. No repo files were modified. Existing suite: 127 tests pass in 23 s (MEASURED).

## 1. How does the pipeline work end to end (equation -> samples -> heightmap -> mesh), incl. strand profile, draft, base, two-sided, loop, rotate/mirror, size fitting?

### Takeaway
The "model" is a 2.5D heightmap, not a swept solid: sampled centreline polylines are rasterised into a per-pixel height grid H (domed ridge capped by a draft cone), and the positive form STL is that grid triangulated top and bottom, then quadric-decimated to <=400k faces. Everything (loop, hole, base, mould, clay volume, checks) hangs off the same grid, which makes it robust and watertight-by-construction but ties fidelity, memory and time to the pixel size.

### Cited Findings
- Parse: sympy `parse_expr` with a whitelist of functions/constants; kind is auto-detected from the text (explicit `y=f(x)`, implicit, parametric `x=..,y=..` with param `t`, polar `r=f(theta)`, surface `z=f(x,y)`); any non-axis symbol becomes a slider defaulting to 1.0 — [core.py:269-324](file:///home/user/press-moulds/equation-playground/core.py), [README.md:23-28](file:///home/user/press-moulds/equation-playground/README.md). Lambdified to numpy with real cube-root handling [core.py:327-349].
- Sampling [core.py:449-510]: explicit/parametric/polar are sampled uniformly in the parameter (n default 800, UI max 5000, no adaptivity); poles/steps are split into separate polylines by `_split_jumps_1d/2d` [core.py:381-409]; implicit = contourpy marching squares on a grid capped at 400x400 (`min(n,400)`, [core.py:495]) with pole-crossing filtering [core.py:531-547]; surface = grid capped at 150x150 (`min(n,150)`, [core.py:498]). Closed/open flag per polyline from endpoint distance [core.py:427-431].
- Size fitting: `fit_polylines` scales ALL polylines uniformly so the largest bbox side of the CENTRELINE = size_mm and centres at the origin [geometry.py:107-117]. The finished piece is therefore larger than "size" by about one strand width: MEASURED circle size 40 -> form 41.7 x (41.7 + loop) mm; diamond bbox 41.75 mm vs 40+1.8.
- Rotate / mirror are applied in app.py `placed()` to the polylines BEFORE fit_polylines [app.py:290-297]; surfaces ignore them (help text says "2D kinds").
- Heightmap from curves [geometry.py:246-281]: polylines are resampled at px/2 spacing, only pixels within r+2px of a centreline are evaluated (EDT dilation + cKDTree nearest-distance), and `_profile` gives z.
- Strand cross-section [geometry.py:144-148]: with d = distance to centreline, r = strand_w/2, h = strand_h, tanw = tan(90 deg - draft): `z = min(h*sqrt(1-(d/r)^2), (r-d)*tanw)`, 0 outside. I.e. a half-ellipse (r x h) intersected with a cone whose wall is `draft` degrees off vertical (default 20 deg -> wall slope 70 deg, tan = 2.75). Round caps/joins at ends and corners come for free (distance field). No undercut by construction.
- Draft: only enters through the cone cap; for surfaces it drafts the footprint edge via EDT: `H = min(H, e*tanw)` [geometry.py:311-313].
- Hanging loop [geometry.py:190-243]: ring heightmap (od 5, id 1.8, h 1.5 by default) is union'd (`np.maximum`) onto H; auto mode puts it above the form on the line through the centre of mass x, with the hole circle tangent to the highest form pixel within the hole's lateral band (`_hole_tangent`); iterates up to 4x so the loop x converges to the COM x of the form+ring [geometry.py:238-242]; non-auto uses an angle from COM; `loop_shift_mm>0` adds a bridge strand [geometry.py:228-235]; the hole is then forced open (z=0) [geometry.py:236-237]. Hang tilt is reported by `check` [geometry.py:658-660,689].
- Loop applies only to 2D curve kinds; `surface_heightmap` has no loop code (see section 3).
- Surface -> heightmap [geometry.py:284-315]: finite-Z footprint, z normalised to [min(0.6,relief), relief] (default relief 3 mm), bilinear resample onto the px grid, footprint edge drafted.
- Mesh [geometry.py:370-407]: pad 1 px; top = H, bottom = same grid at z=0 with zero-height vertices shared (edge where the drafted wall meets the back plane); pinched zero edges are "lifted" 1e-3 mm to avoid non-manifold edges [geometry.py:386-404]; `two_sided` mirrors the bottom to z=-H (solid symmetric piece, base_mm ignored) [geometry.py:405]; `base_mm>0` instead builds a `_grid_solid` slab of the whole crop rectangle (H + base) with a 0.3 mm max chamfer [geometry.py:375-377].
- `_finish` [geometry.py:349-367]: fast_simplification down to FORM_FACES=400,000 (fallback 1.5x, then none), drops duplicate faces, fixes orientation, and accepts the result only if watertight and volume within 1% of the pre-simplification volume.
- 3D preview in the app [app.py:300-329]: a coarse build with `lpx = max(px, 0.2, size/220)`, same pipeline, `mesh_figure` (Plotly Mesh3d, decimated to 150k faces, smooth shading [app.py:157-171]). Re-run on every slider/equation change (key includes all params, [app.py:306]). "Build" uses the user px (default 0.05); "Draft build" uses max(px,0.1) [app.py:360-365].

### Inferences
- Because the preview uses the same code path with a bigger pixel, preview-vs-print differences are purely resolution, not logic (INFERRED from app.py:306-319 and geometry.py; supported by the stair-step measurements in section 3).
- The anim.py module only drives the 2D plot morph/sweep and has no role in model generation (INFERRED from reading anim.py and app.py:330-355).

### Gaps
- Mould/lid generation is out of scope here (covered by other researchers); only referenced where it shares the heightmap.

## 2. Strengths: what is solid and tested?

### Takeaway
The parser safety, watertightness of straight/degenerate curves, loop placement and the thin-feature/gap detection are deliberately engineered and covered by regression tests; all 20 equations in a varied spread built watertight, one body (except genuinely disjoint ones), in 0.1-2.8 s at 0.1 mm pixel (MEASURED).

### Cited Findings
- Z-fidelity of the strand surface is excellent. MEASURED (t2b.py: ray-cast mesh vs analytic profile at 2000 random points around a diagonal line / circle r=20): max |dz| = 0.15 mm at px 0.2, 0.08 at 0.1, 0.037 at 0.05, 0.022 at 0.03; mean <= 0.016 mm even at 0.2. Footprint width: 1.76 mm at px 0.9, 1.79 at 0.5, 1.802 at 0.2, 1.800 at 0.05 (nominal 1.8). Volume after decimation equals heightmap volume (90.5 mm3 at px 0.1/0.05/0.03/0.02, t3.py), i.e. the 400k cap does not change volume.
- Watertight everywhere tried: 20/20 equations (circle, sine, rose, cos(3theta) rose through the origin, Lissajous, spiral, tan, 1/x, folium, cusp y^2=x^3, cardioid, astroid, diamond, cell/grid implicit patterns, sin(30x), zero-amplitude, line, trefoil-like) gave `is_watertight=True` at px 0.1 (MEASURED t5.py). Sharp corners and cusps are handled gracefully because the strand is a distance field: round joins/caps, no self-intersection problems; crossings simply union.
- Pinched-edge repair loop for lines/zero-height degenerate cases is tested: `test_straight_lines_form_watertight` (y=x, y=1, x=1, y=.5x, zero-amplitude polar; px 0.1/0.05; loop on/off) — [tests/test_geometry_fixes.py:23-36](file:///home/user/press-moulds/equation-playground/tests/test_geometry_fixes.py); `test_build_all_circle_is_watertight_with_positive_volume` and `test_stl_bytes_longer_than_header` — [tests/test_geometry.py:36-52].
- Loop: `test_auto_loop_is_at_top` (y=x^2, y=|x|) [tests/test_geometry_fixes.py:39-46]; MEASURED hang tilt on varied shapes with auto loop: rose -0.1 deg, y=x^3 -1.8, sin(x) 1.3, circle 0.0 — all < 5 deg warn threshold, bodies=1, watertight. Manual angle / shift / small-loop options built without error (t8.py), and `check` warns about tilt, thin ring wall (<0.8) and small hole (<1.2) [geometry.py:683-690] (MEASURED: loop_od 2/id 0.8 produced all three warnings).
- Multiple-piece detection: `test_two_disjoint_circles_warn_separate` [tests/test_geometry.py:55-59]; MEASURED sin(x)sin(y)=0.1 -> 8 bodies and warning "form is 8 separate pieces".
- Thin feature / thin gap detector `_thinnest` [geometry.py:605-632] is tested on synthetic strips and gaps at two pixel sizes (`test_check_warns_thin_strip`, `test_check_warns_thin_gap`, [tests/test_geometry_fixes.py:~55-75]); MEASURED gap values are sensible (rose 1.47 mm, Lissajous 0.93, astroid 1.01, 6-turn Archimedes 0.70 mm).
- Input validation: `FormOptions`/`MouldOptions`/NaN heightmap raise ValueError (`test_bad_form_options_raise_valueerror`, `test_bad_mould_options_raise_valueerror`, `test_nan_in_heightmap_raises`) — [geometry.py:75-102].
- Parse-time safety is strong and tested (`test_huge_numbers_rejected_fast`, `test_odd_unicode_errors`, `test_fullwidth_and_math_italic_normalised`, `test_call_rejection_message`, test_core_fixes.py): 500-char cap, banned names/attribute access/`__`/`import`/`lambda`, `_guard_size` on constant powers [core.py:101-183], restricted `__builtins__`. MEASURED: `9^9^9 + x` rejected in 0.00 s, a 60-term sum > 500 chars rejected, `x^x^x^x=y`, `(x+y+1)^40=1`, `(x+1)^900000=y`, 8-deep nested sin all parse+sample in <= 0.02 s. `sample(n=5e6)` explicit takes 0.9 s (no cap in core; UI caps at 5000 [app.py:181]).
- Pole/step handling: `test_tan_has_multiple_polylines`, `test_floor_steps_not_joined`; MEASURED tan -> 7 polylines, 1/x -> 2.
- Implicit accuracy: circle r=5 radial deviation 6e-5 (801 points, MEASURED).
- Good speed at the preview setting: full preview build (heightmap + mesh) 0.03-0.12 s at 20-200 mm (MEASURED t7.py); a 40 mm design at 0.1 px builds the form in ~0.4 s, at 0.05 px in ~2.1 s (t1.py).
- Surface kind can already yield a cabochon/dome: `z = sqrt(16-x^2-y^2)` gives a circular footprint (NaN outside), H max 3.0 mm, boundary radius 20.00 mm mean (min 19.83, max 20.15) (MEASURED t6.py D).

### Inferences
- The 127-test suite is mostly functional/regression oriented; the strongest coverage is core parsing and watertightness. (INFERRED from test names; see Gaps for what is untested.)

### Gaps
- Test coverage holes, verified by grep over tests/: no test calls `surface_heightmap`, `two_sided=True` in `form_mesh`, `base_mm`, `loop_angle_deg`, `loop_shift_mm`, draft behaviour or `_profile`; rotate/mirror (`placed`) and the 3D preview path live in app.py and are untested. Only `tests/test_clay_app_fixes.py` touches app-level logic.

## 3. Weaknesses, risks and limits (each item reproduced by running code)

### Takeaway
No correctness failures in the mesh itself, but there are eleven reproducible limits: the live preview is visibly stair-stepped and becomes meaningless for large sizes; memory/time explode with size x 1/px (OOM at UI-allowed extremes); strand height is silently not honoured with high draft or narrow strands; the surface kind ignores amplitude, has no loop, and is capped at a 150 grid; base plate is a rectangular slab and its clay is not counted; rotation changes scale; unbounded curves are squashed; many-piece implicit curves give no loop and weak warnings.

### Cited Findings (numbered problems; MEASURED unless stated)
1. **Preview stair-stepping.** Preview pixel is `max(px, 0.2, size/220)` [app.py:305]. Wall slope is 70 deg (tan 2.75), so one pixel step = height step: max adjacent-pixel height step 0.55 mm at px 0.2, 1.19 mm at px 0.91, vs 0.14 mm at the 0.05 build px (t9.py). Hillshade render of a ring wall (scratchpad/stair.png) shows distinct blocky steps at 0.2 mm px and a two-column slab at 200 mm size. A 1.8 mm strand is 9 px wide at 40 mm size, 5 px at 80 mm, 2.6 px at 150 mm, 2.0 px at 200 mm (t7.py I) - above ~100 mm the preview no longer resembles a strand (heights are fine, footprint/profile are not). Surface smoothness in the mesh itself is not the cause (z error <0.15 mm); it is the pixel grid under linear triangulation of steep walls. The preview mesh is also smooth-shaded by Plotly with `flatshading=False` which hides some but not the steps.
2. **Time/memory scale as (size/px)^2 and are not guarded.** Form mesh only (t1.py, eq r=1+0.5cos5theta, loop on): 40 mm @0.2: 215x206 px, 0.1 s, 150 MB; 40 mm @0.1: 0.4 s; 40 mm @0.05 (default): 855x821 px, 2.1 s, 723 MB; 40 mm @0.03: 2.0 M px, 5.0 s, 1.5 GB; 40 mm @0.02: 4.4 M px, 10.9 s, 3.2 GB; 80 mm @0.05: 3.3 s; 120 mm @0.05: 5.8 M px, 5.8 s; 200 mm @0.05: 15.8 M px, 12.9 s, 6.9 GB RSS; 200 mm @0.02 (both inside the UI limits, size<=200 [app.py:247], px>=0.02 [app.py:251]) was killed by the OOM killer on a 16 GB box (ru_maxrss already 6.9 GB at the previous step; the grid alone would be ~100 M px x 8 B = 0.8 GB per float array, INFERRED: several such arrays). Full `build_all` with pins and two-sided at 40 mm: 7.3 s / 1.5 GB at px 0.1, 19.5 s / 3.9 GB at px 0.05 (t8.py P); this exceeds the spinner text "draft about 5 s, final 10-25 s" [app.py:361] only when size grows. Streamlit runs this in the server process, so a big build can take the app down (INFERRED).
3. **Face cap changes mesh density but not volume; at default settings it is already binding.** FORM_FACES=400,000 [geometry.py:17]; a 40 mm rose already has 400k faces at px 0.05 (STL ~20 MB) and 399,900 at 0.03 and 0.02: finer pixel buys no extra mesh detail, only more compute (t1.py). Several tested designs also hit it at 0.1 px (grid 400,000, sin(xy)=0.5 400,000; cell pattern 364k).
4. **strand_h is not honoured with high draft or narrow strands.** Max height achieved with strand_h=1.2 (t6.py A): w=0.4 mm: 1.20 (draft 0), 1.13 (10), 0.55 (20 = default), 0.35 (30), 0.20 (45); w=0.8: 1.10 at 20; w=1.2: 1.04 at 30, 0.60 at 45; w=1.8: 0.90 at 45. Cause: cone cap `(r-d)*tanw` at centre = r*tanw < h [geometry.py:147]. The UI allows strand width 0.4 and draft up to 45 [app.py:248-250] and gives no warning; `check` reports max_thick correctly but does not compare with the requested height.
5. **Surface amplitude slider is a no-op.** `z = a*sin(x)*cos(y)` with a=1 and a=3 yields identical heightmaps; a=-1 inverts; only the sign matters because Z is min-max normalised to `relief_mm` [geometry.py:307-310] (MEASURED t6.py B). Same for offsets. Physical relief is only controlled by the "Relief (mm)" field.
6. **Surface kind: no hanging loop, silent.** `surface_heightmap` has no loop code, `H.info` is empty with `loop=True` (MEASURED); the "Hanging loop" checkbox in app.py:254 stays ticked and nothing warns; `check` has no tilt and no hint. Also rotate/mirror ignored for surfaces, and the footprint is whatever finite region the equation has (square by default), with a >= 0.6 mm slab minimum thickness [geometry.py:309].
7. **Surface resolution capped at 150x150 regardless of Samples n or px.** `n=150/800/5000` all give a (150,150) grid (MEASURED); `z = sin(20x)cos(20y)` on the default 10x10 domain is under-resolved: RMS relief error 0.21 mm, max 0.53 mm on a 0.6-3 mm relief (t6.py C). Footprint boundaries of NaN regions are decided at the 150-grid cell (staircase +-0.17 mm measured on the 20 mm-radius dome at 40 mm size).
8. **Base plate is a full rectangle, not a contour plate, and its clay is not counted.** `base_mm=1.0` on a 40 mm rose: bbox 41.1 x 42.8 x 2.2 mm, volume 269 -> 2021 mm3 (7.5x), faces 130k -> 360k; `check()['clay_cm3']` stays 0.269 because it sums H only [geometry.py:668]; `clay.clay_balls(b["H"], ...)` likewise uses H only [app.py:416, clay.py:32]. With two_sided the base setting is silently ignored (z extent stays 3.0 mm) (MEASURED t6.py F/G). INFERRED consequence: the clay-ball and cost numbers are wrong whenever base>0.
9. **Rotation rescales the piece.** Rotate is applied before size fitting, so "size" refers to the rotated bounding box: a 3:1 ellipse has centreline length 89.1 mm at 0 and 90 deg but 119.5 mm at 45 deg (+34%), the box becoming 40x40 (t6.py H). Stroke/loop/ clay volume therefore change with rotation unintentionally. No test covers it.
10. **Unbounded curves defeat fit-to-size.** Default domain -10..10: `y=tan(x)` fits to 7.3 x 40 mm (y range +-54), `y=exp(x)` to 0.04 x 40 mm (a vertical hairline: the 0.04 mm wide curve is entirely below strand width), `y=x^3` to 0.4 x 40 mm, `y=1/x` to 15 x 40 mm (t7.py J). No automatic y-clipping/window; user must edit ranges by hand. For `y=exp(x)` the form is a spike, not warned.
11. **Uniform parametric sampling misses fast detail; implicit grid misses small features.** Explicit/parametric/polar use uniform n=800; `sin(1/x)` on -1..1: 336 points in the longest piece, minimum |x| sampled 0.16 (t7.py K). Implicit circle with r=0.02 on the -10..10 domain -> "nothing to draw in this range" because the 400 grid has 0.05 spacing (r=0.05 and 0.2 draw, polygonal) (t7.py L). `n=5000` does not raise implicit resolution above 400 (801 vertex circle). Open curves clipped by the domain end with round caps, not flagged.
12. **Many-piece / dense implicit curves.** `sin(x)*sin(y)=0.1` -> 32 polylines (18 closed), 8 bodies, resin-wall 0.30 mm warning; `sin(x*y)=0.5` -> 126 open polylines; strands merge where curve spacing < strand width (hyperbolas converge to the domain corners), so the form becomes blobs but `bodies` reports 1 and no warning explains it; the gap detector floors at 0.3 mm at 0.1 px so "0.3" means "<= 0.3" (t5.py). Auto loop attaches to one body only; two disjoint circles -> bodies 2, loop on one, hang tilt 65.6 deg warning (t8.py). A loop is placed even if the form is many disconnected strands (no sanity warning beyond bodies).
13. **Grammar limits.** README Limits: no inequalities, no ODEs/derivatives, `f(x)` = `f*x`; max 500 chars and max two parts; no sums/products/loops/user functions/piecewise except via floor/Heaviside/min/max/abs; one equation of one kind only (no union of several curves, e.g. a circle plus a line, except as a parametric trick) — [core.py:26-71,269-324, README.md:76-80]. A 60-term Fourier sum is rejected by the length cap (MEASURED). Only a single strand width/height; strands are always outlines, never filled areas (inequalities unsupported => no filled discs/cabochons except through the surface kind).
14. **Heightmap model limits (structural).** No overhangs/undercuts, no through-holes other than the loop hole (the loop hole is forced to 0 and given a solid post in the mould [geometry.py:417-428]); all details are quantised to px; two strands crossing produce a flat union (max of two domes) rather than an over/under weave. Sharp concave corners fill with the distance-field cone (a fillet radius of about r) - this is by design but means you cannot get a crisp inside V (INFERRED from the distance-field definition; the diamond corner outer radius is the strand radius, bbox 41.75 mm MEASURED).
15. **Coverage gaps (see section 2)**: surface path, two_sided/base mesh, loop angle/shift, rotate/mirror, draft limits and the preview are untested.
16. **Plotly preview (browser) cost**: preview mesh is simplified to 150k faces [app.py:157-164] but the Build views (form 400k faces) are sent as 150k-face Mesh3d in the browser; every Streamlit rerun re-sends the figure (INFERRED).

### Inferences
- Items 1 and 2 interact: a designer scaling up to 100-200 mm (e.g. statement earrings) sees a worse preview and a heavier build simultaneously; there is no smart default px derived from size.
- Items 4, 5, 8, 9 are silent-wrong-answer problems (UI accepts the input, output does not match intent, no warning). These are the highest trust risks.
- The `bodies` count is the only topology feedback; dense curve families merge without notice.

### Gaps
- Did not measure browser render time (no browser/GPU in this environment); the "visible stair-step" claim rests on hillshade images of the heightmap, the measured step heights, and the preview pixel formula, not on a screenshot of the Plotly 3D view.
- Did not run the full Streamlit UI end to end; all measurements call geometry.py/core.py directly with the same parameters the UI passes.
- OOM point for 200 mm/0.02 px was observed as a process kill, not a profiled peak.

## 4. Important capabilities missing for a jewellery designer

### Takeaway
The pipeline gives a correct, printable, drafted 2.5D relief piece with one loop, but lacks the vocabulary a jewellery designer needs: smooth/analytic export, variable line weight, shrinkage and unit handling, alternative findings (jump ring / bezel / post / stud / bail), filled shapes, and fidelity controls tied to physical size.

### Cited Findings
- Export formats: SVG (2D kinds only), binary STL for form/mould/lid, one zip with `design.json` [app.py:477-501]; no 3MF/OBJ/STEP/DXF/PNG, no per-part units metadata, millimetres only; MEASURED STL size 20 MB at 400k faces (50 B/face + 84 header). Nothing in the repo mentions shrinkage, scaling or units (grep for shrink|3mf|obj|step|units over *.py/*.md returned nothing relevant).
- Strand style is a single constant width and a single height for the whole piece, round dome only [geometry.py:23-30,144-148]; no per-point/tapered width, no flat-top or square/ribbon profile, no embossed text, no filled regions or outline+fill combos, no domed (pillow) pendant body unless via the surface kind.
- Findings are limited to one ring loop with od/id/height/angle/shift [geometry.py:36-39]; no earring post/stud flat-pad, ear-wire hole through the side, double loop (chandelier), bail, bezel/setting or cabochon frame, no loop for surface kind.
- Two-sided option exists (solid symmetric piece, pins) [geometry.py:370-407, app.py:275-279] but base plate/two-sided are mutually exclusive without notice (section 3 item 8).
- Clay: exact cavity volume and ball placement exist (clay.py) but ignore base plate/loop-hole inconsistencies and ignore clay shrinkage (polymer clay is ~0-1%, ceramic clay 8-15% - general knowledge, not from the repo; no source consulted).
- Fidelity controls: no explicit 'smooth mesh' / subdivision / fillet radius option; "curve smoothness" is controlled by Samples n and pixel size only; implicit and surface grids hard-capped (400 / 150).
- Design reproducibility: design.json saves equation, params, domain, rotate, mirror, form and mould options [app.py:371-373]; but not an import path (no "load design.json" in app.py - INFERRED from grepping app.py for 'design' usage: only written).

### Inferences
- The biggest jewellery-specific gaps are (a) a post/stud/hole findings set, (b) shrinkage scaling ("make the master X% bigger" for ceramics), (c) variable strand width, (d) smooth/hi-res export. Which ones matter depends on clay type; no user research was available.

### Gaps
- No external sources were searched (assignment was a codebase assessment); shrink percentages above are general knowledge and unverified here.

## 5. Prioritised recommendations (impact vs effort)

### Takeaway
Fix the silent-wrong-answer items first (cheap, high trust), then add size-aware pixel/memory guards and a better preview, then add findings/shrinkage/variable width.

### Cited Findings
Recommendations (all INFERRED from the measurements above; effort in rough dev-days):
1. (S, high) Warn or auto-fix when requested strand_h cannot be reached: compute `r*tanw` vs h and show "max height X mm with this draft/width" in the form column or in `check` [geometry.py:147, app.py:248-250]. Also surface amplitude: either honour `z` scale (cap to relief) or say "amplitude is normalised; use Relief".
2. (S, high) Make the clay/cost numbers include the base plate (and mirror) and document that two-sided ignores base; or disable the base control when two-sided is chosen [app.py:264-278, clay.py:32].
3. (S, high) Guard memory/time: estimate pixels = (size/px)^2 before build; refuse or auto-raise px above ~5-8 M px (MEASURED: 5.8 M px ~ 5.8 s mesh, 15.8 M px = 6.9 GB); cap the UI slider combination (200 mm x 0.02 px OOM). Cheap: compute `H.size` before allocating in `curve_heightmap`.
4. (S-M, high) Preview pixel: make it adaptive to strand width (e.g. `lpx <= strand_w/6`) so strands stay >= 6 px wide, and/or show an explicit "preview too coarse" badge when strand < 5 px; consider flat-shaded smoothing via normals computed from the analytic profile (the height is within 0.15 mm; the artefact is only the step slope).
5. (S, medium) Rotation: fit size before rotating (rotate the already fitted polylines) so size/clay don't depend on rotation [app.py:290-297, geometry.py:107-117].
6. (S, medium) Warn on unbounded/degenerate fits: if fitted bbox aspect > ~20:1 or one side < strand width, suggest ranges (exp, tan, x^3).
7. (M, medium) Surface: remove or warn the loop on surfaces, add loop for surfaces (reuse `_add_loop` on the footprint), raise the 150 grid cap or sample at px resolution, and use an analytic evaluation on the pixel grid directly (map x,y -> z) instead of bilinear from a fixed grid.
8. (M, medium) Make implicit sampling adaptive/refined (finer grid near sign changes or user-controlled grid up to ~1500 with contourpy), and add a "minimum curve size" warning when an implicit curve vanishes; add merge/overlap warning to `check` (e.g. strand coverage area > some fraction of bbox or pairs of centrelines closer than strand_w).
9. (M, medium) Mesh quality: raise FORM_FACES as an option (STL ~20 MB at 400k), or export without decimation for the form; optional Laplacian/normal smoothing of the preview mesh.
10. (M, medium) Jewellery features: variable strand width (parameter expression `w(t)`), shrinkage compensation (a single scale % applied before export and recorded in design.json), second hole/post pad, filled-shape option for closed curves (inequality-like fill).
11. (S, medium) Tests: add tests for surface_heightmap (amplitude, footprint, dome), `form_mesh(two_sided/base)`, draft vs strand_h cap, loop angle/shift, `placed()` rotate/mirror, and a perf/memory smoke test at 40 mm @0.05.
12. (L, low-medium) Export 3MF/OBJ with units, and add "import design.json" to reload.

### Inferences
- Suggested order: 1, 2, 3, 5, 6 (a day or two total, remove silent errors) -> 4, 7, 11 -> 8-10, 12.

### Gaps
- Effort estimates are judgement, not measured. No user testing of what designers need.
