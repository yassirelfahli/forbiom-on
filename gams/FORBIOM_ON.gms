* =========================================================================
* FORBIOM MODEL
* - logistics constraints include arc capacities + mill capacities
* - prices are FIXED to exogenous basePrice_y path 
* - all economic flow variables are in MILLION m3
* - prices/costs are in $/m3
* - objective and totals are therefore in MILLION $
* =========================================================================

* =========================================================================
* 1. MODEL STRUCTURE (SETS)
* =========================================================================
SETS
    r       "Regions" /TroutLake, Abitibi, Algoma, Kenora, Nipissing, Algonquin/
    p       "Products" /CLT, Glulam, Lumber, Pulpwood/
    y       "Years" /2020*2030/
    tree    "Tree Species" /Spruce, JackPine, WhiteBirch, TolerantHdwds, WhitePine, RedPine, Aspen/
    s       "Site Class" /SC1, SC2, SC3/
    age     "Forest Age" /0*150/
    m       "Manufacturing layers" /Primary, Secondary/
    met     "Tier metrics" /Production, Revenue, ProcessingCost/
    comp    "Product chain cost components" /BaseProcessing, ProductMarkup, LumberInputCost, Total/
    cpScen  "Carbon price sensitivity scenarios" /cp0, cp50, cp100, cp170, cp250, cp350, cp500/
    outMet  "Sensitivity output metrics"
            /Obj, Zprofit, Zemission, CarbonStorage, NetCarbon, NetCarbDel, NetCarbPct,
             CarbonCost, Revenue, HarvestCost, ProcCost, TransCost, TotalHarvest, TotalProduction, TotalSales/
    chgMet  "Change metrics for scenario deltas" /AbsChange, PctChange/
    demCol  "Demand-sensitivity chart columns (same layout as former mt chart)" /DemandMultiplierCLTGlulam, Obj, Zprofit, Zemission, CarbonCost, Revenue, HarvestCost, ProcCost, TransCost, TotalHarvest, TotalProduction, TotalSales/
    demScen "Demand-change scenarios (Table 3 style, 6 regions)" /Baseline, D50, D100, D200, D300, D400, DU10/
    pubRow  "Publication summary rows: carb_* = carbon-price sweep; dem_* = demand sweep at cp170"
            / carb_cp0, carb_cp50, carb_cp100, carb_cp170, carb_cp250, carb_cp350, carb_cp500
              dem_Baseline, dem_D50, dem_D100, dem_D200, dem_D300, dem_D400, dem_DU10 /
    tabSumCol(outMet) "Pub table: Obj, gross em., stored C, net C, delta & pct vs ref, harvest" /Obj, Zemission, CarbonStorage, NetCarbon, NetCarbDel, NetCarbPct, TotalHarvest/
    prScen  "Lumber price sensitivity scenarios" /Pbase, PD5, PI5, PD10, PI10/
    cmScen  "Coupled demand + lumber price scenarios" /CM_D100_PD5, CM_D100_PI10, CM_D200_PD10/;

ALIAS (r, rr);

SET pubCarbRow(pubRow, cpScen) /
    carb_cp0.cp0, carb_cp50.cp50, carb_cp100.cp100, carb_cp170.cp170
    carb_cp250.cp250, carb_cp350.cp350, carb_cp500.cp500
/;

SET pubDemRow(pubRow, demScen) /
    dem_Baseline.Baseline, dem_D50.D50, dem_D100.D100, dem_D200.D200
    dem_D300.D300, dem_D400.D400, dem_DU10.DU10
/;

* =========================================================================
* 2. DATA INPUT: YIELD TABLES (Plonski Volume m3/ha)
* =========================================================================
PARAMETER YieldData(tree, s, age) "Gross Merchantable Volume (m3/ha)";

* [DATA INPUT: WHITE PINE SC1]
YieldData('WhitePine', 'SC1', '30') = 76;   YieldData('WhitePine', 'SC1', '40') = 157;
YieldData('WhitePine', 'SC1', '50') = 242;  YieldData('WhitePine', 'SC1', '60') = 315;
YieldData('WhitePine', 'SC1', '70') = 372;  YieldData('WhitePine', 'SC1', '80') = 414;

* [DATA INPUT: JACK PINE SC1]
YieldData('JackPine', 'SC1', '30') = 89;    YieldData('JackPine', 'SC1', '40') = 155;
YieldData('JackPine', 'SC1', '50') = 196;   YieldData('JackPine', 'SC1', '60') = 223;
YieldData('JackPine', 'SC1', '70') = 238;   YieldData('JackPine', 'SC1', '80') = 243;

* [DATA INPUT: TOLERANT HARDWOODS SC1]
YieldData('TolerantHdwds', 'SC1', '30') = 36;
YieldData('TolerantHdwds', 'SC1', '40') = 68;
YieldData('TolerantHdwds', 'SC1', '50') = 100;
YieldData('TolerantHdwds', 'SC1', '60') = 130;
YieldData('TolerantHdwds', 'SC1', '70') = 158;
YieldData('TolerantHdwds', 'SC1', '80') = 185;

* [DATA INPUT: SITE CLASS PROXIES]
YieldData(tree, 'SC2', age) = YieldData(tree, 'SC1', age) * 0.80;
YieldData(tree, 'SC3', age) = YieldData(tree, 'SC1', age) * 0.60;

* [DATA INPUT: SPECIES PROXIES]
YieldData('RedPine', s, age)    = YieldData('WhitePine', s, age);
YieldData('Spruce', s, age)     = YieldData('JackPine', s, age);
YieldData('Aspen', s, age)      = YieldData('JackPine', s, age) * 0.9;
YieldData('WhiteBirch', s, age) = YieldData('JackPine', s, age) * 0.8;

* =========================================================================
* 3. REGIONAL PARAMETERS
* =========================================================================
TABLE speciesMix(r, tree) "Forest Composition (%)"
               Spruce  JackPine WhiteBirch TolerantHdwds WhitePine RedPine Aspen
    TroutLake   0.50    0.30     0.10       0.00          0.00      0.00    0.10
    Abitibi     0.60    0.20     0.10       0.00          0.00      0.00    0.10
    Kenora      0.40    0.40     0.10       0.00          0.00      0.05    0.05
    Algoma      0.10    0.05     0.10       0.40          0.30      0.05    0.00
    Nipissing   0.10    0.05     0.10       0.30          0.40      0.05    0.00
    Algonquin   0.05    0.00     0.10       0.50          0.30      0.05    0.00;

PARAMETERS
    initialAge(r)        /TroutLake 30, Abitibi 30, Algoma 30, Kenora 30, Nipissing 30, Algonquin 30/
    initialStockRegion(r) "Initial ROUNDWOOD stock (MILLION m3)"
                         /TroutLake 28.99948, Abitibi 107.77522, Algoma 54.88489, Kenora 49.74619, Nipissing 45.26169, Algonquin 36.72526/;

SET regionSite(r, s) "Dominant site class"
/
    TroutLake.SC2
    Abitibi.SC2
    Algoma.SC1
    Kenora.SC3
    Nipissing.SC1
    Algonquin.SC1
/;


PARAMETERS
    regionArea(r)   "Calculated hectares"
    CAI_Region(r,y) "Annual roundwood growth (MILLION m3/year)"
    initStockRW(r)  "Initial roundwood stock (MILLION m3)"
    growthRW(r,y)   "Roundwood growth (MILLION m3/year)";

