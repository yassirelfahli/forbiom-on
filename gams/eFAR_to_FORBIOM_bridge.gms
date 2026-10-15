* =========================================================================
* eFAR -> FORBIOM bridge include for SA13.gms
* Purpose:
*   Overwrite placeholder FORBIOM parameters with empirical values prepared
*   from eFAR data and saved in input/efar_bridge.gdx.
*
* Expected symbols in input/efar_bridge.gdx:
*   ef_millCap(r,p,y)        [MILLION m3/year]
*   ef_arcCap(r,rr,p,y)      [MILLION m3/year]
*   ef_demandCapBase(r,p,y)  [MILLION m3/year]
*   ef_harvestCost_y(r,y)    [$ / m3]
*   ef_transportCost(r,rr,p) [$ / m3]
*
* Notes:
* - Any missing cell stays at your existing SA13 default.
* - This file does not change model structure, only calibration values.
* =========================================================================

PARAMETERS
    ef_millCap(r,p,y)        "eFAR calibrated mill capacity"
    ef_arcCap(r,rr,p,y)      "eFAR calibrated arc capacity"
    ef_demandCapBase(r,p,y)  "eFAR calibrated baseline demand cap"
    ef_harvestCost_y(r,y)    "eFAR calibrated harvest cost by region and year"
    ef_transportCost(r,rr,p) "eFAR calibrated transport cost";

$if not exist "input/efar_bridge.gdx" $goto no_efar_bridge

$gdxin input/efar_bridge.gdx
$loadDC ef_millCap ef_arcCap ef_demandCapBase ef_harvestCost_y ef_transportCost
$gdxin

* ---- Surgical overwrite of placeholders with empirical data ----
millCap(r,p,y)$ef_millCap(r,p,y) = ef_millCap(r,p,y);
arcCap(r,rr,p,y)$ef_arcCap(r,rr,p,y) = ef_arcCap(r,rr,p,y);
demandCapBase(r,p,y)$ef_demandCapBase(r,p,y) = ef_demandCapBase(r,p,y);
harvestCost_y(r,y)$ef_harvestCost_y(r,y) = ef_harvestCost_y(r,y);
transportCost(r,rr,p)$ef_transportCost(r,rr,p) = ef_transportCost(r,rr,p);

* Demand cap used in constraints and scenario loops.
demandCap_y(r,p,y) = demandCapBase(r,p,y);

put_utility 'log' /
    'eFAR bridge loaded: millCap/arcCap/demandCapBase/harvestCost_y/transportCost overwritten from input/efar_bridge.gdx';
$goto end_efar_bridge

$label no_efar_bridge
put_utility 'log' /
    'eFAR bridge skipped: input/efar_bridge.gdx not found, using SA13 defaults.';

$label end_efar_bridge
