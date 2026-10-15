* =========================================================================
* eFAR -> FORBIOM bridge include for S20.txt
* Uses bridge GDX produced in Papers/Forbiom/input/efar_bridge.gdx
* =========================================================================

PARAMETERS
    ef_millCap(r,p,y)        "eFAR calibrated mill capacity"
    ef_arcCap(r,rr,p,y)      "eFAR calibrated arc capacity"
    ef_demandCapBase(r,p,y)  "eFAR calibrated baseline demand cap"
    ef_harvestCost_y(r,y)    "eFAR calibrated harvest cost by region and year"
    ef_transportCost(r,rr,p) "eFAR calibrated transport cost";

$if not exist "Papers/Forbiom/input/efar_bridge.gdx" $goto no_efar_bridge_s20

$gdxin Papers/Forbiom/input/efar_bridge.gdx
$loadDC ef_millCap ef_arcCap ef_demandCapBase ef_harvestCost_y ef_transportCost
$gdxin

* Overwrite only where data exists; otherwise keep S20 defaults.
millCap(r,p,y)$ef_millCap(r,p,y) = ef_millCap(r,p,y);
arcCap(r,rr,p,y)$ef_arcCap(r,rr,p,y) = ef_arcCap(r,rr,p,y);
demandCapBase(r,p,y)$ef_demandCapBase(r,p,y) = ef_demandCapBase(r,p,y);
harvestCost_y(r,y)$ef_harvestCost_y(r,y) = ef_harvestCost_y(r,y);
transportCost(r,rr,p)$ef_transportCost(r,rr,p) = ef_transportCost(r,rr,p);

* Keep demand caps consistent for constraints and scenario loops.
demandCap_y(r,p,y) = demandCapBase(r,p,y);

put_utility 'log' /
    'S20 eFAR bridge loaded from Papers/Forbiom/input/efar_bridge.gdx';
$goto end_efar_bridge_s20

$label no_efar_bridge_s20
put_utility 'log' /
    'S20 eFAR bridge skipped: Papers/Forbiom/input/efar_bridge.gdx not found, using S20 defaults.';

$label end_efar_bridge_s20
