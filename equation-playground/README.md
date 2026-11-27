# Equation playground

Type an equation. Tune sliders. Export SVG and STL.

## Install

    pip install -r requirements.txt

## Run

    streamlit run app.py

## What to type

| Kind | Example | Sliders |
|---|---|---|
| explicit | `y = a sin(b x)` | a, b |
| implicit | `x^2 + y^2 = r^2` | r |
| parametric | `x = a cos(t), y = b sin(k t)` | a, b, k |
| polar | `r = a + b cos(k theta)` | a, b, k |
| surface | `z = a sin(x) cos(y)` | a |

## How sliders are chosen

`x y z t theta r` are axes when the kind uses them.
Every other symbol is a slider. `pi`, `e`, `E` are constants.
In `x^2 + y^2 = r^2`, `r` is a slider.
Sliders start at 1.0, range -5 to 5, step 0.01.

## Make it

- **Form type**: Full 3D (default) = bottom half + top half pressed together, piece domed both sides. Flat back = one mould + flat lid.
- **Alignment pins**: 3 pins on the top half / lid, sockets in the mould. One pin is 1 mm bigger so parts cannot go together backwards. Mould face stays flat for blade shaving.
- **Overflow**: gutter ring around the form, vent lines to the block edge, relief pockets in enclosed gaps. Bottom half only (pockets on both).
- **Loop**: auto (top, over centre of mass) or by angle. Shift in/out. Outer dia, hole dia, height.
- **Rotate / mirror** the shape before the loop is placed.
- **Draft build**: 0.1 mm pixel, fast look. **Build**: print quality.

## Export

SVG (2D kinds), form STL, mould STL, top half or lid STL. Or one zip with all plus `design.json` (equation, settings, check, clay balls).

## Check report

- **Separate pieces**: more than 1 warns.
- **Thinnest feature**: warns below 1.0 mm.
- **Thinnest resin wall**: warns below 0.6 mm.
- **Hang tilt**: warns above 5 deg.
- **Watertight**: both should be True.

## Clay

Exact cavity volume from the heightmap, plus extra % (default 15). Given as N equal balls with diameter in mm for calipers. Placement map shows where each ball goes. Editor only, never in any STL. Grams use 1.7 g/cm3 (approximate).

## Cost

Enter clay price paid + grams bought, resin price paid + ml bought, presses per mould. Gives clay cost per piece, mould resin cost, cost per piece and per pair. Saved in `prices.json`.

## Defaults

- Strand 1.8 x 1.2 mm (width x height). Draft 20 deg.
- Size 40 mm. Pixel 0.05 mm.
- Pair on: L + mirrored R.
- Loop od 5.0 mm, hole 1.8 mm.
- Pins 3.0 mm dia, 2.0 mm high, 0.15 mm clearance.

## Limits

- No inequalities. No ODEs or derivatives.
- `f(x)` means `f*x`. `f` becomes a slider.
- Complex values are not drawn.