regionArea(r) =
    (initialStockRegion(r) * 1000000)
    /
    sum((tree, age, s)$(ord(age)-1 = initialAge(r) and regionSite(r, s)),
        speciesMix(r, tree) * YieldData(tree, s, age));

LOOP(y,
   LOOP(r,
      CAI_Region(r, y) =
         sum(tree,
             speciesMix(r, tree) *
             (
               sum((age, s)$(ord(age)-1 = initialAge(r) + 10 and regionSite(r, s)), YieldData(tree, s, age))
             - sum((age, s)$(ord(age)-1 = initialAge(r)      and regionSite(r, s)), YieldData(tree, s, age))
             )
         ) / 10 * regionArea(r) / 1000000;
   );
);

initStockRW(r) = initialStockRegion(r);

* Stochastic growth shock (climate, disturbance, measurement) - reproducible
* Range ~0.88 to 1.12 (±12%) for realistic interannual variability
SCALAR growthShockMin /0.88/, growthShockMax /1.12/;
PARAMETER growthShock(r,y) "Annual growth multiplier (region- and year-specific)";
growthShock(r,y) = growthShockMin + (growthShockMax - growthShockMin)
    * mod(ord(r)*31 + ord(y)*17 + 7, 97) / 97;
growthRW(r,y)  = CAI_Region(r,y) * growthShock(r,y);

* Stochastic harvest cost shock - region- and year-specific, non-deterministic
* Range ~0.90 to 1.10 (±10%). Use LOOP so each (r,y) gets independent uniform draw.
* For reproducibility: gams SA4.gms --seed=N
SCALAR harvestCostShockMin /0.90/, harvestCostShockMax /1.10/;
PARAMETER harvestCostShock(r,y) "Harvest cost multiplier by region and year"
          harvestCost_y(r,y)    "Harvest cost by region and year ($/m3)";
LOOP((r,y),
    harvestCostShock(r,y) = uniform(harvestCostShockMin, harvestCostShockMax);
);

* =========================================================================
* 4. ECONOMIC / VALUE-CHAIN PARAMETERS
* =========================================================================
SCALARS
    carbonPrice   "Carbon price ($/tCO2)" /170/
    demandGrowth  "Annual demand growth rate" /0.00/
* 1 = enforce maxHarvestRate ceiling; 0 = drop sustainabilityRW (used in demScen loop)
    useHarvestCeiling "Toggle 1% harvest ceiling (off during demand scenarios)" /1/;

PARAMETERS
    manufacturingTier(p) "1=Primary, 2=Secondary"
                         /CLT 2, Glulam 2, Lumber 1, Pulpwood 1/

    maxHarvestRate(r)    "Max sustainable harvest ratio"
                         /Abitibi 0.01, Algoma 0.01, Algonquin 0.01, Kenora 0.01, Nipissing 0.01, TroutLake 0.01/

    basePrice(p)         "Base price ($/m3)"
                         /CLT 700, Glulam 575, Lumber 375, Pulpwood 75/

    yieldFactor(p)       "Output per unit of primary raw-material input"
                         /CLT 0.82, Glulam 0.85, Lumber 0.90, Pulpwood 0.98/

    lumberInputPerUnit(p) "m3 lumber required per m3 product"
                         /CLT 1.20, Glulam 1.10, Lumber 0, Pulpwood 0/

    baseProcessingCost(m) "Base processing cost by layer ($/m3 output)"
                          /Primary 100, Secondary 50/

    productMarkup(p)      "Additional product-specific processing cost ($/m3 output)"
                          /CLT 150, Glulam 120, Lumber 20, Pulpwood -80/

    processingCost_y(p, y) "Processing cost over time ($/m3 output)"
    basePrice_y(p, y)      "Exogenous price path ($/m3)"
    demandCap_y(r,p,y)     "Max final demand served (MILLION m3/year)"
    baseDemand(r,p)        "Base final demand cap (MILLION m3/year)"
    cpValue(cpScen)        "Carbon price by scenario ($/tCO2)"
    demandCapBase(r,p,y)   "Stored baseline demand cap"
    demandShock(r,p,y)     "Stochastic demand multiplier by region/product/year"
    basePricePath(p,y)     "Frozen reference price path (before scenario shocks)";

cpValue('cp0')   = 0;
cpValue('cp50')  = 50;
cpValue('cp100') = 100;
cpValue('cp170') = 170;
cpValue('cp250') = 250;
cpValue('cp350') = 350;
cpValue('cp500') = 500;

* Processing cost: NO fake embedded lumber cost here
processingCost_y(p, y) =
    (
      (baseProcessingCost('Primary')   + productMarkup(p))$(manufacturingTier(p)=1)
    + (baseProcessingCost('Secondary') + productMarkup(p))$(manufacturingTier(p)=2)
    ) * power(0.98, ord(y)-1);

* Exogenous product prices grow 3% annually
basePrice_y(p, y) = basePrice(p) * power(1.03, ord(y)-1);

baseDemand(r,p) = 0;

* ---------------------------------------------------------------------------
* Demand sized to regional sustainable harvest proxy (Mm3/yr ≈ 1% of stock).
* Shares leave headroom so D50–D400 multipliers still raise demTableQty
* (else MT plateaus and higher-D scenarios are pointless).
* ---------------------------------------------------------------------------
PARAMETER sustHarvestProxy(r) "Approx max annual harvest Mm3/yr (1% of stock)";
sustHarvestProxy(r) = maxHarvestRate(r) * initStockRW(r);

baseDemand(r,'Lumber')   = 0.20 * sustHarvestProxy(r) * yieldFactor('Lumber');
baseDemand(r,'Pulpwood') = 0.08 * sustHarvestProxy(r) * yieldFactor('Pulpwood');

baseDemand(r,'CLT')    = 0.035 * sustHarvestProxy(r)
                         * yieldFactor('Lumber') / lumberInputPerUnit('CLT');
baseDemand(r,'Glulam') = 0.030 * sustHarvestProxy(r)
                         * yieldFactor('Lumber') / lumberInputPerUnit('Glulam');

* Stochastic demand shock (market, policy) - makes harvestRW vary by year/region
* Range ~0.88 to 1.12. Use --seed=N for reproducibility.
LOOP((r,p,y),
    demandShock(r,p,y) = uniform(0.88, 1.12);
);
demandCap_y(r,p,y) = baseDemand(r,p) * power(1 + demandGrowth, ord(y)-1) * demandShock(r,p,y);
demandCapBase(r,p,y) = demandCap_y(r,p,y);
* Reference price path for price / coupled sensitivity (lumber shock only unless noted)
basePricePath(p,y) = basePrice_y(p,y);

* Demand-change multipliers — MT only (lumber pull OFF so D200–D400 still vary)
SCALAR demLumberPullShare "Share of MT demand growth that expands lumber final demand" /0.0/;
PARAMETER demDemandMult(demScen,p) "Multiplier on demandCap for demand scenarios";
demDemandMult(demScen,p) = 1;
demDemandMult('Baseline','CLT') = 1.00;  demDemandMult('Baseline','Glulam') = 1.00;
demDemandMult('D50','CLT')      = 1.50;  demDemandMult('D50','Glulam')      = 1.50;
demDemandMult('D100','CLT')     = 2.00;  demDemandMult('D100','Glulam')     = 2.00;
demDemandMult('D200','CLT')     = 3.00;  demDemandMult('D200','Glulam')     = 3.00;
demDemandMult('D300','CLT')     = 4.00;  demDemandMult('D300','Glulam')     = 4.00;
demDemandMult('D400','CLT')     = 5.00;  demDemandMult('D400','Glulam')     = 5.00;
demDemandMult('DU10','CLT')     = 1.10;  demDemandMult('DU10','Glulam')     = 1.10;
demDemandMult(demScen,'Lumber') =
    1 + demLumberPullShare * (demDemandMult(demScen,'CLT') - 1);
