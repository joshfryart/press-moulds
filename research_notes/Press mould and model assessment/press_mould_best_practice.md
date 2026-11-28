# Press mould best practice for clay jewellery (3D-printed resin / silicone moulds) - external benchmark

Research date: 2026-11-28. Method note: roughly 14 tool calls. Several sources below were read only via search-result summaries, not full-page fetches; these are marked "(snippet)". Coverage is uneven: shrinkage, resin cure/safety and orientation are reasonably sourced. Hard numeric rules for press-mould draft, wall thickness, flash gutters, registration clearance and thin-earthenware minimum thickness are largely NOT found in authoritative sources (see Gaps). Values labelled "Inference" are not sourced and should be treated as hypotheses to test, not benchmarks.

## 1. Clay shrinkage and scale compensation (earthenware, porcelain; holes for jump rings)

### Takeaway
Shrinkage is two-stage (wet-to-dry, dry-to-fired) and the stages compound rather than add. The SIO-2 PA white earthenware datasheet gives only 6.8% drying and -0.4% firing at cone 04 (about 6.4% total), well below the "12-15%" quoted for porcelain. Scale CAD by 1/(1 - total shrinkage), and use a test tile for the specific clay and firing.

### Cited Findings
- SIO-2 "PA" white earthenware (Ceramica Collet): biscuit firing range cone 05-03 (1911-2019 F); water content 20%; Atterberg plasticity 16; CaCO3 17%; drying shrinkage 6.8%; firing shrinkage at cone 04 = -0.4% (slight expansion); absorption at cone 04 12.3%; dry bending strength 5.1 N/mm2; fired 27.8 N/mm2 at cone 04; thermal expansion 79.1e-7 /C. Sold as a wheel/modelling body, 12.5 kg packs. No cone 05 shrinkage is published; PDF creation date 2021-05-30 — [SIO-2 PA datasheet (hosted by ceramiq.pl)](https://www.ceramiq.pl/pliki/Karty/PA_us.pdf) (read directly from the PDF text)
- Drying and firing shrinkage are measured on different bases (wet-to-dry vs dry-to-fired) and cannot simply be added. Digitalfire's example: 6.25% dry + 6.66% fired = 12.9% if added, but true total is 12.5%; the total is a little less than the sum — [Digitalfire tech-tip (snippet)](https://digitalfire.com/picture/2239) and [Digitalfire glossary: firing shrinkage (snippet)](https://digitalfire.com/glossary/firing+shrinkage)
- Digitalfire: fired shrinkage rises with temperature to a maximum (usually below 15%), plateaus, then can fall (bloating/over-firing). Plainsman "Polar Ice" porcelain 14-15% total, described as about the highest normally encountered for a pottery clay (snippet) — [Digitalfire](https://digitalfire.com/glossary/firing+shrinkage)
- A German porcelain maker's phased figures: drying 1-3%, biscuit 10-12%, hard fire 12-15%, single fire 14-22%; 20%+ seen internationally. This is industrial hard-fired porcelain, not cone 06-04 (snippet) — [Holst Porzellan](https://holst-porzellan.com/en/knowledge/kiln-and-firing/shrinkage/)
- Valentine Clays (UK supplier): shrinkage has two stages, earthenware typically 5-10%, stoneware/porcelain "10-15% or more"; page gives no scaling formula — [Valentine Clays shrinkage rates](https://valentineclays.co.uk/pages/shrinkage-rates)
- Forum posters report typical porcelain around 10-11% (rising with ball clay) and manufacturer listings 12-15% — [Ceramic Arts Daily forum, porcelain survey (snippet; low-quality anecdotal)](https://community.ceramicartsdaily.org/topic/13999-porcelain-survey/page/3/)
- Shapeways porcelain (2016; slip-cast service, glazed) guidance: glaze layer about 1-2 mm thick; holes should be >5 mm (a 4 mm hole closed up with glaze); fine detail min 1 mm height and width; thin wires/walls >3 mm for breakage in clean-up; 2 mm clearance per wall for fit; feet higher than glaze thickness. Page warns it may be outdated and the numbers are for a service with heavy glaze, so they are conservative for hobby jewellery — [Shapeways: tips for designing in porcelain](https://www.shapeways.com/blog/tips-for-designing-in-porcelain)

### Inferences
- Total shrinkage T = 1 - (1 - d)(1 - f) (my arithmetic reproduces Digitalfire's 12.5% example). For SIO-2 PA at cone 04: 1 - 0.932 x 1.004 = about 6.4%; scale factor 1/(1 - T) = about 1.068 (about 6.8% oversize). Sensitive to the negative firing figure and to the unpublished cone 05 value; a reasonable CAD default range for low-fire white earthenware is 6-10% (scale 1.06-1.11) pending a test tile.
- Porcelain at 12-15% total means scale 1.14-1.18; note that scaling by 1/(1-T) not (1+T) matters more as T grows (15% => 1.176, not 1.15).
- A mould-generation app should expose per-clay shrinkage (drying, firing) as inputs and apply the compound formula, and should scale hole diameters by the same factor and add margin for glaze (hole diameter after glaze = fired hole minus about 2x glaze thickness; for jump rings aim for roughly 1.5-2 mm finished plus extra if glazed). Unsourced; test.

### Gaps
- No cone 05 shrinkage figure for SIO-2 PA; the sheet's -0.4% at cone 04 is surprising for a pure total and is unexplained (manufacturer contact info@sio-2.com is on the sheet). SIO-2 porcelain datasheets were not retrieved.
- No source found on hole-size compensation for jump rings specifically.
- Holst, Valentine and forum figures were read from search summaries only.

## 2. Mould geometry: draft, wall thickness, cavity depth, undercuts, one vs two part, registration

### Takeaway
Authoritative numbers are scarce. The one explicit figure found (at least 2 degrees draft on exterior, 3 degrees interior, more for texture) comes from a single non-authoritative blog; forum experience says there is no single best angle. Undercut detection and registration-key practice are well described qualitatively.

### Cited Findings
- Draft: "at least 2 degrees of taper on exterior surfaces and 3 degrees on interior features, textured surfaces need more"; too little makes pieces grip, crack, warp or tear. Single-blog source, not ceramics authority — [search result summary of scienceinsights.org plaster mould guide (snippet, low confidence)](https://scienceinsights.org/how-to-make-a-slip-cast-mold-from-plaster/)
- A McNeel (Rhino) forum user making plaster moulds from 3D-printed models reports working with drafts from 2 to nearly 60 degrees and concluding there is no single best angle (anecdotal) — [McNeel forum](https://discourse.mcneel.com/t/advice-and-guidance-adding-or-designing-with-draft-in-mind/215566.md)
- Undercut test: view from above and run a fingernail down the casting area; if you cannot see the nail tip at any point there is an undercut to remove — [Ceramics Monthly, Mold Making 101 (snippet)](https://ceramicartsnetwork.org/ceramics-monthly/ceramics-monthly-article/Monthly-Methods-Mold-Making-101)
- Registration: carve cone-shaped keys (natches) into the flat parting surface so the second half gets matching bumps; plastic natches are an alternative; a vendor 3D-printed case-mould system uses 13.5 mm holes for its natches (vendor, promotional) — [Ceramics Monthly Mold Making 101 (snippet)](https://ceramicartsnetwork.org/ceramics-monthly/ceramics-monthly-article/Monthly-Methods-Mold-Making-101); [Digitalfire: mold natches](https://digitalfire.com/glossary/mold+natches)
- Formlabs design specs (print limits, Clear resin at 100 micron): minimum wall 0.4 mm on Form 2, 0.2 mm on Form 3; minimum unsupported overhang 10 degrees from horizontal; drain holes 2.5-3.5 mm for enclosed cavities; at least 0.5 mm clearance between moving parts or they may fuse — [Formlabs design specs](https://formlabs.com/support/Design-Specs/) (snippet)
- Printed polymer-clay earring moulds exist on MakerWorld at about 24 x 21 x 13 mm and 24 x 30 x 12.5 mm; one print used 0.2 mm layers, 2 walls, 20% infill; a commenter found cutting the clay out hard; several are licensed non-commercial/no redistribution — [MakerWorld 1239249](https://makerworld.com/models/1239249), [MakerWorld 1403553](https://makerworld.com/models/1403553)

### Inferences
- A press mould for a relief earring is normally one-part (open face) with the whole relief having positive draft relative to the pressing direction; pieces with true undercuts or full 3D shape need two parts with keys. Not directly sourced.
- Benchmark tests for an app: undercut detection relative to the pull direction, per-face draft check (flag below about 2-3 degrees, no source better than the blog above), minimum feature size consistent with the print resolution and clay (at least about 1 mm detail per Shapeways, practically limited by clay grain and layer lines), registration key clearance of at least 0.2-0.5 mm per side (extrapolating Formlabs 0.5 mm; unsourced).
- Mould walls of 0.2-0.4 mm are printable, but a press mould needs far more for stiffness (multiple mm) - unsourced.

### Gaps
- No source found for: recommended cavity depth, minimum strand width that presses reliably in earthenware/polymer clay, flash/overflow gutter dimensions, how much extra clay, key/pin clearance values for resin press moulds, minimum mould wall for pressing. These are likely tacit hobbyist knowledge not published in citable form.

## 3. Pressing, release, drying, thin ceramic jewellery, weight

### Takeaway
Polymer clay: silicone usually needs no release; water or cornstarch if it sticks; bake per brand. Ceramic: thin porcelain/earthenware fails mainly from uneven drying, so dry slowly and evenly and support thin parts. Explicit minimum thickness and earring-weight numbers were not found.

### Cited Findings
- Sculpey Premo: 275 F (130 C) for 30 min per 1/4 in (6 mm) thickness; silicone moulds usually need no release; if sticking use water or cornstarch (cornstarch rinsed off after baking); clay should be soft to capture detail; let the piece cool before demoulding. Fimo reportedly gets sticky with water. Independent tester baked Premo at 320 F (conflicts with the maker's 275 F) — [Sculpey, using silicone moulds](https://www.sculpey.com/blogs/blog/using-silicone-moulds-with-polymer-clay) (snippet), [Sculpey bakeable moulds](https://www.sculpey.com/blogs/blog/sculpey-bakeable-molds), [Blue Bottle Tree, baking temperature](https://thebluebottletree.com/bake-polymer-clay-temperature/comment-page-1), [Blue Bottle Tree on mold releases](https://thebluebottletree.com/?p=3048705)
- Thin porcelain: slow and even drying is critical; uneven drying (not speed) causes cracks and residual stress; thin walls dry faster than thick; heavy attachments on thin sections warp; remedies include wrapping in airtight chamber rests, foam supports, plastic strips on rims — [Ceramic Arts Network: Persnickety Porcelain](https://ceramicartsnetwork.org/daily/article/Persnickety-Porcelain-How-to-Minimize-Your-Loss-Rate-With-this-Gorgeous-Yet-Difficult-Material); [Digitalfire: drying crack](https://digitalfire.com/glossary/drying+crack); [Digitalfire article on drying without cracks](https://digitalfire.com/article/drying+ceramics+without+cracks) (all snippets)
- Porous 3D-printed moulds let casting material penetrate and conventional release agents may not prevent it; coatings (silazane, silicone sprays) help release - patent/academic sources for injection/cold casting, not clay — [US patent 10946556 (snippet)](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/10946556)
- Traditional ceramic jewellery press mould: model attached to slab, cottle wall, plaster poured; the article gives no thickness, undercut, release or firing numbers — [Ceramic Arts Network plaster press mould](https://ceramicartsnetwork.org/daily/pottery-making-techniques/ceramic-decorating-techniques/how-to-make-and-use-a-plaster-press-mold-to-make-ceramic-jewelry/)

### Inferences
- Plaster (absorbent) moulds help earthenware release by wicking water; resin and silicone are non-absorbent so wet clay sticks more and needs cornstarch/talc/light dusting, partial drying to leather-hard in the mould, or flexible silicone for demoulding. Unsourced; test.
- Practical earthenware jewellery thickness is typically of the order of 2-4 mm fired with lightweight designs and small hole radius; not sourced.

### Gaps
- No sourced minimum thickness for fired earthenware/porcelain jewellery, no earring weight limit (often cited by makers around 10-15 g per earring; not found in a citable source), no sourced amount of extra clay or overflow gutter design, no direct comparison of ceramic clay release from resin vs silicone, no Canadian-specific guidance (SIO-2 is sold in Canada, e.g. PSH listing found, not read).

## 4. 3D printing the mould (resin printers, finish, cure, silicone inhibition, safety)

### Takeaway
Fully clean and fully UV-post-cure resin parts (IPA wash, many hours of UV for silicone moulding). Orient the cavity face steeply or tilted 30-45 degrees to reduce layer lines. Uncured resin is a skin sensitiser; post-cured resin biocompatibility for jewellery contact is resin-specific and wasn't verified.

### Cited Findings
- Platinum-cure silicone can fail to cure against under-cured UV resin; Smooth-On: dip in 91% IPA, wash with dish soap and water, post-cure fully, rotate for about 6 hours (the part yellows when fully cured); tin-cure silicone is far less prone; Inhibit-X is sold for platinum silicone; sealers or release agents help (acrylic dip from a single Hackaday anecdote); forum reports are mixed (some Formlabs clear resin parts worked with mould release only) — [Smooth-On FAQ 210](https://www.smooth-on.com/support/faq/210/), [Smooth-On: Molding UV cured resin best practices (PDF)](https://smooth-on.com/assets/pdf/Molding%20UV%20Cured%20Resin%20Best%20Practices%20Guide.pdf), [Hackaday](https://hackaday.com/2022/10/30/stop-silicone-cure-inhibition-no-fancy-or-expensive-products-required), [Formlabs forum](https://forum.formlabs.com/t/would-dental-resin-inhibit-the-curing-of-platinum-cure-silocone/24661) (all snippets)
- Orientation: tilting 30-45 degrees and avoiding large faces parallel to the build plate reduces layer lines; steeper faces show fewer layers; Formlabs forum advice for a flat-face mould: angle 30 degrees in X and Y; thinner layers reduce stepping at cost of time — [Anycubic troubleshooting guide](https://wiki.anycubic.com/en/resin-3d-printer/anycubic-photon-p1-max/severe-layer-lines-troubleshooting-guide), [Formlabs forum striations thread](https://forum.formlabs.com/t/striations-in-flexible-molds-how-to-reduce-or-remove/14380) (snippets)
- Safety: uncured resin is irritant/sensitiser (sensitisation can be long lasting), most contact happens during wash and post-cure; wear gloves; check SDS (some budget water-washable resins reportedly contain ACMO, claim from a competitor guide); remove jewellery before handling uncured resin — [Formlabs resin safety FAQ](https://formlabs.com/blog/resin-safety-resin-terms-faq/), [Prusa blog on resin safety](https://blog.prusa3d.com/everything-you-always-wanted-to-know-about-resins-and-safety-sla-printing-but-were-afraid-to-ask_70758/), [Trusana safety sheet](https://henryschein.com/us-es/images/zahn/Trusana_3D_Printer_Safety.pdf) (snippets)
- Creality: resin prints must be washed and cured, otherwise they stay soft or sticky — [Creality blog](https://www.creality.com/blog/can-you-make-jewelry-with-a-3d-printer) (snippet; vendor)

### Inferences
- A resin mould is not in contact with skin; only fired/baked clay contacts the wearer, so the main safety concern is clay contamination from under-cured resin (polymer clay especially, baked in mould) and maker handling. Reasoning, not sourced.
- Silicone inhibition only matters if the workflow makes silicone negative moulds from a printed positive (positive -> silicone mould); direct printed negatives do not involve it.
- Resin shrinkage/warp for printed moulds was not found; mould dimensions should be verified on a test piece.

### Gaps
- No sourced XY resolution figures for Elegoo/Anycubic LCD printers (commonly 18-50 micron pixels, unverified here), no sourced warp/shrinkage values for resins, no data on how much layer lines transfer to earthenware or polymer clay, no food/skin safety certification for specific resins, no Canada-specific regulation.

## 5. Tools, community workflows, software

### Takeaway
No dedicated open-source or commercial app that automatically generates clay press moulds from a design was found; makers use general CAD with Boolean subtraction.

### Cited Findings
- Digitalfire describes 3D-printed clay cutters/stampers drawn in Fusion 360 and patterned to print 25 at a time — [Digitalfire video 120](https://digitalfire.com/video/120)
- Adafruit tutorial: lithophane generator turns artwork into relief for 3D-printed stamp moulds — [Adafruit](https://learn.adafruit.com/how-to-3d-print-molds-for-custom-stamps)
- A Grasshopper (Rhino) script for automatic master mould generation exists (licence unverified) — [STLFinder listing](https://www.stlfinder.com/model/automatic-master-mould-generation-Pgoh2Ewj/126134) (snippet)
- MakerWorld hosts many ready-made polymer-clay earring moulds and a parametric stamp generator; licences often restrict commercial use — [MakerWorld search results above](https://makerworld.com/models/1239249)
- Etsy, Instructables, Blue Bottle Tree and maker forums exist for this (Blue Bottle Tree and Sculpey above); no Etsy seller documentation was retrieved.

### Gaps
- Fusion 360 / Blender / Meshmixer / "Mold Maker"-type feature set not verified; commercial products (e.g. dedicated ceramic jewellery mould generators) not found.

## 6. Pitfalls that cause failed pieces

### Takeaway
Drawn from the sources above plus inference; mostly drying, draft/undercuts, release and cure problems.

### Cited Findings
- Insufficient draft or undercuts: piece grips the mould, tears or cracks on removal — [scienceinsights.org (snippet)](https://scienceinsights.org/how-to-make-a-slip-cast-mold-from-plaster/)
- Uneven drying, heavy attachments on thin sections: cracks and warping — [Ceramic Arts Network porcelain](https://ceramicartsnetwork.org/daily/article/Persnickety-Porcelain-How-to-Minimize-Your-Loss-Rate-With-this-Gorgeous-Yet-Difficult-Material) (snippet)
- Holes closed by glaze (4 mm closed, 5 mm open in Shapeways' thick glaze) — [Shapeways](https://www.shapeways.com/blog/tips-for-designing-in-porcelain)
- Under-cured or unwashed resin: sticky surface, silicone inhibition — [Smooth-On FAQ 210](https://www.smooth-on.com/support/faq/210/)
- Wrong shrinkage assumption (adding rather than compounding stages, or using a hard-fired porcelain figure for low-fire earthenware) — [Digitalfire](https://digitalfire.com/picture/2239)
- Baking polymer clay in a non-bakeable mould, or demoulding before cooling — [Sculpey](https://www.sculpey.com/blogs/blog/sculpey-bakeable-molds)

### Inferences
- Layer lines and printed surface porosity transfer to the clay and increase sticking; sand/seal or coat the mould surface.
- Trapped air and no vent/flash path in deep cavities cause under-filled detail; unsourced.

### Gaps
- Anecdotal pitfalls from Etsy/forum sellers not retrieved.

## Source quality flags
- Strong: SIO-2 PA datasheet (primary, read in full); Formlabs, Smooth-On, Sculpey (vendor but primary); Digitalfire (respected technical site, summaries only).
- Weak/anecdotal: scienceinsights.org draft figures, McNeel and Formlabs forums, Ceramic Arts forum, MakerWorld, Creality/Hackaday.
- Conflicts: Premo bake temperature (275 F official vs 320 F tester); porcelain shrinkage 10-11% (forum) vs 12-15% (makers) vs up to 22% single fire (industrial); Shapeways porcelain figures are a glazed slip-cast service, dated 2016.
