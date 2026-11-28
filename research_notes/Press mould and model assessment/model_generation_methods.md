# Equation-to-3D-printable-jewellery: tools, techniques, and upgrades over a pixel heightmap

Scope note: ~12 searches (snippet-level, few full-page fetches). Items marked [UNVERIFIED] come from general knowledge, not a source I retrieved.

## 1. What tools and workflows exist

### Takeaway
Existing equation-to-jewellery workflows mostly (a) export a 2D graph to SVG then extrude (Desmos -> Tinkercad), or (b) build parametric surfaces/tubes in a CAS or CAD (Wolfram, Blender, Fusion, build123d). I found no source for a dedicated web "equation to STL jewellery" tool or an Etsy-specific workflow; treat that as a gap.

### Cited Findings
- Desmos is 2D; the common community route is screenshot/export -> SVG -> import to Tinkercad -> scale (~2 mm height) -> STL. 3D equations are typically done in Wolfram/other CAS and exported to STL. — [search results incl. Callysto lesson](https://www.callysto.ca/wp-content/uploads/2024/03/3D-Printing-Lesson-Plan-1.pdf), [Wolfram jewellery blog](https://blog.wolfram.com/2021/02/15/3d-printed-jewelry-made-with-the-wolfram-language-showcases-the-beauty-of-mathematics)
- Wolfram blog: a heart pendant exported to STL from ~3 lines of Wolfram Language; Shapeways sells equation-derived pendants ("Mathematical Menagerie"). — [Wolfram blog](https://blog.wolfram.com/2021/02/15/3d-printed-jewelry-made-with-the-wolfram-language-showcases-the-beauty-of-mathematics), [Shapeways pendant](https://www.shapeways.com/product/LAMPEAK6Y/hyperbole-01-pendant)
- Polar-curve pendants exist as shared models (e.g. r = -8 sin(4θ)). — [STLFinder polar flower pendant](https://www.stlfinder.com/model/polar-coordinate-flower-pendant-hrvbcA49/3472334)
- Blender: Curve to Mesh node sweeps one or more profile curves along a path, marks sharp edges automatically; no UVs generated. Curve primitives exist as nodes. — [Blender 3.0 procedural curves](https://code.blender.org/2021/09/procedural-curves-in-3-0-and-beyond/), [Blender manual](https://docs.blender.org/manual/en/4.4/modeling/curves/properties/geometry.html), [CurveToMeshUV](https://github.com/quellenform/blender-CurveToMeshUV)
- Sverchok (Blender add-on) offers bevel-curve = profile swept along path. — [Sverchok docs](https://nortikin.github.io/sverchok/docs/nodes/surface/bevel_curve.html)
- build123d: draw a Spline in BuildLine, place a cross-section at path start, `sweep()`. — [build123d docs](https://build123d.readthedocs.io/en/latest/examples_1.html)
- libfive meshes SDF-like implicit models with manifold dual contouring (claimed more accurate than marching cubes; forum claim). Python bindings must be built from source with CMake (no confirmed pip wheel). — [Blender Artists SD5 thread](https://blenderartists.org/t/sd5-addon-csg-sdf-modeling-using-libfive/1561003), [libfive repo mirror](https://github.com/mkeeter/ao)
- Pip/pure-Python SDF meshers: fogleman/sdf (marching cubes, mesh simplification), sdfCAD, texosdf fork. — [texosdf](https://pypi.org/project/texosdf/), [py-sdf](https://github.com/rcarmo/py-sdf), [sdfCAD](https://pypi.org/project/sdfcad/)

### Inferences
- Grasshopper/Rhino, Fusion/Onshape, MatterControl, OpenSCAD were not retrieved; they are GUI/CAD or non-Python and, for this app, only useful as quality references (sweep with round profile = target look). Rhino/Fusion are commercial.
- libfive is poor fit for "pip on Windows"; fogleman-style numpy SDF + skimage is the pip-able analogue.

### Gaps
- No sources found on Etsy seller workflows, MatterControl, OpenSCAD polygon/offset specifics, Grasshopper pipe components, or existing web equation-to-STL jewellery sites.

## 2. Technique comparison for strand jewellery

### Takeaway
For thin strands, sampling the curve densely as a polyline and either (a) buffering it with shapely and extruding, or (b) building a swept tube mesh directly from a profile, gives smooth analytic edges with tiny meshes; heightmaps stair-step at pixel size and scale mesh size with area. SDF + marching cubes is robust for crossings/cusps but is still grid-limited (smoother than a binary heightmap only because the field is continuous).

### Cited Findings
- Shapely buffer: `shapely.buffer(geom, distance, quad_segs=..., cap_style, join_style, mitre_limit)`; defaults round caps/joins, quad_segs=8 (segments per quarter circle); join styles round/mitre/bevel; `resolution` is the old name. Union of buffered strands merges crossings automatically. — [Shapely buffer docs](https://shapely.readthedocs.io/en/2.1.1/reference/shapely.buffer.html), [GeoPandas buffer](https://geopandas.org/en/v1.1.2/docs/reference/api/geopandas.GeoSeries.buffer.html)
- scikit-image `marching_cubes(volume, level=None, spacing=(1,1,1), ...)` returns vertices in physical units when spacing set; default level = midpoint of min/max. — [skimage source v0.23.1](https://github.com/scikit-image/scikit-image/blob/v0.23.1/skimage/measure/_marching_cubes_lewiner.py)
- trimesh hard dependency is numpy only; shapely/rtree via `trimesh[easy]`; mapbox-earcut is a recommended optional triangulator. `is_watertight`, `is_winding_consistent`, `euler_number` available. — [trimesh PyPI](https://pypi.org/project/trimesh/), [Debian control](https://tracker.debian.org/media/packages/t/trimesh/control-4.5.1-3)
- build123d/CadQuery B-rep sweeps produce exact surfaces; tessellation tolerance for STL not confirmed in my searches. — [build123d docs](https://build123d.readthedocs.io/en/latest/)

### Comparison (my synthesis; qualitative, mostly [UNVERIFIED] by source)
| Method | Smoothness | Mesh size | Crossings/cusps | Round section | Pip/Windows |
|---|---|---|---|---|---|
| Heightmap raster | stair-steps at pixel (0.05-0.1 mm = visible on 20-40 mm) | grows ~area/pixel^2 | trivial (max) | profile via height only | yes |
| Shapely buffer + extrude (flat-top/bevel stack) | polyline-accurate edges, smoothness set by sampling + quad_segs | small | union handles it | stepped by stacking offsets | yes (wheels) |
| Profile sweep (custom numpy tube) | smoothest, true round/domed section | small | self-intersections give overlapping solids; need union/boolean (manifold3d/ trimesh boolean) | native | yes |
| SDF + marching cubes | smooth normals, voxel-limited; fillets/blends free (smooth-min) | medium-large | robust, smooth union | native via distance-to-curve | yes (numpy/scipy/skimage) |
| B-rep CAD (CadQuery/build123d) | exact | small | booleans can fail on near-tangent/cusps [UNVERIFIED] | native | OCP wheels exist, heavy [UNVERIFIED] |

### Inferences
- Highest-leverage upgrade: replace raster heightmap with distance-field of the polyline (scipy/numpy distance-to-segments on a coarse 3D or 2.5D grid) with a rounded profile h(d)=sqrt(r²-d²) (or domed profile), mesh with marching cubes at 0.03-0.05 mm, or a 2.5D approach: compute 2D signed distance to strand centreline on the grid, derive height analytically, and bilinearly interpolate — removes binary stair-stepping because height varies continuously with sub-pixel distance. [Design suggestion, not sourced.]
- Alternative with smallest meshes: shapely buffer per offset level (e.g. 8-12 nested offsets approximating a dome) and extrude/stack; visible terracing is much finer than pixels but still present.
- Cusps: round joins in shapely avoid spikes; for tubes, cusps produce degenerate frames, so SDF/buffer approaches are more robust.

### Gaps
- No benchmark numbers (speed, triangle counts) found; would need local profiling.

## 3. Equation grammar and safety

### Takeaway
Do not use `sympify`/`parse_expr` or `eval` on user text; use a whitelisted AST walker (or a restricted library) with vectorised numpy evaluation, plus hard limits on expression length, node count, and sample count.

### Cited Findings
- SymPy docs: `parse_expr` uses eval and should not be used on unsanitised input; `evaluate=False` does not change that. — [SymPy parsing docs](https://eksamensvedlegg.it.ntnu.no/Felles/sympy-docs-html-1.14.0/modules/parsing.html), [SO: how safe is sympify](https://kiwix.lema.org/stackoverflow.com_en_all_2023-11/questions/16718644/how-safe-is-sympy-s-sympify-string-evalf)
- asteval claims to avoid known eval exploits but admits perfect safety is hard. — [asteval motivation](https://lmfit.github.io/asteval/_sources/motivation.rst.txt)
- Whitelisting options: `safersympify` (PyPI), DIY `ast` walker allowing only arithmetic node types. — [safersympify](https://pypi.org/project/safersympify/), [gist](https://gist.github.com/M0r13n/5df080f2502565795a8f2d096dc7e69c)
- numexpr described as "safe" only in a tutorial; no security analysis found. — [PythonGuides](https://pythonguides.com/?p=64806) [weak source]

### Inferences / recommendations [design suggestions]
- Own AST whitelist: Num, BinOp(+-*/**), UnaryOp, Call to {sin,cos,tan,exp,log,sqrt,abs,atan2,...}, Name in {t,theta,x,y,pi,e}; cap length (~200 chars), node count, exponent size (guard `**` with huge constants), evaluate on numpy arrays of bounded size (<= e.g. 20k samples).
- Poles/discontinuities: sample, mask non-finite and |value|>bound, split polyline into segments at masked samples or jumps larger than k×median step; adaptive resampling by arc length.
- Implicit curves f(x,y)=0: skimage.measure.find_contours (marching squares) on a grid; parametric/polar: sample t, polar r(θ)→(r cosθ, r sinθ). Closure: check endpoints distance vs strand width, auto-close option.
- Bound cost: grid size cap, timeouts via worker process (Streamlit), vectorised eval only.

### Gaps
- No source on how existing web tools (Desmos/GeoGebra) parse input; Desmos/GeoGebra export features not verified.

## 4. Fractals / complex curves and spacing checks

### Takeaway
Epicycles/Fourier fits turn any closed polygon (including fractal outlines) into a smooth sum of rotating phasors; truncation smooths fine detail, which helps printability. Spacing checks are done with polygon offset/morphology.

### Cited Findings
- Fourier epicycles: sample an SVG path to N points, DFT, keep top-k terms (Bostock: 2000 samples, up to 350 epicycles); n-th term is a circle of radius |c_n|. — [Observable fourier-series-zoom](https://observablehq.com/@mbostock/fourier-series-zoom), [LimitPoint Epicycles](https://www.github.com/LimitPoint/Epicycles)
- No source retrieved on L-systems or IFS for jewellery; fractal behaviour under truncation not covered by results.

### Inferences [UNVERIFIED, standard geometry practice]
- Fourier: use numpy.fft on uniformly arc-length-resampled complex points; keep K lowest-frequency terms; reconstruct at high sample density; Gibbs ringing near corners. 
- Minimum gap check: buffer centreline by w/2 (strand), then verify gap ≥ g by `poly.buffer(-g/2).buffer(g/2)` style opening/closing comparison, or compute distance between non-adjacent segments (shapely STRtree) excluding arc-length neighbours. Strand width check: erosion `buffer(-w_min/2)` must retain the strand. Flag/auto-scale if violated.
- L-system/IFS: generate polylines iteratively with cap on segment count (e.g. 4^n growth); Koch-like fractals have unbounded length so limit depth by minimum segment length ≥ strand width.

### Gaps
- No sourced numbers for minimum strand width / press-mould gap; belongs to materials research.

## 5. Mesh export and validation

### Takeaway
Prefer 3MF (units, smaller, one forum claim of better manifold preservation) with binary STL as a fallback; always check watertight/winding before export.

### Cited Findings
- STL has no units; 3MF stores units, colour/materials, and is compressed (~half STL size per one source). STL's strength is universal support. — [Snapmaker 3MF vs STL](https://www.snapmaker.com/blog/3mf-vs-stl/), [Autodesk](https://www.autodesk.com/products/fusion-360/blog/3mf-next-generation-file-format-additive-manufacturing/), [Prusa](https://blog.prusaprinters.org/3mf-file-format-and-why-its-great), [Xometry](https://www.xometry.com/resources/3d-printing/3mf-file-format/)
- OpenSCAD list reply: 3MF may preserve manifold topology that STL loses because vertex-duplication info is stored (forum opinion). — [OpenSCAD list thread](https://lists.openscad.org/empathy/thread/N5P4GYNGPMWBABHCN7UTDTNCRQW5CX7E)
- trimesh imports 3MF and exports STL; 3MF export support in trimesh is [UNVERIFIED] here (trimesh docs not fetched; I believe it requires lxml-type extras).
- A manifold mesh has each edge shared by exactly two faces. — [Meshy blog](https://www.meshy.ai/blog/fix-non-manifold-edges-stl-repair) [weak source]

### Inferences
- Validation checklist: `is_watertight`, `is_winding_consistent`, `euler_number`, `volume>0`, merge vertices before export (`process=True`/`merge_vertices`), remove degenerate faces, bounding-box sanity in mm; run `trimesh.repair` as last resort. Simplification: quadric decimation needs fast-simplification/open3d; not verified.

### Gaps
- Slicer expectations beyond folklore not found; 3MF export via trimesh not confirmed; simplification library licensing not checked.

## 6. Recommendations for the heightmap app (Python/Streamlit/trimesh/numpy/scipy)

### Takeaway
Ranked upgrades (design judgement, mostly unsourced):
1. Stop binarising: compute distance-to-centreline (scipy.ndimage.distance_transform_edt with sub-pixel via analytic point-to-segment distance for accuracy) and map to a continuous round/domed height; stair-stepping from the edge largely disappears. Coarser grid may suffice.
2. Or polyline-first geometry: sample curve adaptively, shapely union of buffered segments (round joins, quad_segs ≥16), then extrude / layer offsets; mesh size drops by orders of magnitude.
3. Mesh with skimage marching_cubes at spacing in mm (sourced above), then light Taubin/Laplacian smoothing (trimesh.smoothing) [UNVERIFIED parameters] limited to avoid shrinking strands.
4. Replace any eval with whitelisted AST + bounds; split at poles.
5. Add min-gap/min-width checks via buffer opening; report violations in UI.
6. Export 3MF (units mm) plus STL; run watertight checks and show status.
7. Optional: custom tube sweep with rotation-minimising frames for true round sections; union via a manifold boolean library [UNVERIFIED availability on Windows].

### Gaps
- None of the quality/speed claims were benchmarked; recommend a quick local A/B (triangle count, max deviation from ideal profile) before committing.