demDemandMult(demScen,'Pulpwood') = 1;

DISPLAY sustHarvestProxy, baseDemand, demDemandMult, demLumberPullShare;

* Lumber price multipliers (exogenous path for Lumber only; other products unchanged)
PARAMETER prLumberMult(prScen) "Multiplier on basePricePath for Lumber";
prLumberMult(prScen) = 1;
prLumberMult('Pbase') = 1.00;
prLumberMult('PD5')   = 0.95;
prLumberMult('PI5')   = 1.05;
prLumberMult('PD10')  = 0.90;
prLumberMult('PI10')  = 1.10;

* Coupled: MT demand (CLT/Glulam) + lumber price shock together
PARAMETER cmDemandMult(cmScen,p) "Demand cap multiplier for coupled runs"
          cmLumberMult(cmScen)   "Lumber price multiplier for coupled runs";
cmDemandMult(cmScen,p) = 1;
cmDemandMult('CM_D100_PD5','CLT')    = 2.00;
cmDemandMult('CM_D100_PD5','Glulam') = 2.00;
cmLumberMult('CM_D100_PD5')          = 0.95;
cmDemandMult('CM_D100_PI10','CLT')    = 2.00;
cmDemandMult('CM_D100_PI10','Glulam') = 2.00;
cmLumberMult('CM_D100_PI10')          = 1.10;
cmDemandMult('CM_D200_PD10','CLT')    = 3.00;
cmDemandMult('CM_D200_PD10','Glulam') = 3.00;
cmLumberMult('CM_D200_PD10')          = 0.90;
cmDemandMult(cmScen,'Lumber') =
    1 + demLumberPullShare * (cmDemandMult(cmScen,'CLT') - 1);
cmDemandMult(cmScen,'Pulpwood') = 1;

* =========================================================================
* 5. TRANSPORT / LOGISTICS
* =========================================================================
TABLE transportBase(r,rr) "Transport cost proxy ($/m3)"
                TroutLake Abitibi Algoma Kenora Nipissing Algonquin
    TroutLake       0        38      42     100      14         9
    Abitibi        26         0      35      75      25        32
    Algoma         31        28       0      60      31        38
    Kenora         79        61      49       0      79        87
    Nipissing      14        27      31      79       0         8
    Algonquin       9        34      38      87       8         0;

PARAMETERS
    transportCost(r,rr,p)          "Transport cost by product ($/m3)"
    arcCap(r,rr,p,y)               "Arc capacity (MILLION m3/year) (shipments cannot exceed transport capacity)"
    millCap(r,p,y)                 "Mill output capacity (MILLION m3/year)"
    harvestCostRW                  "Harvest cost for roundwood ($/m3)"
    carbonEmissionFactor(p)        "Process emission factor (tCO2/m3 output)"
    carbonStorageFactor(p)         "Stored carbon factor (tCO2/m3 output)"
    transportEmissionFactor(r,rr,p) "Freight emission factor (tCO2/m3 shipped)";

transportCost(r,rr,p)$(not sameas(r,rr)) = transportBase(r,rr);

* Placeholder capacities: will be replace with real data when available
arcCap(r,rr,p,y)$(not sameas(r,rr)) = 20;

millCap(r,'Lumber',y)   = 10;
millCap(r,'Pulpwood',y) = 10;
* Sized so D400 MT demand (x5 on baseline) is not mill-capacity constrained
millCap(r,'CLT',y)      = 2.5;
millCap(r,'Glulam',y)   = 2.5;

harvestCostRW = 38;
harvestCost_y(r,y) = harvestCostRW * harvestCostShock(r,y);

carbonEmissionFactor('CLT')      = 0.15;
carbonEmissionFactor('Glulam')   = 0.17;
carbonEmissionFactor('Lumber')   = 0.065;
carbonEmissionFactor('Pulpwood') = 0.01;

carbonStorageFactor('CLT')      = 0.7;
carbonStorageFactor('Glulam')   = 0.7;
carbonStorageFactor('Lumber')   = 0.4;
carbonStorageFactor('Pulpwood') = 0.07;

transportEmissionFactor(r,rr,p)$(not sameas(r,rr)) = 0.018;

* =========================================================================
* 6. VARIABLES
* =========================================================================
POSITIVE VARIABLES
    stockRW(r,y)          "Roundwood stock (MILLION m3)"
    harvestRW(r,y)        "Roundwood harvest (MILLION m3)"
    production(r,p,y)     "Output production (MILLION m3)"
    sales(r,p,y)          "Final sales / served demand (MILLION m3)"
    exports(r,rr,p,y)     "Interregional shipments (MILLION m3)"
    price(r,p,y)          "Price variable fixed to exogenous path ($/m3)"
    carbonStorage(r,p,y)  "Stored carbon (MtCO2 eq if factors are tCO2/m3 and quantities in million m3)"
    carbonEmission(r,p,y) "Emissions (MtCO2 eq)";

VARIABLES
    Zprofit        "Net economic value before carbon cost (MILLION $)"
    Zemission      "Total carbon emissions (MtCO2 eq)"
    Zstorage       "Total stored carbon (MtCO2 eq)"
    ZnetCarbon     "Net carbon = emissions - storage (MtCO2 eq)"
    carbonCost     "Carbon cost (MILLION $)"
    obj            "Objective = Zprofit - carbonCost (MILLION $)"
    revenue        "Revenue (MILLION $)"
    harvestCostTot "Harvest cost (MILLION $)"
    procCostTot    "Processing cost (MILLION $)"
    transCostTot   "Transport cost (MILLION $)";

* =========================================================================
* 7. EQUATIONS
* =========================================================================
EQUATIONS
    stockBalanceRW(r,y)
    sustainabilityRW(r,y)
    roundwoodUseEq(r,y)
    millCapacityEq(r,p,y)
    demandCapEq(r,p,y)
    arcCapEq(r,rr,p,y)
    lumberBalance(r,y)
    pulpwoodBalance(r,y)
    cltBalance(r,y)
    glulamBalance(r,y)
    carbonStoreEq(r,p,y)
    carbonEmitEq(r,p,y)
    emissionEq
    storageEq
    netCarbonEq
    eCarbonCost
    revenueEq
    harvestCostEq
    procCostEq
    transCostEq
    profitEq
    scalarObjective;

stockBalanceRW(r,y)..
    stockRW(r,y) =E=
          (initStockRW(r) - harvestRW(r,y))$(ord(y)=1)
        + (stockRW(r,y-1) + growthRW(r,y) - harvestRW(r,y))$(ord(y)>1);

* Active only when useHarvestCeiling=1. Demand scenarios set this to 0 so
* harvest/MT can track demDemandMult; stockBalanceRW and stockRW.lo still bind.
sustainabilityRW(r,y)$useHarvestCeiling..
    harvestRW(r,y) =L=
          maxHarvestRate(r) * initStockRW(r)$(ord(y)=1)
        + maxHarvestRate(r) * (stockRW(r,y-1) + growthRW(r,y))$(ord(y)>1);

