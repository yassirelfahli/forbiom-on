* =========================================================================
* build_efar_bridge.gms
* Build input/efar_bridge.gdx from CSV files prepared from eFAR workbook.
*
* Run from Papers/Forbiom:
*   gams build_efar_bridge.gms
*
* Input CSV files expected in input/:
*   ef_millCap.csv         columns: r,p,y,value
*   ef_arcCap.csv          columns: r,rr,p,y,value
*   ef_demandCapBase.csv   columns: r,p,y,value
*   ef_harvestCost_y.csv   columns: r,y,value
*   ef_transportCost.csv   columns: r,rr,p,value
*
* Output:
*   input/efar_bridge.gdx
* =========================================================================

SETS
    r  "FORBIOM regions" /TroutLake, Abitibi, Algoma, Kenora, Nipissing, Algonquin/
    rr "FORBIOM destination region alias" /TroutLake, Abitibi, Algoma, Kenora, Nipissing, Algonquin/
    p  "FORBIOM products" /CLT, Glulam, Lumber, Pulpwood/
    y  "FORBIOM years" /2020*2030/;

PARAMETERS
    ef_millCap(r,p,y)        "Calibrated mill capacity (MILLION m3/year)"
    ef_arcCap(r,rr,p,y)      "Calibrated lane capacity (MILLION m3/year)"
    ef_demandCapBase(r,p,y)  "Calibrated baseline demand cap (MILLION m3/year)"
    ef_harvestCost_y(r,y)    "Calibrated harvest cost ($/m3)"
    ef_transportCost(r,rr,p) "Calibrated transport cost ($/m3)";

* Default to zero for sparse data merges.
ef_millCap(r,p,y) = 0;
ef_arcCap(r,rr,p,y) = 0;
ef_demandCapBase(r,p,y) = 0;
ef_harvestCost_y(r,y) = 0;
ef_transportCost(r,rr,p) = 0;

* Convert CSV -> temporary GDX files (only if file exists).
$if exist "input/ef_millCap.csv"       execute 'csv2gdx input/ef_millCap.csv id=ef_millCap       index=1,2,3 values=4 useHeader=Y trace=0 output=input/ef_millCap.gdx'
$if exist "input/ef_arcCap.csv"        execute 'csv2gdx input/ef_arcCap.csv id=ef_arcCap         index=1,2,3,4 values=5 useHeader=Y trace=0 output=input/ef_arcCap.gdx'
$if exist "input/ef_demandCapBase.csv" execute 'csv2gdx input/ef_demandCapBase.csv id=ef_demandCapBase index=1,2,3 values=4 useHeader=Y trace=0 output=input/ef_demandCapBase.gdx'
$if exist "input/ef_harvestCost_y.csv" execute 'csv2gdx input/ef_harvestCost_y.csv id=ef_harvestCost_y index=1,2 values=3 useHeader=Y trace=0 output=input/ef_harvestCost_y.gdx'
$if exist "input/ef_transportCost.csv" execute 'csv2gdx input/ef_transportCost.csv id=ef_transportCost index=1,2,3 values=4 useHeader=Y trace=0 output=input/ef_transportCost.gdx'

* Load whichever converted files exist.
$if exist "input/ef_millCap.gdx"       execute_load 'input/ef_millCap.gdx',       ef_millCap=ef_millCap;
$if exist "input/ef_arcCap.gdx"        execute_load 'input/ef_arcCap.gdx',        ef_arcCap=ef_arcCap;
$if exist "input/ef_demandCapBase.gdx" execute_load 'input/ef_demandCapBase.gdx', ef_demandCapBase=ef_demandCapBase;
$if exist "input/ef_harvestCost_y.gdx" execute_load 'input/ef_harvestCost_y.gdx', ef_harvestCost_y=ef_harvestCost_y;
$if exist "input/ef_transportCost.gdx" execute_load 'input/ef_transportCost.gdx', ef_transportCost=ef_transportCost;

* Export single bridge file consumed by eFAR_to_FORBIOM_bridge.gms.
execute_unload 'input/efar_bridge.gdx',
    ef_millCap, ef_arcCap, ef_demandCapBase, ef_harvestCost_y, ef_transportCost;

put_utility 'log' / 'Built input/efar_bridge.gdx from available CSV files in input/.';