* Roundwood can only feed primary processing (Lumber + Pulpwood)
roundwoodUseEq(r,y)..
      production(r,'Lumber',y)   / yieldFactor('Lumber')
    + production(r,'Pulpwood',y) / yieldFactor('Pulpwood')
    =L= harvestRW(r,y);

millCapacityEq(r,p,y)..
    production(r,p,y) =L= millCap(r,p,y);

demandCapEq(r,p,y)..
    sales(r,p,y) =L= demandCap_y(r,p,y);

arcCapEq(r,rr,p,y)$(not sameas(r,rr))..
    exports(r,rr,p,y) =L= arcCap(r,rr,p,y);

* Lumber balance: final lumber sales + lumber shipments + lumber used in CLT/Glulam
lumberBalance(r,y)..
      production(r,'Lumber',y)
    + sum(rr$(not sameas(r,rr)), exports(rr,r,'Lumber',y))
    =E=
      sales(r,'Lumber',y)
    + sum(rr$(not sameas(r,rr)), exports(r,rr,'Lumber',y))
    + lumberInputPerUnit('CLT')    * production(r,'CLT',y)
    + lumberInputPerUnit('Glulam') * production(r,'Glulam',y);

pulpwoodBalance(r,y)..
      production(r,'Pulpwood',y)
    + sum(rr$(not sameas(r,rr)), exports(rr,r,'Pulpwood',y))
    =E=
      sales(r,'Pulpwood',y)
    + sum(rr$(not sameas(r,rr)), exports(r,rr,'Pulpwood',y));

cltBalance(r,y)..
      production(r,'CLT',y)
    + sum(rr$(not sameas(r,rr)), exports(rr,r,'CLT',y))
    =E=
      sales(r,'CLT',y)
    + sum(rr$(not sameas(r,rr)), exports(r,rr,'CLT',y));

glulamBalance(r,y)..
      production(r,'Glulam',y)
    + sum(rr$(not sameas(r,rr)), exports(rr,r,'Glulam',y))
    =E=
      sales(r,'Glulam',y)
    + sum(rr$(not sameas(r,rr)), exports(r,rr,'Glulam',y));

carbonStoreEq(r,p,y)..
    carbonStorage(r,p,y) =E= carbonStorageFactor(p) * production(r,p,y);

carbonEmitEq(r,p,y)..
    carbonEmission(r,p,y) =E=
        carbonEmissionFactor(p) * production(r,p,y)
      + sum(rr$(not sameas(r,rr)), transportEmissionFactor(r,rr,p) * exports(r,rr,p,y));

emissionEq..
    Zemission =E= sum((r,p,y), carbonEmission(r,p,y));

storageEq..
    Zstorage =E= sum((r,p,y), carbonStorage(r,p,y));

netCarbonEq..
    ZnetCarbon =E= Zemission - Zstorage;

* Carbon charge on gross emissions only (ZnetCarbon still available for reporting)
eCarbonCost..
    carbonCost =E= carbonPrice * Zemission;

revenueEq..
    revenue =E= sum((r,p,y), price(r,p,y) * sales(r,p,y));

harvestCostEq..
    harvestCostTot =E= sum((r,y), harvestCost_y(r,y) * harvestRW(r,y));

procCostEq..
    procCostTot =E= sum((r,p,y), processingCost_y(p,y) * production(r,p,y));

transCostEq..
    transCostTot =E= sum((r,rr,p,y)$(not sameas(r,rr)), transportCost(r,rr,p) * exports(r,rr,p,y));

profitEq..
    Zprofit =E= revenue - harvestCostTot - procCostTot - transCostTot;

scalarObjective..
    obj =E= Zprofit - carbonCost;

* =========================================================================
* 8. BOUNDS / FIXED PRICES / INITIAL LEVELS
* =========================================================================
* Fix prices to the exogenous 3% growth path
price.fx(r,p,y) = basePrice_y(p,y);

* No within-region shipments
exports.fx(r,r,p,y) = 0;

* Soft stock floor (30% of initial from 2025) — room for high-D MT expansion
stockRW.lo(r,y)$(y.val >= 2025) = 0.30 * initStockRW(r);

* Starting levels
stockRW.l(r,y)      = initStockRW(r);
harvestRW.l(r,y)    = maxHarvestRate(r) * initStockRW(r);
production.l(r,p,y) = 0.25 * demandCap_y(r,p,y);
sales.l(r,p,y)      = 0.25 * demandCap_y(r,p,y);
exports.l(r,rr,p,y)$(not sameas(r,rr)) = 0;

* =========================================================================
* 9. MODEL AND SOLVE
* =========================================================================
MODEL ForestCP /
    stockBalanceRW, sustainabilityRW, roundwoodUseEq,
    millCapacityEq, demandCapEq, arcCapEq,
    lumberBalance, pulpwoodBalance, cltBalance, glulamBalance,
    carbonStoreEq, carbonEmitEq,
    emissionEq, storageEq, netCarbonEq, eCarbonCost,
    revenueEq, harvestCostEq, procCostEq, transCostEq,
    profitEq, scalarObjective
/;

SOLVE ForestCP USING NLP MAXIMIZING obj;

* =========================================================================
* 10. REPORTING
* =========================================================================
PARAMETER
    tierMetrics(r,m,met,y)      "Manufacturing layer metrics"
    productChainCost(p,comp,y)  "Product cost breakdown"
    revRPY(r,p,y)               "Revenue by region/product/year (MILLION $)"
    revR(r)                     "Total revenue by region (MILLION $)"
    rev2025(r)                  "Revenue by region in 2025 (MILLION $)"
    sensSummary(cpScen,outMet)  "Carbon-price sensitivity summary"
    sensForPlot(cpScen,*)       "Chart-ready carbon sensitivity table"
    sensBase(outMet)            "Carbon sensitivity baseline values at cp170"
    sensDelta(cpScen,outMet,chgMet) "Carbon sensitivity delta vs cp170"
    demSummary(demScen,outMet)    "Demand-scenario full metrics (at reference carbon price)"
    demForChart(demScen,demCol)   "Chart-ready demand sensitivity (D50-style labels)"
    demSensBase(outMet)           "Demand sensitivity baseline = Baseline demScen"
    demSensDelta(demScen,outMet,chgMet) "Demand delta vs Baseline demScen"
    demTableQty(demScen,r) "Mass timber CLT+Glulam, sum over years (1000 m3)"
    demTableRev(demScen,r) "Direct output CLT+Glulam sales revenue, sum over years (MILLION $)"
    demObj(demScen)       "Objective after each demand scenario (MILLION $)"
    demTotQty(demScen)    "Total mass-timber qty all regions (1000 m3)"
    demTotRev(demScen)    "Total CLT+Glulam revenue all regions (MILLION $)"
    demForPlot(demScen,*) "Compact demand-sensitivity table for DISPLAY"
    prTableQty(prScen,r)  "Price sens: mass timber qty sum years (1000 m3)"
    prTableRev(prScen,r)   "Price sens: CLT+Glulam revenue sum years (MILLION $)"
    prObj(prScen)          "Price sens: objective (MILLION $)"
    prTotQty(prScen)       "Price sens: total MT qty all regions (1000 m3)"
    prTotRev(prScen)       "Price sens: total MT rev (MILLION $)"
    prForPlot(prScen,*)    "Compact price-sensitivity table"
    cmTableQty(cmScen,r)   "Coupled: mass timber qty (1000 m3)"
    cmTableRev(cmScen,r)   "Coupled: CLT+Glulam rev (MILLION $)"
    cmObj(cmScen)          "Coupled: objective (MILLION $)"
    cmTotQty(cmScen)       "Coupled: total MT qty (1000 m3)"
    cmTotRev(cmScen)       "Coupled: total MT rev (MILLION $)"
    cmForPlot(cmScen,*)    "Compact coupled-sensitivity table"
    pubSummaryTab(pubRow,tabSumCol)"Policy table"
    regionalHarvestDem(demScen,r,y) "Roundwood harvest M m3/yr by demand scenario (D50..), region, year — filled in SS10b loop; MNR harvest response to MT demand shocks";

tierMetrics(r,m,'Production',y) =
    sum(p$(manufacturingTier(p)=ord(m)), production.l(r,p,y));

tierMetrics(r,m,'Revenue',y) =
    sum(p$(manufacturingTier(p)=ord(m)), price.l(r,p,y) * sales.l(r,p,y));

tierMetrics(r,m,'ProcessingCost',y) =
    sum(p$(manufacturingTier(p)=ord(m)), processingCost_y(p,y) * production.l(r,p,y));

productChainCost(p,'BaseProcessing',y) =
      baseProcessingCost('Primary')$(manufacturingTier(p)=1)
    + baseProcessingCost('Secondary')$(manufacturingTier(p)=2);

productChainCost(p,'ProductMarkup',y) = productMarkup(p);
productChainCost(p,'LumberInputCost',y) = basePrice_y('Lumber',y) * lumberInputPerUnit(p);
productChainCost(p,'Total',y) = processingCost_y(p,y);

revRPY(r,p,y) = price.l(r,p,y) * sales.l(r,p,y);
revR(r)       = sum((p,y), revRPY(r,p,y));
rev2025(r)    = sum(p, revRPY(r,p,'2025'));

DISPLAY
    obj.l, Zprofit.l, Zemission.l, carbonCost.l,
    tierMetrics,
    price.l, stockRW.l, harvestRW.l, production.l, exports.l, sales.l,
    revenue.l, harvestCostTot.l, procCostTot.l, transCostTot.l,
    revR, rev2025, tierMetrics;

* =========================================================================
* 10b. DEMAND CHANGE — TABLE BY SIX REGIONS (mass timber qty + direct $)
*     MT demand multipliers only (lumber pull = 0); harvest ceiling OFF.
*     Expect demTableQty and TotalHarvest to rise Base → D400.
* =========================================================================
OPTION solprint=off, limrow=0, limcol=0;
carbonPrice = cpValue('cp170');
useHarvestCeiling = 0;
put_utility 'log' / '=== Starting demand sensitivity (demScen loop; harvest ceiling OFF) ===';
LOOP(demScen,
    demandCap_y(r,p,y) = demandCapBase(r,p,y) * demDemandMult(demScen,p);
    SOLVE ForestCP USING NLP MAXIMIZING obj;
    demObj(demScen) = obj.l;
    demTableQty(demScen,r) =
        sum(y, production.l(r,'CLT',y) + production.l(r,'Glulam',y)) * 1000;
    demTableRev(demScen,r) =
        sum(y, price.l(r,'CLT',y) * sales.l(r,'CLT',y)
              + price.l(r,'Glulam',y) * sales.l(r,'Glulam',y));
    demSummary(demScen,'Obj')             = obj.l;
    demSummary(demScen,'Zprofit')         = Zprofit.l;
    demSummary(demScen,'Zemission')       = Zemission.l;
    demSummary(demScen,'CarbonStorage')   = Zstorage.l;
    demSummary(demScen,'NetCarbon')       = ZnetCarbon.l;
    demSummary(demScen,'CarbonCost')      = carbonCost.l;
    demSummary(demScen,'Revenue')         = revenue.l;
    demSummary(demScen,'HarvestCost')     = harvestCostTot.l;
    demSummary(demScen,'ProcCost')        = procCostTot.l;
    demSummary(demScen,'TransCost')       = transCostTot.l;
    demSummary(demScen,'TotalHarvest')    = sum((r,y), harvestRW.l(r,y));
    demSummary(demScen,'TotalProduction') = sum((r,p,y), production.l(r,p,y));
    demSummary(demScen,'TotalSales')      = sum((r,p,y), sales.l(r,p,y));
    regionalHarvestDem(demScen,r,y)       = harvestRW.l(r,y);
);
useHarvestCeiling = 1;
demandCap_y(r,p,y) = demandCapBase(r,p,y);
put_utility 'log' / '=== Demand sensitivity done; harvest ceiling RESTORED ===';
* NetCarbon delta / % vs Baseline demand (same cp170); shows policy lever when primal is fixed under carbon tax
LOOP(demScen,
    demSummary(demScen,'NetCarbDel') = demSummary(demScen,'NetCarbon') - demSummary('Baseline','NetCarbon');
);
LOOP(demScen,
    demSummary(demScen,'NetCarbPct')$(abs(demSummary('Baseline','NetCarbon')) > 1e-6)
        = 100 * demSummary(demScen,'NetCarbDel') / abs(demSummary('Baseline','NetCarbon'));
);
demSummary(demScen,'NetCarbPct')$(abs(demSummary('Baseline','NetCarbon')) <= 1e-6) = 0;

demTotQty(demScen) = sum(r, demTableQty(demScen,r));
demTotRev(demScen) = sum(r, demTableRev(demScen,r));
demForPlot(demScen,'CLTmult')   = demDemandMult(demScen,'CLT');
demForPlot(demScen,'TotQty1k')  = demTotQty(demScen);
demForPlot(demScen,'TotRevM')   = demTotRev(demScen);
demForPlot(demScen,'Obj')       = demObj(demScen);

demForChart(demScen,'DemandMultiplierCLTGlulam') = demDemandMult(demScen,'CLT');
demForChart(demScen,'Obj')             = demSummary(demScen,'Obj');
demForChart(demScen,'Zprofit')         = demSummary(demScen,'Zprofit');
demForChart(demScen,'Zemission')       = demSummary(demScen,'Zemission');
demForChart(demScen,'CarbonCost')      = demSummary(demScen,'CarbonCost');
demForChart(demScen,'Revenue')         = demSummary(demScen,'Revenue');
demForChart(demScen,'HarvestCost')     = demSummary(demScen,'HarvestCost');
demForChart(demScen,'ProcCost')        = demSummary(demScen,'ProcCost');
demForChart(demScen,'TransCost')       = demSummary(demScen,'TransCost');
demForChart(demScen,'TotalHarvest')    = demSummary(demScen,'TotalHarvest');
demForChart(demScen,'TotalProduction') = demSummary(demScen,'TotalProduction');
demForChart(demScen,'TotalSales')      = demSummary(demScen,'TotalSales');

demSensBase(outMet) = demSummary('Baseline',outMet);
demSensDelta(demScen,outMet,'AbsChange') = demSummary(demScen,outMet) - demSensBase(outMet);
demSensDelta(demScen,outMet,'PctChange')$demSensBase(outMet) = 100 * demSensDelta(demScen,outMet,'AbsChange') / demSensBase(outMet);

put_utility 'log' / '=== Demand sensitivity: search .lst for demTableQty / demForPlot ===';
demandCap_y(r,p,y) = demandCapBase(r,p,y);
* Re-solve baseline so exports and carbon loop start from baseline levels
SOLVE ForestCP USING NLP MAXIMIZING obj;
tierMetrics(r,m,'Production',y) =
    sum(p$(manufacturingTier(p)=ord(m)), production.l(r,p,y));
tierMetrics(r,m,'Revenue',y) =
    sum(p$(manufacturingTier(p)=ord(m)), price.l(r,p,y) * sales.l(r,p,y));
tierMetrics(r,m,'ProcessingCost',y) =
    sum(p$(manufacturingTier(p)=ord(m)), processingCost_y(p,y) * production.l(r,p,y));
revRPY(r,p,y) = price.l(r,p,y) * sales.l(r,p,y);
revR(r)       = sum((p,y), revRPY(r,p,y));
rev2025(r)    = sum(p, revRPY(r,p,'2025'));

* =========================================================================
* 10b1. REGIONAL HARVEST BY YEAR — BY DEMAND SCENARIO (MNR / policy tables)
*     One matrix per demScen (Baseline, D50, D100, ...) from SS10b solves.
*     demandCap_y = demandCapBase * demDemandMult (MT demand shock); demandCapBase
*     embeds stochastic demandShock(r,p,y). Also harvestCostShock, growthShock.
*     carbonPrice = 170 throughout SS10b. Units: MILLION m3 per year (not cumulative).
* =========================================================================
DISPLAY regionalHarvestDem;

file hrvrep / 'output/regional_harvest_by_year_demand_scenarios.txt' /;
hrvrep.pc = 5;
hrvrep.nd = 12;
put hrvrep;
put 'Regional roundwood harvest by year — BY DEMAND SCENARIO (MILLION m3 per year)'/;
put 'Each block = equilibrium after solving with that demScen (CLT/Glulam cap multipliers)'/;
put 'Underlying caps: demandCapBase * demDemandMult; demandCapBase includes demandShock(r,p,y)'/;
put 'Other variability: harvestCostShock(r,y), growthShock(r,y). Carbon price = 170 $/tCO2.'/;
put 'Reproducibility: gams SA13.gms --seed=<integer>'/;
put /;
loop(demScen,
    put '=== Demand scenario: ' demScen.tl
        '  CLT mult ' demDemandMult(demScen,'CLT'):8:4 /;
    put 'Region':20;
    loop(y,
        put y.tl:10;
    );
    put /;
    loop(r,
        put r.tl:20;
        loop(y,
            put regionalHarvestDem(demScen,r,y):10:4;
        );
        put /;
    );
    put '  Horizon sum by region (M m3):'/;
    loop(r,
        put '    ' r.tl:18;
        put sum(y, regionalHarvestDem(demScen,r,y)):12:4 /;
    );
    put /;
);
putclose hrvrep;
put_utility 'log' / 'Wrote output/regional_harvest_by_year_demand_scenarios.txt';

file hrvcsv / 'output/regional_harvest_by_year_demand_scenarios_long.csv' /;
hrvcsv.pc = 5;
put hrvcsv;
put 'demScen,CLT_cap_mult,Region,Year,Harvest_Mm3_per_year'/;
loop(demScen,
    loop(r,
        loop(y,
            put demScen.tl;
            put ',';
            put demDemandMult(demScen,'CLT'):0:6;
            put ',';
            put r.tl;
            put ',';
            put y.tl;
            put ',';
            put regionalHarvestDem(demScen,r,y):0:8;
            put /;
        );
    );
);
putclose hrvcsv;
put_utility 'log' / 'Wrote output/regional_harvest_by_year_demand_scenarios_long.csv';

Execute_Unload "output/RegionalHarvestByYear.gdx", demScen, r, y, regionalHarvestDem, demDemandMult;
put_utility 'log' / 'Wrote output/RegionalHarvestByYear.gdx';

* One DISPLAY block — search .lst for "demTableQty", "demSummary", or "demForPlot"
DISPLAY demDemandMult, demForPlot, demTotQty, demTotRev, demObj, demTableQty, demTableRev;
DISPLAY demSummary, demForChart;
DISPLAY demSensBase, demSensDelta;

file demrep / 'output/demand_sensitivity_report.txt' /;
demrep.pc = 5;
demrep.nd = 12;
put demrep;
put 'Demand sensitivity - mass timber (CLT+Glulam), 6 regions, sum over years'/;
put 'Qty = 1000 m3 ; Rev = MILLION $'/;
put /;
loop(demScen,
    put 'Scenario: ' demScen.tl /;
    put '  CLT mult ' demDemandMult(demScen,'CLT'):12:4
        '  Obj ' demObj(demScen):12:4
        '  TotQty(1000m3) ' demTotQty(demScen):12:2
        '  TotRev(M$) ' demTotRev(demScen):12:4 /;
    loop(r,
        put '  ' r.tl:12
            ' Qty ' demTableQty(demScen,r):12:2
            ' Rev ' demTableRev(demScen,r):12:4 /;
    );
    put /;
);
putclose demrep;
put_utility 'log' / 'Wrote output/demand_sensitivity_report.txt';

Execute_Unload "output/DemandChangeByRegion.gdx",
    demScen, demDemandMult, demTableQty, demTableRev,
    demObj, demTotQty, demTotRev, demForPlot,
    demSummary, demForChart, demSensBase, demSensDelta,
    regionalHarvestDem;

* =========================================================================
* 10c. LUMBER PRICE SENSITIVITY — same regional MT table as demand block
* =========================================================================
put_utility 'log' / '=== Starting lumber price sensitivity (prScen) ===';
LOOP(prScen,
    demandCap_y(r,p,y) = demandCapBase(r,p,y);
    basePrice_y(p,y) = basePricePath(p,y);
    basePrice_y('Lumber',y) = basePricePath('Lumber',y) * prLumberMult(prScen);
    price.fx(r,p,y) = basePrice_y(p,y);
    SOLVE ForestCP USING NLP MAXIMIZING obj;
    prObj(prScen) = obj.l;
    prTableQty(prScen,r) =
        sum(y, production.l(r,'CLT',y) + production.l(r,'Glulam',y)) * 1000;
    prTableRev(prScen,r) =
        sum(y, price.l(r,'CLT',y) * sales.l(r,'CLT',y)
              + price.l(r,'Glulam',y) * sales.l(r,'Glulam',y));
);
prTotQty(prScen) = sum(r, prTableQty(prScen,r));
prTotRev(prScen) = sum(r, prTableRev(prScen,r));
prForPlot(prScen,'LumberMult') = prLumberMult(prScen);
prForPlot(prScen,'TotQty1k')   = prTotQty(prScen);
prForPlot(prScen,'TotRevM')    = prTotRev(prScen);
prForPlot(prScen,'Obj')        = prObj(prScen);
basePrice_y(p,y) = basePricePath(p,y);
price.fx(r,p,y) = basePrice_y(p,y);
demandCap_y(r,p,y) = demandCapBase(r,p,y);
SOLVE ForestCP USING NLP MAXIMIZING obj;
tierMetrics(r,m,'Production',y) =
    sum(p$(manufacturingTier(p)=ord(m)), production.l(r,p,y));
tierMetrics(r,m,'Revenue',y) =
    sum(p$(manufacturingTier(p)=ord(m)), price.l(r,p,y) * sales.l(r,p,y));
tierMetrics(r,m,'ProcessingCost',y) =
    sum(p$(manufacturingTier(p)=ord(m)), processingCost_y(p,y) * production.l(r,p,y));
revRPY(r,p,y) = price.l(r,p,y) * sales.l(r,p,y);
revR(r)       = sum((p,y), revRPY(r,p,y));
rev2025(r)    = sum(p, revRPY(r,p,'2025'));

DISPLAY prLumberMult, prForPlot, prTotQty, prTotRev, prObj, prTableQty, prTableRev;

file prrep / 'output/price_sensitivity_report.txt' /;
prrep.pc = 5;
prrep.nd = 12;
put prrep;
put 'Lumber price sensitivity - mass timber (CLT+Glulam), 6 regions, sum over years'/;
put 'Qty = 1000 m3 ; Rev = MILLION $ ; LumberMult = shock to lumber price path'/;
put /;
loop(prScen,
    put 'Scenario: ' prScen.tl /;
    put '  LumberMult ' prLumberMult(prScen):12:4
        '  Obj ' prObj(prScen):12:4
        '  TotQty(1000m3) ' prTotQty(prScen):12:2
        '  TotRev(M$) ' prTotRev(prScen):12:4 /;
    loop(r,
        put '  ' r.tl:12
            ' Qty ' prTableQty(prScen,r):12:2
            ' Rev ' prTableRev(prScen,r):12:4 /;
    );
    put /;
);
putclose prrep;
put_utility 'log' / 'Wrote output/price_sensitivity_report.txt';

Execute_Unload "output/PriceChangeByRegion.gdx",
    prScen, prLumberMult, prTableQty, prTableRev,
    prObj, prTotQty, prTotRev, prForPlot;

* =========================================================================
* 10d. COUPLED SENSITIVITY — MT demand shift + lumber price shock together
* =========================================================================
put_utility 'log' / '=== Starting coupled sensitivity (cmScen) ===';
LOOP(cmScen,
    demandCap_y(r,p,y) = demandCapBase(r,p,y) * cmDemandMult(cmScen,p);
    basePrice_y(p,y) = basePricePath(p,y);
    basePrice_y('Lumber',y) = basePricePath('Lumber',y) * cmLumberMult(cmScen);
    price.fx(r,p,y) = basePrice_y(p,y);
    SOLVE ForestCP USING NLP MAXIMIZING obj;
    cmObj(cmScen) = obj.l;
    cmTableQty(cmScen,r) =
        sum(y, production.l(r,'CLT',y) + production.l(r,'Glulam',y)) * 1000;
    cmTableRev(cmScen,r) =
        sum(y, price.l(r,'CLT',y) * sales.l(r,'CLT',y)
              + price.l(r,'Glulam',y) * sales.l(r,'Glulam',y));
);
cmTotQty(cmScen) = sum(r, cmTableQty(cmScen,r));
cmTotRev(cmScen) = sum(r, cmTableRev(cmScen,r));
cmForPlot(cmScen,'CLTmult')     = cmDemandMult(cmScen,'CLT');
cmForPlot(cmScen,'LumberMult')  = cmLumberMult(cmScen);
cmForPlot(cmScen,'TotQty1k')    = cmTotQty(cmScen);
cmForPlot(cmScen,'TotRevM')     = cmTotRev(cmScen);
cmForPlot(cmScen,'Obj')         = cmObj(cmScen);
demandCap_y(r,p,y) = demandCapBase(r,p,y);
basePrice_y(p,y) = basePricePath(p,y);
price.fx(r,p,y) = basePrice_y(p,y);
SOLVE ForestCP USING NLP MAXIMIZING obj;
tierMetrics(r,m,'Production',y) =
    sum(p$(manufacturingTier(p)=ord(m)), production.l(r,p,y));
tierMetrics(r,m,'Revenue',y) =
    sum(p$(manufacturingTier(p)=ord(m)), price.l(r,p,y) * sales.l(r,p,y));
tierMetrics(r,m,'ProcessingCost',y) =
    sum(p$(manufacturingTier(p)=ord(m)), processingCost_y(p,y) * production.l(r,p,y));
revRPY(r,p,y) = price.l(r,p,y) * sales.l(r,p,y);
revR(r)       = sum((p,y), revRPY(r,p,y));
rev2025(r)    = sum(p, revRPY(r,p,'2025'));

DISPLAY cmDemandMult, cmLumberMult, cmForPlot, cmTotQty, cmTotRev, cmObj, cmTableQty, cmTableRev;

file cmrep / 'output/coupled_sensitivity_report.txt' /;
cmrep.pc = 5;
cmrep.nd = 12;
put cmrep;
put 'Coupled sensitivity - MT demand (CLT+Glulam) x lumber price, 6 regions'/;
put /;
loop(cmScen,
    put 'Scenario: ' cmScen.tl /;
    put '  CLTdemMult ' cmDemandMult(cmScen,'CLT'):12:4
        '  LumberMult ' cmLumberMult(cmScen):12:4
        '  Obj ' cmObj(cmScen):12:4
        '  TotQty ' cmTotQty(cmScen):12:2
        '  TotRev ' cmTotRev(cmScen):12:4 /;
    loop(r,
        put '  ' r.tl:12
            ' Qty ' cmTableQty(cmScen,r):12:2
            ' Rev ' cmTableRev(cmScen,r):12:4 /;
    );
    put /;
);
putclose cmrep;
put_utility 'log' / 'Wrote output/coupled_sensitivity_report.txt';

Execute_Unload "output/CoupledSensitivityByRegion.gdx",
    cmScen, cmDemandMult, cmLumberMult, cmTableQty, cmTableRev,
    cmObj, cmTotQty, cmTotRev, cmForPlot;

* =========================================================================
* 11. EXPORTS
* =========================================================================
Execute_Unload "ForestResults.gdx",
    obj, Zprofit, Zemission, carbonCost,
    price, stockRW, harvestRW, production, exports, sales,
    revenue, harvestCostTot, procCostTot, transCostTot,
    revR, rev2025, tierMetrics;

Execute "gdx2csv ForestResults.gdx";

Execute_Unload "output/ForestResults.gdx",
    obj, Zprofit, Zemission, carbonCost,
    price, stockRW, harvestRW, production, exports, sales,
    revenue, harvestCostTot, procCostTot, transCostTot,
    revR, rev2025,CAI_Region, regionArea, tierMetrics;

Execute "gdx2csv output/ForestResults.gdx output=output/results_summary.csv";

* =========================================================================
* 12. CARBON PRICE SENSITIVITY
* =========================================================================
LOOP(cpScen,
    carbonPrice = cpValue(cpScen);
    SOLVE ForestCP USING NLP MAXIMIZING obj;

    sensSummary(cpScen,'Obj')             = obj.l;
    sensSummary(cpScen,'Zprofit')         = Zprofit.l;
    sensSummary(cpScen,'Zemission')       = Zemission.l;
    sensSummary(cpScen,'CarbonStorage')   = Zstorage.l;
    sensSummary(cpScen,'NetCarbon')       = ZnetCarbon.l;
    sensSummary(cpScen,'CarbonCost')      = carbonCost.l;
    sensSummary(cpScen,'Revenue')         = revenue.l;
    sensSummary(cpScen,'HarvestCost')     = harvestCostTot.l;
    sensSummary(cpScen,'ProcCost')        = procCostTot.l;
    sensSummary(cpScen,'TransCost')       = transCostTot.l;
    sensSummary(cpScen,'TotalHarvest')    = sum((r,y), harvestRW.l(r,y));
    sensSummary(cpScen,'TotalProduction') = sum((r,p,y), production.l(r,p,y));
    sensSummary(cpScen,'TotalSales')      = sum((r,p,y), sales.l(r,p,y));
);
* NetCarbon delta / % vs cp170 — shows emissions/storage components move with Obj even when NetCarbon is unchanged
LOOP(cpScen,
    sensSummary(cpScen,'NetCarbDel') = sensSummary(cpScen,'NetCarbon') - sensSummary('cp170','NetCarbon');
);
LOOP(cpScen,
    sensSummary(cpScen,'NetCarbPct')$(abs(sensSummary('cp170','NetCarbon')) > 1e-6)
        = 100 * sensSummary(cpScen,'NetCarbDel') / abs(sensSummary('cp170','NetCarbon'));
);
sensSummary(cpScen,'NetCarbPct')$(abs(sensSummary('cp170','NetCarbon')) <= 1e-6) = 0;

sensForPlot(cpScen,'CarbonPrice')     = cpValue(cpScen);
sensForPlot(cpScen,'Obj')             = sensSummary(cpScen,'Obj');
sensForPlot(cpScen,'Zprofit')         = sensSummary(cpScen,'Zprofit');
sensForPlot(cpScen,'Zemission')       = sensSummary(cpScen,'Zemission');
sensForPlot(cpScen,'CarbonCost')      = sensSummary(cpScen,'CarbonCost');
sensForPlot(cpScen,'Revenue')         = sensSummary(cpScen,'Revenue');
sensForPlot(cpScen,'HarvestCost')     = sensSummary(cpScen,'HarvestCost');
sensForPlot(cpScen,'ProcCost')        = sensSummary(cpScen,'ProcCost');
sensForPlot(cpScen,'TransCost')       = sensSummary(cpScen,'TransCost');
sensForPlot(cpScen,'TotalHarvest')    = sensSummary(cpScen,'TotalHarvest');
sensForPlot(cpScen,'TotalProduction') = sensSummary(cpScen,'TotalProduction');
sensForPlot(cpScen,'TotalSales')      = sensSummary(cpScen,'TotalSales');

sensBase(outMet) = sensSummary('cp170',outMet);
sensDelta(cpScen,outMet,'AbsChange') = sensSummary(cpScen,outMet) - sensBase(outMet);
sensDelta(cpScen,outMet,'PctChange')$sensBase(outMet) = 100 * sensDelta(cpScen,outMet,'AbsChange') / sensBase(outMet);

DISPLAY cpValue, sensSummary, sensForPlot;
DISPLAY sensBase, sensDelta;

* =========================================================================
* 13. PUBLICATION SUMMARY TABLE -> LaTeX rows + CSV (Obj, emissions, storage, net C, deltas, harvest)
* =========================================================================
pubSummaryTab(pubRow, tabSumCol) = 0;
LOOP((pubRow, cpScen)$pubCarbRow(pubRow, cpScen),
    pubSummaryTab(pubRow, tabSumCol) = sensSummary(cpScen, tabSumCol);
);
LOOP((pubRow, demScen)$pubDemRow(pubRow, demScen),
    pubSummaryTab(pubRow, tabSumCol) = demSummary(demScen, tabSumCol);
);

DISPLAY pubSummaryTab;

file fltx / 'output/summary_table_body.tex' /;
fltx.pc = 5;
put fltx;
put '% Auto-generated from SA13.gms — paste inside tabular after \midrule'/;
put '% Cols: Obj; Zemission; CarbonStorage (Zstorage); NetCarbon; $\Delta$NetC \& \% vs cp170 (carb) or Baseline (dem); TotHarvest'/;
put '% NetCarbon (Mt) = Zemission$-$Zstorage (narrow product/transport accounting).'/;
put '% --- Carbon price scenarios (cpScen); baseline demand caps ---'/;
LOOP((pubRow, cpScen)$pubCarbRow(pubRow, cpScen),
    put 'Carbon price ';
    put cpScen.tl;
    put ' (\$/tCO2) & ';
    put pubSummaryTab(pubRow, 'Obj'):0:2;
    put ' & ';
    put pubSummaryTab(pubRow, 'Zemission'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'CarbonStorage'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'NetCarbon'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'NetCarbDel'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'NetCarbPct'):0:2;
    put ' & ';
    put pubSummaryTab(pubRow, 'TotalHarvest'):0:2;
    put ' ';
    put '\';
    put '\';
    put /;
);
put '% --- Demand scenarios (demScen); carbon price = 170 \$/tCO2 (see \S10b) ---'/;
LOOP((pubRow, demScen)$pubDemRow(pubRow, demScen),
    put 'Demand ';
    put demScen.tl;
    put ' (MT cap mult.) & ';
    put pubSummaryTab(pubRow, 'Obj'):0:2;
    put ' & ';
    put pubSummaryTab(pubRow, 'Zemission'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'CarbonStorage'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'NetCarbon'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'NetCarbDel'):0:3;
    put ' & ';
    put pubSummaryTab(pubRow, 'NetCarbPct'):0:2;
    put ' & ';
    put pubSummaryTab(pubRow, 'TotalHarvest'):0:2;
    put ' ';
    put '\';
    put '\';
    put /;
);
putclose fltx;

file fcsv / 'output/summary_public_table.csv' /;
fcsv.pc = 5;
put fcsv;
put 'Block,Scenario,Obj_MUSD,Zemission_Mt,CarbonStorage_Mt,NetCarbon_Mt,NetCarbDelta_Mt,NetCarbPct_vs_ref,TotalHarvest_Mm3'/;
put '_NOTE,Horizon_totals_sum_r_y_NetCarbDelta_Pct_carbon_rows_vs_cp170_demand_rows_vs_Baseline_see_GAMS_sec13'/;
LOOP((pubRow, cpScen)$pubCarbRow(pubRow, cpScen),
    put 'Carbon,';
    put cpScen.tl;
    put ',';
    put pubSummaryTab(pubRow, 'Obj'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'Zemission'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'CarbonStorage'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'NetCarbon'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'NetCarbDel'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'NetCarbPct'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'TotalHarvest'):0:4;
    put /;
);
LOOP((pubRow, demScen)$pubDemRow(pubRow, demScen),
    put 'Demand,';
    put demScen.tl;
    put ',';
    put pubSummaryTab(pubRow, 'Obj'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'Zemission'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'CarbonStorage'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'NetCarbon'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'NetCarbDel'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'NetCarbPct'):0:4;
    put ',';
    put pubSummaryTab(pubRow, 'TotalHarvest'):0:4;
    put /;
);
putclose fcsv;
put_utility 'log' / 'Wrote output/summary_table_body.tex and output/summary_public_table.csv';

OPTION solprint=on;

Execute_Unload "output/SensitivityResults.gdx",
    cpValue, sensSummary, sensForPlot,
    sensBase, sensDelta,
    demDemandMult, demSummary, demForChart, demSensBase, demSensDelta,
    demTableQty, demTableRev,
    demObj, demTotQty, demTotRev, demForPlot,
    prLumberMult, prTableQty, prTableRev, prObj, prTotQty, prTotRev, prForPlot,
    cmDemandMult, cmLumberMult, cmTableQty, cmTableRev,
    cmObj, cmTotQty, cmTotRev, cmForPlot,
    pubSummaryTab,
    regionalHarvestDem;

Execute_Unload "output/PublicSummaryTable.gdx",
    pubRow, pubCarbRow, pubDemRow, tabSumCol, pubSummaryTab;
Execute "gdx2csv output/PublicSummaryTable.gdx output=output/summary_public_table_from_gdx.csv";

Execute "gdx2csv output/SensitivityResults.gdx output=output/sensitivity_results.csv";

$log Corrected roundwood-based model finished. Prices were fixed to basePrice_y to prevent artificial endogenous drift.