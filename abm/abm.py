"""FORBIOM-ABM: agent-based model of forest biomass utilization in six Ontario FMU regions.

Companion to FORBIOM-ON (GAMS spatial optimization, Activity 2). Regions, carbon factors and the
CLT/glulam lumber-input ratios follow FORBIOM-ON; fibre supply (LTMD) and current harvest are
calibrated to ARWoodS 2019-2024; employment intensities to eFAR 2020-2022 (see calibrate.py).

Agents
  FMUManager      one per region; releases available Crown volume (LTMD x disturbance), allocates fibre
  Contractor      harvest/haul enterprises (Indigenous-owned or other); logistic supply response
  Plant           incumbent mills and new entrants (mass-timber hubs, urban CLT plants, community
                  log-to-panel "spokes", community bioheat, pellet plants); logistic utilization and
                  investment decisions under bounded rationality and adaptive price expectations
  Markets         southern Ontario mass-timber and prefab-panel demand, northern community housing,
                  community heat demand, export pellets, commodity lumber/OSB
Time step: one year, 2026-2045.
"""
from __future__ import annotations

import copy
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent

REGIONS = ["TroutLake", "Abitibi", "Algoma", "Kenora", "Nipissing", "Algonquin"]
FIBRES = ["SW", "PO", "HW"]
YEARS = list(range(2026, 2046))
ODT_PER_M3 = 0.42

# Approximate FMU centroids (lat, lon); road distance = great-circle x circuity factor
COORDS = {
    "TroutLake": (50.60, -92.30), "Abitibi": (49.30, -81.00), "Algoma": (46.90, -83.90),
    "Kenora": (50.00, -94.30), "Nipissing": (46.60, -79.60), "Algonquin": (45.70, -78.40),
    "GTA": (43.70, -79.42),
}
PORTS = {"ThunderBay": (48.38, -89.25), "Montreal": (45.50, -73.57)}
CIRCUITY = 1.3


def road_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h)) * CIRCUITY


DIST_GTA = {r: road_km(COORDS[r], COORDS["GTA"]) for r in REGIONS}
DIST_PORT = {r: min(road_km(COORDS[r], p) for p in PORTS.values()) for r in REGIONS}


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-40.0, min(40.0, x))))


def crf(rate: float, years: int) -> float:
    return rate / (1 - (1 + rate) ** -years)


# ---------------------------------------------------------------------------------------------
# Parameters (2026 CAD, real). "src" notes in report Appendix A.
# ---------------------------------------------------------------------------------------------
BASE_PARAMS: dict = {
    "prices": {  # reference levels
        "lumber": 300.0,        # SPF mill-net $/m3
        "mt": 1100.0,           # CLT/glulam $/m3 FOB plant, southern Ontario market
        "panel": 1300.0,        # prefab wall/floor panel, $/m3 wood-equivalent
        "osb": 400.0,           # OSB/composite $/m3
        "hw_lumber": 750.0,     # hardwood lumber $/m3
        "pulpwood": 70.0,       # pulp-grade roundwood value at mill $/m3
        "residue": 30.0,        # mill residue $/odt
        "pellet": 230.0,        # industrial pellets $/odt FOB plant (before freight to port)
    },
    "price_vol": {"lumber": 0.15, "mt": 0.06, "panel": 0.05, "osb": 0.15, "pellet": 0.10, "fuel": 0.10},
    "price_rho": 0.6,
    "mt_elasticity": 1.5,
    "freight_product": 0.07,     # $/m3-km finished product (truck)
    "freight_log": 0.12,         # $/m3-km logs
    "freight_rail_odt": 0.04,    # $/odt-km pellets (rail)
    "harvest_cost": 38.0,        # $/m3 stump-to-roadside (FORBIOM-ON harvestCostRW)
    "lowgrade_cost_mult": 1.10,
    "inregion_haul_km": 110.0,
    "stumpage": 6.0,
    "access": {"TroutLake": 1.10, "Abitibi": 1.00, "Algoma": 1.10, "Kenora": 1.15, "Nipissing": 1.00, "Algonquin": 1.05},
    "forest_residue_odt_per_m3": 0.12,
    "forest_residue_cost": 45.0,  # $/odt recovery + grinding
    "mill_residue_absorbed": 0.60,  # share of mill residues already used by pulp/composite/cogeneration
    "discount": 0.08, "life": 20,
    "wage": 70000.0,
    # technologies -------------------------------------------------------------------------
    "tech": {
        "inc_SW": {"lrf": 0.55, "conv": 150.0, "res_frac": 0.40, "jobs": 0.363 + 0.045},
        "inc_PO": {"yield": 0.62, "conv": 270.0, "res_frac": 0.10, "jobs": 0.356 + 0.007},
        "inc_HW": {"saw_share": 0.25, "lrf": 0.50, "conv": 350.0, "pulp_handling": 15.0, "jobs": 0.60},
        "mt_hub": {"log_cap": 150000.0, "lrf": 0.55, "conv": 150.0, "res_frac": 0.40, "mt_cap": 60000.0,
                    "lumber_per_mt": 1.20, "mt_conv": 250.0, "capex": 150e6,
                    "jobs_saw": 0.363 + 0.045, "jobs_mt": 1.6},
        "mt_urban": {"mt_cap": 60000.0, "lumber_per_mt": 1.20, "mt_conv": 250.0, "capex": 100e6,
                      "lumber_haul_km": 700.0, "jobs_mt": 1.6},
        "spoke": {"log_cap": 25000.0, "lrf": 0.50, "conv": 190.0, "res_frac": 0.42, "panel_cap": 10000.0,
                   "lumber_per_panel": 1.15, "panel_conv": 550.0, "capex": 25e6, "jobs_saw": 0.8, "jobs_panel": 5.0},
        "bioheat": {"cap_odt": 5000.0, "opex": 60.0, "chip": 10.0, "capex": 12e6, "jobs": 1.5},
        "pellet": {"cap_odt": 80000.0, "opex": 75.0, "chip": 10.0, "capex": 50e6, "jobs": 0.6},
    },
    "learning_rate": 0.10, "learning_n0": 2.0,
    "max_per_region": {"mt_hub": 2, "mt_urban": 3, "spoke": 3, "bioheat": 4, "pellet": 1},
    "build_lag": 2,
    "ramp": [0.5, 0.8],
    # behaviour -----------------------------------------------------------------------------
    "k_contractor": 12.0, "z_contractor": -1.0,
    "k_mill": 4.0, "z_mill": -1.0,
    "k_invest": 5.0, "z_invest": 1.0, "p_invest_max": 0.6,
    "expect_alpha": 0.3,
    "price_adj": 0.30,
    "exit_years": 3, "p_exit": 0.4,
    "contractor_slack": 1.25, "n_contractors": 10,
    "p_contractor_expand": 0.5, "contractor_expand": 0.15,
    "fire_prob": 0.06, "fire_loss": (0.10, 0.30), "supply_noise": 0.05,
    # demand --------------------------------------------------------------------------------
    "mt_demand0": 165000.0,      # FORBIOM-ON baseline CLT+glulam demand caps, six regions (m3/yr)
    "panel_demand0": 60000.0,
    "demand_growth": 0.08,
    "north_housing_units": {"TroutLake": 150, "Abitibi": 120, "Algoma": 60, "Kenora": 120, "Nipissing": 50, "Algonquin": 40},
    "m3_per_unit": 35.0, "north_housing_growth": 0.02,
    "heat_demand_odt": {"TroutLake": 10000, "Abitibi": 9000, "Algoma": 5000, "Kenora": 8000, "Nipissing": 4000, "Algonquin": 3000},
    "heat_value_odt": {"TroutLake": 600, "Abitibi": 550, "Algoma": 350, "Kenora": 450, "Nipissing": 250, "Algonquin": 300},
    # Indigenous and community ------------------------------------------------------------
    "ind_labour_share": {"TroutLake": 0.30, "Abitibi": 0.18, "Algoma": 0.15, "Kenora": 0.35, "Nipissing": 0.14, "Algonquin": 0.08},
    "ind_contractor_share": {"TroutLake": 0.20, "Abitibi": 0.15, "Algoma": 0.10, "Kenora": 0.35, "Nipissing": 0.10, "Algonquin": 0.10},
    "ind_owned_hire_share": 0.60,
    "ind_partner_hire_bonus": 0.15,
    "ind_contractor_workforce": 0.80,
    "contractor_jobs": 0.40,       # FTE per 1,000 m3 harvested and hauled
    # carbon (tCO2e) ------------------------------------------------------------------------
    "c_store": {"lumber": 0.40, "mt": 0.70, "panel": 0.70, "osb": 0.55, "pulp": 0.07},
    "c_process": {"lumber": 0.065, "mt": 0.15, "panel": 0.12, "osb": 0.20, "pulp": 0.01, "pellet_odt": 0.05},
    "c_freight": 0.00005,          # tCO2 per m3-km
    "c_harvest": 0.012,            # tCO2 per m3 harvested
    "c_fossil_heat_odt": 1.23,     # tCO2 avoided per odt replacing heating oil/diesel
}

STRATEGIES: dict = {
    "S0": {"name": "Business as usual", "techs": {}},
    "S1": {"name": "Southern urban mass-timber plants", "techs": {"mt_urban": ["GTA"]},
           "grant": {"mt_urban": 0.0}, "equity": {"mt_urban": 0.0}},
    "S2": {"name": "Northern integrated log-to-mass-timber hubs", "techs": {"mt_hub": REGIONS},
           "grant": {"mt_hub": 0.15}, "equity": {"mt_hub": 0.20}},
    "S3": {"name": "Distributed Indigenous/community network", "techs": {"spoke": REGIONS, "bioheat": REGIONS},
           "grant": {"spoke": 0.40, "bioheat": 0.50}, "equity": {"spoke": 0.51, "bioheat": 0.51},
           "capacity_building": True},
    "S4": {"name": "Hub-and-spoke hybrid", "techs": {"mt_hub": REGIONS, "spoke": REGIONS, "bioheat": REGIONS, "pellet": REGIONS},
           "grant": {"mt_hub": 0.15, "spoke": 0.40, "bioheat": 0.50, "pellet": 0.10},
           "equity": {"mt_hub": 0.20, "spoke": 0.51, "bioheat": 0.51, "pellet": 0.20}},
    "S5": {"name": "Hub-and-spoke hybrid + enabling policy", "techs": {"mt_hub": REGIONS, "spoke": REGIONS, "bioheat": REGIONS, "pellet": REGIONS},
           "grant": {"mt_hub": 0.15, "spoke": 0.40, "bioheat": 0.50, "pellet": 0.10},
           "equity": {"mt_hub": 0.20, "spoke": 0.51, "bioheat": 0.51, "pellet": 0.20},
           "capacity_building": True, "ind_priority": True, "procurement": 0.25, "clean_heat_incentive": 50.0},
}


def load_calibration() -> pd.DataFrame:
    return pd.read_csv(HERE / "calibration" / "regions.csv").set_index("region").loc[REGIONS]


# ---------------------------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------------------------
@dataclass
class Contractor:
    region: str
    capacity: float
    cost_mult: float
    indigenous: bool
    sold: float = 0.0
    revenue: float = 0.0
    cost: float = 0.0


@dataclass
class Plant:
    pid: int
    tech: str
    region: str
    scale: float = 1.0
    equity_ind: float = 0.0
    capex_net: float = 0.0
    grant_paid: float = 0.0
    online_year: int = 0
    incumbent: bool = False
    fibre: str | None = None
    base_cap: float = 0.0
    cost_mult: float = 1.0
    active: bool = True
    loss_years: int = 0
    age: int = 0
    desired: dict = field(default_factory=dict)
    intake: dict = field(default_factory=dict)
    feed_odt: float = 0.0
    out: dict = field(default_factory=dict)
    profit: float = 0.0
    cum_profit: float = 0.0
    jobs: float = 0.0


class FMUManager:
    def __init__(self, region: str, ltmd: dict[str, float]):
        self.region = region
        self.ltmd = ltmd
        self.available: dict[str, float] = dict(ltmd)

    def release(self, rng: np.random.Generator, p: dict) -> None:
        loss = rng.uniform(*p["fire_loss"]) if rng.random() < p["fire_prob"] else 0.0
        noise = rng.normal(1.0, p["supply_noise"])
        for f in FIBRES:
            self.available[f] = max(0.0, self.ltmd[f] * (1 - loss) * noise)


# ---------------------------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------------------------
class BiomassABM:
    def __init__(self, strategy: str | dict = "S0", seed: int = 0, overrides: dict | None = None,
                 cal: pd.DataFrame | None = None):
        self.p = copy.deepcopy(BASE_PARAMS)
        for k, v in (overrides or {}).items():
            if isinstance(v, dict) and isinstance(self.p.get(k), dict):
                self.p[k].update(v)
            else:
                self.p[k] = v
        self.s = STRATEGIES[strategy] if isinstance(strategy, str) else strategy
        self.seed = seed
        self.rng = np.random.default_rng(seed)  # environment stream: prices, disturbance, initial agents
        self.cal = load_calibration() if cal is None else cal
        self.fmu = {r: FMUManager(r, {f: float(self.cal.loc[r, f"LTMD_{f}"]) for f in FIBRES}) for r in REGIONS}
        self.year = YEARS[0]
        self.t = 0
        self.plants: list[Plant] = []
        self.contractors: list[Contractor] = []
        self.pid = 0
        self.built_count = {k: 0 for k in self.p["tech"]}
        self.records: list[dict] = []
        self.plant_records: list[dict] = []
        self.public_cost = 0.0
        self.public_cost_region = {r: 0.0 for r in REGIONS + ["GTA"]}
        self._init_prices()
        self._init_agents()

    # -- prices ---------------------------------------------------------------------------
    def _init_prices(self) -> None:
        pr = self.p["prices"]
        self.shock = {k: 0.0 for k in self.p["price_vol"]}
        self.P = dict(pr)
        self.Pexp = dict(pr)
        self.heat_mult = 1.0
        self.w = {}
        for r in REGIONS:
            for f in FIBRES:
                self.w[(r, f)] = self._contractor_unit_cost(r, f, 1.0) * 1.10
        self.wexp = dict(self.w)

    def _draw_prices(self) -> None:
        p, rng, rho = self.p, self.rng, self.p["price_rho"]
        z_l = rng.normal()
        corr = {"lumber": 1.0, "mt": 0.4, "panel": 0.3, "osb": 0.6, "pellet": 0.0, "fuel": 0.0}
        for k, vol in p["price_vol"].items():
            z = corr[k] * z_l + math.sqrt(1 - corr[k] ** 2) * rng.normal()
            self.shock[k] = rho * self.shock[k] + math.sqrt(1 - rho ** 2) * vol * z
        pr = p["prices"]
        self.P["lumber"] = pr["lumber"] * math.exp(self.shock["lumber"])
        self.P["osb"] = pr["osb"] * math.exp(self.shock["osb"])
        self.P["pellet"] = pr["pellet"] * math.exp(self.shock["pellet"])
        self.P["mt_ref"] = pr["mt"] * math.exp(self.shock["mt"])
        self.P["panel_ref"] = pr["panel"] * math.exp(self.shock["panel"])
        self.heat_mult = math.exp(self.shock["fuel"])

    def _update_expectations(self) -> None:
        a = self.p["expect_alpha"]
        for k in ("lumber", "osb", "pellet"):
            self.Pexp[k] += a * (self.P[k] - self.Pexp[k])
        self.Pexp["mt"] += a * (self.P["mt"] - self.Pexp["mt"])
        self.Pexp["panel"] += a * (self.P["panel"] - self.Pexp["panel"])
        for key in self.w:
            self.wexp[key] += a * (self.w[key] - self.wexp[key])

    # -- agent set-up ---------------------------------------------------------------------
    def _contractor_unit_cost(self, r: str, f: str, mult: float) -> float:
        p = self.p
        base = p["harvest_cost"] * p["access"][r] * mult
        if f != "SW":
            base *= p["lowgrade_cost_mult"]
        return base + p["freight_log"] * p["inregion_haul_km"] + p["stumpage"]

    def _u(self, *key: int) -> float:
        """Keyed uniform draw: identical across strategies for the same decision (common random numbers)."""
        return float(np.random.default_rng([self.seed, *key]).random())

    def _new_pid(self) -> int:
        self.pid += 1
        return self.pid

    def _init_agents(self) -> None:
        p, rng = self.p, self.rng
        for r in REGIONS:
            act = {f: float(self.cal.loc[r, f"ACT_{f}"]) for f in FIBRES}
            total_cap = sum(act.values()) * p["contractor_slack"]
            n = p["n_contractors"]
            ind_share = p["ind_contractor_share"][r]
            n_ind = max(1, round(n * ind_share))
            weights = rng.dirichlet(np.ones(n) * 3)
            for i in range(n):
                self.contractors.append(Contractor(
                    region=r, capacity=total_cap * weights[i], cost_mult=float(rng.lognormal(0, 0.08)),
                    indigenous=i < n_ind))
            # incumbent mills: three agents per region-fibre, capacity calibrated so the year-0
            # desired intake equals observed 2019-2024 harvest
            for f in FIBRES:
                if act[f] <= 1000:
                    continue
                shares = [0.5, 0.3, 0.2]
                for s in shares:
                    pl = Plant(pid=self._new_pid(), tech=f"inc_{f}", region=r, incumbent=True, fibre=f,
                               cost_mult=float(rng.lognormal(0, 0.05)), equity_ind=0.0)
                    v = self._value_per_m3(pl, self.Pexp)
                    w0 = self.w[(r, f)]
                    u0 = sigmoid(p["k_mill"] * (v - w0) / w0 - p["z_mill"])
                    pl.base_cap = act[f] * s / max(u0, 0.05)
                    pl.online_year = YEARS[0] - 10
                    self.plants.append(pl)

    # -- unit economics -------------------------------------------------------------------
    def _lumber_value(self, pl: Plant, P: dict) -> float:
        """Net value of one m3 of lumber produced by a hub/spoke (into MT/panels or commodity)."""
        tp = self.p["tech"][pl.tech]
        if pl.tech == "mt_hub":
            fr = self.p["freight_product"] * DIST_GTA[pl.region]
            mt_val = (P["mt"] - tp["mt_conv"] - fr) / tp["lumber_per_mt"]
            return max(mt_val, P["lumber"])
        if pl.tech == "spoke":
            local_val = (P["panel"] - tp["panel_conv"] - self.p["freight_product"] * 100) / tp["lumber_per_panel"]
            south_val = (P["panel"] - tp["panel_conv"] - self.p["freight_product"] * DIST_GTA[pl.region]) / tp["lumber_per_panel"]
            share_local = self._local_panel_share(pl.region)
            return max(share_local * local_val + (1 - share_local) * south_val, P["lumber"])
        return P["lumber"]

    def _local_panel_share(self, r: str) -> float:
        dem = self._north_housing_m3(r)
        cap = sum(self.p["tech"]["spoke"]["panel_cap"] for q in self.plants
                  if q.tech == "spoke" and q.region == r and q.active)
        return min(1.0, dem / cap) if cap > 0 else 1.0

    def _value_per_m3(self, pl: Plant, P: dict, f: str | None = None) -> float:
        """Willingness to pay for one m3 roundwood of fibre f at the mill gate."""
        p = self.p
        tp = p["tech"][pl.tech]
        res_val = P.get("residue", p["prices"]["residue"]) * p["mill_residue_absorbed"]
        if pl.tech == "inc_SW":
            return tp["lrf"] * (P["lumber"] - tp["conv"] * pl.cost_mult) + tp["res_frac"] * ODT_PER_M3 * res_val
        if pl.tech == "inc_PO":
            return tp["yield"] * (P["osb"] - tp["conv"] * pl.cost_mult) + tp["res_frac"] * ODT_PER_M3 * res_val
        if pl.tech == "inc_HW":
            saw = tp["saw_share"] * tp["lrf"] * (p["prices"]["hw_lumber"] * P["lumber"] / p["prices"]["lumber"] - tp["conv"])
            return saw + (1 - tp["saw_share"]) * (p["prices"]["pulpwood"] - tp["pulp_handling"])
        if pl.tech in ("mt_hub", "spoke"):
            return tp["lrf"] * (self._lumber_value(pl, P) - tp["conv"]) + tp["res_frac"] * ODT_PER_M3 * res_val
        if pl.tech in ("bioheat", "pellet"):
            return max(0.0, self._value_per_odt(pl, P) - tp["chip"]) * ODT_PER_M3
        return 0.0

    def _value_per_odt(self, pl: Plant, P: dict) -> float:
        p = self.p
        tp = p["tech"][pl.tech]
        if pl.tech == "bioheat":
            incentive = self.s.get("clean_heat_incentive", 0.0) * p["c_fossil_heat_odt"]
            return p["heat_value_odt"][pl.region] * self.heat_mult + incentive - tp["opex"]
        if pl.tech == "pellet":
            return P["pellet"] - p["freight_rail_odt"] * DIST_PORT[pl.region] - tp["opex"]
        return 0.0

    def _capacity(self, pl: Plant) -> float:
        tp = self.p["tech"][pl.tech]
        if pl.incumbent:
            return pl.base_cap
        ramp = self.p["ramp"]
        k = self.year - pl.online_year
        r = ramp[k] if 0 <= k < len(ramp) else 1.0
        if pl.tech in ("mt_hub", "spoke"):
            return tp["log_cap"] * r
        if pl.tech == "mt_urban":
            return tp["mt_cap"] * r
        return tp["cap_odt"] * r

    def _north_housing_m3(self, r: str) -> float:
        p = self.p
        return p["north_housing_units"][r] * p["m3_per_unit"] * (1 + p["north_housing_growth"]) ** self.t

    def _south_demand(self, kind: str) -> float:
        p = self.p
        base = p["mt_demand0"] if kind == "mt" else p["panel_demand0"]
        return base * (1 + p["demand_growth"]) ** self.t * (1 + self.s.get("procurement", 0.0))

    # -- annual step ----------------------------------------------------------------------
    def step(self) -> None:
        p = self.p
        self._draw_prices()
        for r in REGIONS:
            self.fmu[r].release(self.rng, p)
        active = [q for q in self.plants if q.active and q.online_year <= self.year]
        for q in active:
            q.intake = {f: 0.0 for f in FIBRES}
            q.out, q.feed_odt, q.profit, q.jobs = {}, 0.0, 0.0, 0.0
        for c in self.contractors:
            c.sold = c.revenue = c.cost = 0.0

        # 1. plants decide desired roundwood intake from expected margins
        for q in active:
            q.desired = {}
            if q.tech == "mt_urban":
                continue
            cap = self._capacity(q)
            if q.incumbent:
                fibres = [q.fibre]
            elif q.tech in ("mt_hub", "spoke"):
                fibres = ["SW"]
            else:
                fibres = ["PO", "HW"]
            for f in fibres:
                v = self._value_per_m3(q, self.Pexp, f)
                w = self.wexp[(q.region, f)]
                u = sigmoid(p["k_mill"] * (v - w) / w - p["z_mill"])
                if q.tech in ("bioheat", "pellet"):
                    need_odt = self._bio_roundwood_need(q, cap)
                    q.desired[f] = need_odt / ODT_PER_M3 / len(fibres) * u
                else:
                    q.desired[f] = cap * u

        # 2. fibre markets clear region by region; contractors split effort across fibres by demand
        for r in REGIONS:
            dem = {f: sum(q.desired.get(f, 0.0) for q in active if q.region == r) for f in FIBRES}
            tot = sum(dem.values())
            for f in FIBRES:
                effort = dem[f] / tot if tot > 0 else 0.0
                self._clear_fibre_market(r, f, active, effort)

        # 3. production, residues, bioenergy, product markets
        self._produce(active)
        self._accounting(active)
        self._invest()
        self._contractor_dynamics()
        self._update_expectations()
        self.year += 1
        self.t += 1

    def _bio_roundwood_need(self, q: Plant, cap_odt: float) -> float:
        if q.tech == "bioheat":
            cap_odt = min(cap_odt, self._heat_headroom(q))
        res = self._residue_pool_estimate(q.region) / max(1, self._n_bio(q.region))
        return max(0.0, cap_odt - res)

    def _heat_headroom(self, q: Plant) -> float:
        others = [x for x in self.plants if x.tech == "bioheat" and x.region == q.region and x.active
                  and x.online_year <= self.year and x.pid < q.pid]
        used = sum(self._capacity(x) for x in others)
        return max(0.0, self.p["heat_demand_odt"][q.region] - used)

    def _n_bio(self, r: str) -> int:
        return sum(1 for x in self.plants if x.tech in ("bioheat", "pellet") and x.region == r and x.active
                   and x.online_year <= self.year)

    def _residue_pool_estimate(self, r: str) -> float:
        last = getattr(self, "_residue_last", {}).get(r)
        if last is not None:
            return last
        act = sum(float(self.cal.loc[r, f"ACT_{f}"]) for f in FIBRES)
        return act * (0.40 * ODT_PER_M3 * (1 - self.p["mill_residue_absorbed"]) + self.p["forest_residue_odt_per_m3"])

    def _clear_fibre_market(self, r: str, f: str, active: list[Plant], effort: float) -> None:
        p = self.p
        buyers = [q for q in active if q.region == r and q.desired.get(f, 0.0) > 0]
        D = sum(q.desired[f] for q in buyers)
        w = self.w[(r, f)]
        offers = []
        for c in (c for c in self.contractors if c.region == r):
            cost = self._contractor_unit_cost(r, f, c.cost_mult)
            o = c.capacity * effort * sigmoid(p["k_contractor"] * (w - cost) / cost - p["z_contractor"])
            offers.append((c, o, cost))
        S_offer = sum(o for _, o, _ in offers)
        S = min(S_offer, self.fmu[r].available[f])
        Q = min(D, S)

        # allocation to buyers (licence holders first; Indigenous-majority entrants first under priority)
        if D > 0:
            def group(q: Plant) -> int:
                if self.s.get("ind_priority") and q.equity_ind >= 0.5:
                    return 0
                return 1 if q.incumbent else 2
            remaining = Q
            for g in (0, 1, 2):
                grp = [q for q in buyers if group(q) == g]
                d = sum(q.desired[f] for q in grp)
                if d <= 0:
                    continue
                give = min(remaining, d)
                for q in grp:
                    q.intake[f] += give * q.desired[f] / d
                remaining -= give

        # allocation to contractors (Indigenous contractors first under priority)
        if S_offer > 0 and Q > 0:
            if self.s.get("ind_priority"):
                ind = [(c, o, k) for c, o, k in offers if c.indigenous]
                oth = [(c, o, k) for c, o, k in offers if not c.indigenous]
                q_ind = min(Q, sum(o for _, o, _ in ind))
                parts = [(ind, q_ind), (oth, Q - q_ind)]
            else:
                parts = [(offers, Q)]
            for grp, qty in parts:
                tot = sum(o for _, o, _ in grp)
                if tot <= 0:
                    continue
                for c, o, cost in grp:
                    v = qty * o / tot
                    c.sold += v
                    c.revenue += v * w
                    c.cost += v * cost

        # price adjustment toward market balance
        excess = (D - S) / max(S, 1.0)
        w_new = w * (1 + p["price_adj"] * max(-0.5, min(0.5, excess)))
        floor = 0.9 * min((k for _, _, k in offers), default=w)
        ceiling = max((self._value_per_m3(q, self.P, f) for q in buyers), default=w * 1.5)
        self.w[(r, f)] = max(floor, min(max(ceiling, floor), w_new))
        self._tx_price = getattr(self, "_tx_price", {})
        self._tx_price[(r, f)] = w

    def _produce(self, active: list[Plant]) -> None:
        p = self.p
        tech = p["tech"]
        residues_mill = {r: 0.0 for r in REGIONS + ["GTA"]}
        harvest = {r: 0.0 for r in REGIONS + ["GTA"]}
        for q in active:
            vol = sum(q.intake.values())
            harvest[q.region] += vol
            if q.tech in ("inc_SW", "mt_hub", "spoke"):
                tp = tech[q.tech]
                q.out["lumber"] = vol * tp["lrf"]
                q.out["res_odt"] = vol * tp["res_frac"] * ODT_PER_M3
                residues_mill[q.region] += q.out["res_odt"]
            elif q.tech == "inc_PO":
                q.out["osb"] = vol * tech["inc_PO"]["yield"]
                q.out["res_odt"] = vol * tech["inc_PO"]["res_frac"] * ODT_PER_M3
                residues_mill[q.region] += q.out["res_odt"]
            elif q.tech == "inc_HW":
                tp = tech["inc_HW"]
                q.out["lumber_hw"] = vol * tp["saw_share"] * tp["lrf"]
                q.out["pulp"] = vol * (1 - tp["saw_share"])

        # mass timber: hubs convert own lumber, urban plants buy lumber
        for q in active:
            if q.tech == "mt_hub":
                tp = tech["mt_hub"]
                mt_cap = tp["mt_cap"] * self._capacity(q) / tp["log_cap"]
                q.out["mt"] = min(q.out["lumber"] / tp["lumber_per_mt"], mt_cap)
                q.out["lumber"] -= q.out["mt"] * tp["lumber_per_mt"]
            elif q.tech == "mt_urban":
                tp = tech["mt_urban"]
                lumber_cost = (self.Pexp["lumber"] + p["freight_product"] * tp["lumber_haul_km"]) * tp["lumber_per_mt"]
                m = (self.Pexp["mt"] - tp["mt_conv"] - lumber_cost) / max(lumber_cost, 1.0)
                q.out["mt"] = self._capacity(q) * sigmoid(p["k_mill"] * m - p["z_mill"])
                q.out["lumber_bought"] = q.out["mt"] * tp["lumber_per_mt"]
            elif q.tech == "spoke":
                tp = tech["spoke"]
                panel_cap = tp["panel_cap"] * self._capacity(q) / tp["log_cap"]
                q.out["panel"] = min(q.out["lumber"] / tp["lumber_per_panel"], panel_cap)
                q.out["lumber"] -= q.out["panel"] * tp["lumber_per_panel"]

        # southern mass-timber market clears on price
        mt_supply = sum(q.out.get("mt", 0.0) for q in active)
        D_mt = self._south_demand("mt")
        eps = p["mt_elasticity"]
        self.P["mt"] = self.P["mt_ref"] * (min(1.0, D_mt / mt_supply) ** (1 / eps) if mt_supply > 0 else 1.0)
        self.mt_sold = min(mt_supply, D_mt * (self.P["mt_ref"] / self.P["mt"]) ** eps) if mt_supply > 0 else 0.0

        # panels: local northern housing first, remainder to southern market
        south_panel = 0.0
        for r in REGIONS:
            spokes = [q for q in active if q.tech == "spoke" and q.region == r]
            tot = sum(q.out["panel"] for q in spokes)
            local = min(tot, self._north_housing_m3(r))
            for q in spokes:
                share = q.out["panel"] / tot if tot > 0 else 0.0
                q.out["panel_local"] = local * share
                q.out["panel_south"] = q.out["panel"] - q.out["panel_local"]
                south_panel += q.out["panel_south"]
        D_pan = self._south_demand("panel")
        self.P["panel"] = self.P["panel_ref"] * (min(1.0, D_pan / south_panel) ** (1 / eps) if south_panel > 0 else 1.0)

        # residues and bioenergy feedstock
        self._residue_last = {}
        self.residue_stats = {}
        for r in REGIONS:
            mill_surplus = residues_mill[r] * (1 - p["mill_residue_absorbed"])
            forest_res = harvest[r] * p["forest_residue_odt_per_m3"]
            self._residue_last[r] = mill_surplus + forest_res
            bios = sorted([q for q in active if q.tech in ("bioheat", "pellet") and q.region == r],
                          key=lambda x: (x.tech != "bioheat", x.pid))
            mill_left, forest_left = mill_surplus, forest_res
            for q in bios:
                cap = self._capacity(q)
                if q.tech == "bioheat":
                    cap = min(cap, self._heat_headroom(q))
                rw_odt = sum(q.intake.values()) * ODT_PER_M3
                need = max(0.0, cap - rw_odt)
                from_mill = min(need, mill_left)
                mill_left -= from_mill
                need -= from_mill
                from_forest = min(need, forest_left)
                forest_left -= from_forest
                q.out["feed_mill"], q.out["feed_forest"], q.out["feed_rw"] = from_mill, from_forest, rw_odt
                q.feed_odt = from_mill + from_forest + rw_odt
            self.residue_stats[r] = {"mill_res_odt": residues_mill[r], "mill_surplus_odt": mill_surplus,
                                     "mill_surplus_used": mill_surplus - mill_left,
                                     "forest_res_avail": forest_res, "forest_res_used": forest_res - forest_left}

    def _accounting(self, active: list[Plant]) -> None:
        p, tech = self.p, self.p["tech"]
        fr = p["freight_product"]
        cr = crf(p["discount"], p["life"])
        mt_scale = self.mt_sold / max(1e-9, sum(q.out.get("mt", 0.0) for q in active))
        res_price = p["prices"]["residue"]
        for q in active:
            fibre_cost = sum(q.intake[f] * self._tx_price.get((q.region, f), 0.0) for f in FIBRES)
            rev = cost = 0.0
            jobs = 0.0
            vol = sum(q.intake.values())
            if q.tech == "inc_SW":
                tp = tech["inc_SW"]
                rev = q.out["lumber"] * self.P["lumber"] + q.out["res_odt"] * res_price * p["mill_residue_absorbed"]
                cost = q.out["lumber"] * tp["conv"] * q.cost_mult
                jobs = vol / 1000 * tp["jobs"]
            elif q.tech == "inc_PO":
                tp = tech["inc_PO"]
                rev = q.out["osb"] * self.P["osb"] + q.out["res_odt"] * res_price * p["mill_residue_absorbed"]
                cost = q.out["osb"] * tp["conv"] * q.cost_mult
                jobs = vol / 1000 * tp["jobs"]
            elif q.tech == "inc_HW":
                tp = tech["inc_HW"]
                hw_price = p["prices"]["hw_lumber"] * self.P["lumber"] / p["prices"]["lumber"]
                rev = q.out["lumber_hw"] * hw_price + q.out["pulp"] * p["prices"]["pulpwood"]
                cost = q.out["lumber_hw"] * tp["conv"] + q.out["pulp"] * tp["pulp_handling"]
                jobs = vol / 1000 * tp["jobs"]
            elif q.tech == "mt_hub":
                tp = tech["mt_hub"]
                sold = q.out["mt"] * mt_scale
                rev = (q.out["lumber"] * self.P["lumber"] + sold * (self.P["mt"] - fr * DIST_GTA[q.region])
                       + q.out["res_odt"] * res_price * p["mill_residue_absorbed"])
                cost = vol * tp["lrf"] * tp["conv"] + q.out["mt"] * tp["mt_conv"]
                jobs = vol / 1000 * tp["jobs_saw"] + q.out["mt"] / 1000 * tp["jobs_mt"]
            elif q.tech == "mt_urban":
                tp = tech["mt_urban"]
                sold = q.out["mt"] * mt_scale
                rev = sold * (self.P["mt"] - fr * 30)
                cost = q.out["mt"] * tp["mt_conv"] + q.out["lumber_bought"] * (self.P["lumber"] + fr * tp["lumber_haul_km"])
                jobs = q.out["mt"] / 1000 * tp["jobs_mt"]
            elif q.tech == "spoke":
                tp = tech["spoke"]
                rev = (q.out["lumber"] * self.P["lumber"]
                       + q.out["panel_local"] * (self.P["panel"] - fr * 100)
                       + q.out["panel_south"] * (self.P["panel"] - fr * DIST_GTA[q.region])
                       + q.out["res_odt"] * res_price * p["mill_residue_absorbed"])
                cost = vol * tp["lrf"] * tp["conv"] + q.out["panel"] * tp["panel_conv"]
                jobs = vol / 1000 * tp["jobs_saw"] + q.out["panel"] / 1000 * tp["jobs_panel"]
            elif q.tech in ("bioheat", "pellet"):
                tp = tech[q.tech]
                val = self._value_per_odt(q, self.P) + tp["opex"]
                rev = q.feed_odt * val
                feed_cost = (q.out["feed_mill"] * res_price
                             + q.out["feed_forest"] * (p["forest_residue_cost"] + 0.15 * 80))
                cost = q.feed_odt * tp["opex"] + feed_cost + q.out["feed_rw"] * tp["chip"]
                jobs = q.feed_odt / 1000 * tp["jobs"] + q.out["feed_forest"] / 1000 * 0.3
            capital = 0.0 if q.incumbent else q.capex_net * cr
            op = rev - cost - fibre_cost
            q.profit = op - capital
            q.cum_profit += q.profit
            q.jobs = jobs
            q.revenue = rev
            q.op_margin = op
            q.age += 1
            q.loss_years = q.loss_years + 1 if op < 0 else 0
            if q.loss_years >= p["exit_years"] and self._u(2, self.t, q.pid) < p["p_exit"]:
                q.active = False
        self._record(active)

    # -- investment -----------------------------------------------------------------------
    def _learning_mult(self, tech: str) -> float:
        b = -math.log2(1 - self.p["learning_rate"])
        n0 = self.p["learning_n0"]
        return ((self.built_count[tech] + n0) / n0) ** (-b)

    def _invest(self) -> None:
        p = self.p
        techs = self.s.get("techs", {})
        ann = 1 / crf(p["discount"], p["life"])
        for tech, locs in techs.items():
            for loc in locs:
                existing = [q for q in self.plants if q.tech == tech and q.region == loc and q.active]
                limit = self.s.get("max_override", {}).get(tech, {}).get(loc, p["max_per_region"][tech])
                if len(existing) >= limit:
                    continue
                cand = Plant(pid=-1, tech=tech, region=loc, equity_ind=self.s.get("equity", {}).get(tech, 0.0),
                             online_year=self.year + p["build_lag"])
                tp = p["tech"][tech]
                capex = tp["capex"] * self._learning_mult(tech)
                grant = self.s.get("grant", {}).get(tech, 0.0)
                capex_net = capex * (1 - grant)
                margin = self._expected_annual_margin(cand)
                if margin is None:
                    continue
                npv = margin * ann - capex_net
                prob = p["p_invest_max"] * sigmoid(p["k_invest"] * npv / capex_net - p["z_invest"])
                tech_i = list(p["tech"]).index(tech)
                loc_i = (REGIONS + ["GTA"]).index(loc)
                if self._u(3, self.t, tech_i, loc_i, len(existing)) < prob:
                    cand.pid = self._new_pid()
                    cand.capex_net = capex_net
                    cand.grant_paid = capex * grant
                    self.public_cost += capex * grant
                    self.public_cost_region[loc] += capex * grant
                    self.plants.append(cand)
                    self.built_count[tech] += 1

    def _expected_annual_margin(self, q: Plant) -> float | None:
        p, tp = self.p, self.p["tech"][q.tech]
        horizon_t = self.t + p["build_lag"] + 1
        if q.tech in ("mt_hub", "spoke"):
            committed = sum(self._full_cap(x).get("SW", 0.0) for x in self.plants
                            if x.region == q.region and x.active)
            free = self.fmu[q.region].ltmd["SW"] - committed
            if free < 0.7 * tp["log_cap"]:
                return None
            w = self.wexp[(q.region, "SW")]
            if q.tech == "mt_hub":
                dem = p["mt_demand0"] * (1 + p["demand_growth"]) ** horizon_t * (1 + self.s.get("procurement", 0.0))
                cap_mt = sum(p["tech"][x.tech]["mt_cap"] for x in self.plants if x.tech in ("mt_hub", "mt_urban") and x.active)
                share = max(0.0, min(1.0, (dem - cap_mt) / tp["mt_cap"]))
                if share < 0.4:
                    return None
                fr = p["freight_product"] * DIST_GTA[q.region]
                lumber = tp["log_cap"] * tp["lrf"]
                mt = tp["mt_cap"] * share
                rev = mt * (self.Pexp["mt"] - fr) + (lumber - mt * tp["lumber_per_mt"]) * self.Pexp["lumber"]
                cost = lumber * tp["conv"] + mt * tp["mt_conv"] + tp["log_cap"] * w
                return 0.9 * (rev - cost)
            local = self._north_housing_m3(q.region) * (1 + p["north_housing_growth"]) ** 3
            local_cap = sum(p["tech"]["spoke"]["panel_cap"] for x in self.plants
                            if x.tech == "spoke" and x.region == q.region and x.active)
            local_head = max(0.0, local - local_cap)
            dem_s = p["panel_demand0"] * (1 + p["demand_growth"]) ** horizon_t * (1 + self.s.get("procurement", 0.0))
            cap_s = sum(p["tech"]["spoke"]["panel_cap"] for x in self.plants if x.tech == "spoke" and x.active)
            south_head = max(0.0, dem_s + sum(self._north_housing_m3(r) for r in REGIONS) - cap_s)
            panels_local = min(tp["panel_cap"], local_head)
            panels_south = min(tp["panel_cap"] - panels_local, 0.5 * south_head)
            if panels_local + panels_south < 0.4 * tp["panel_cap"]:
                return None
            lumber = tp["log_cap"] * tp["lrf"]
            panels = panels_local + panels_south
            fr = p["freight_product"]
            rev = (panels_local * (self.Pexp["panel"] - fr * 100)
                   + panels_south * (self.Pexp["panel"] - fr * DIST_GTA[q.region])
                   + (lumber - panels * tp["lumber_per_panel"]) * self.Pexp["lumber"])
            cost = lumber * tp["conv"] + panels * tp["panel_conv"] + tp["log_cap"] * w
            return 0.9 * (rev - cost)
        if q.tech == "mt_urban":
            dem = p["mt_demand0"] * (1 + p["demand_growth"]) ** horizon_t * (1 + self.s.get("procurement", 0.0))
            cap_mt = sum(p["tech"][x.tech]["mt_cap"] for x in self.plants if x.tech in ("mt_hub", "mt_urban") and x.active)
            share = max(0.0, min(1.0, (dem - cap_mt) / tp["mt_cap"]))
            if share < 0.4:
                return None
            mt = tp["mt_cap"] * share
            lumber_cost = (self.Pexp["lumber"] + p["freight_product"] * tp["lumber_haul_km"]) * tp["lumber_per_mt"]
            return 0.9 * mt * (self.Pexp["mt"] - p["freight_product"] * 30 - tp["mt_conv"] - lumber_cost)
        if q.tech in ("bioheat", "pellet"):
            if q.tech == "bioheat":
                used = sum(p["tech"]["bioheat"]["cap_odt"] for x in self.plants
                           if x.tech == "bioheat" and x.region == q.region and x.active)
                head = p["heat_demand_odt"][q.region] - used
                if head < 0.6 * tp["cap_odt"]:
                    return None
                feed = min(tp["cap_odt"], head)
            else:
                feed = tp["cap_odt"]
            committed_lg = sum(self._full_cap(x).get("PO", 0.0) + self._full_cap(x).get("HW", 0.0)
                               for x in self.plants if x.region == q.region and x.active)
            free_lg = (self.fmu[q.region].ltmd["PO"] + self.fmu[q.region].ltmd["HW"] - committed_lg) * ODT_PER_M3
            res = self._residue_pool_estimate(q.region)
            if q.tech == "pellet" and free_lg + res < 0.8 * feed:
                return None
            w = 0.5 * (self.wexp[(q.region, "PO")] + self.wexp[(q.region, "HW")]) / ODT_PER_M3 + tp["chip"]
            res_use = min(feed, 0.5 * res)
            feed_cost = res_use * (p["prices"]["residue"] + 10) + (feed - res_use) * w
            val = self._value_per_odt(q, self.Pexp)
            return 0.9 * (feed * val - feed_cost)
        return None

    def _full_cap(self, q: Plant) -> dict:
        if q.incumbent:
            return {q.fibre: q.base_cap}
        tp = self.p["tech"][q.tech]
        if q.tech in ("mt_hub", "spoke"):
            return {"SW": tp["log_cap"]}
        if q.tech in ("bioheat", "pellet"):
            return {"PO": 0.25 * tp["cap_odt"] / ODT_PER_M3, "HW": 0.25 * tp["cap_odt"] / ODT_PER_M3}
        return {}

    def _contractor_dynamics(self) -> None:
        p = self.p
        boost = self.s.get("capacity_building", False)
        for ri, r in enumerate(REGIONS):
            cs = [c for c in self.contractors if c.region == r]
            for ci, c in enumerate(cs):
                util = c.sold / max(1.0, c.capacity)
                margin = (c.revenue - c.cost) / max(1.0, c.cost)
                pe = p["p_contractor_expand"] * (1.6 if (boost and c.indigenous) else 1.0)
                if util > 0.85 and margin > 0.05 and self._u(1, self.t, ri, ci) < min(0.95, pe):
                    c.capacity *= 1 + p["contractor_expand"]
            if boost and self.t < 5:
                # capacity-building programme: new Indigenous contractor capacity, 2% of LTMD per year
                add = 0.02 * sum(self.fmu[r].ltmd.values())
                cost_mult = float(np.exp(0.03 + 0.08 * np.random.default_rng([self.seed, 4, self.t, ri]).normal()))
                self.contractors.append(Contractor(region=r, capacity=add, cost_mult=cost_mult, indigenous=True))
                self.public_cost += add * 20.0
                self.public_cost_region[r] += add * 20.0

    # -- recording ------------------------------------------------------------------------
    def _record(self, active: list[Plant]) -> None:
        p = self.p
        wage = p["wage"]
        for r in list(REGIONS) + ["GTA"]:
            qs = [q for q in active if q.region == r]
            cs = [c for c in self.contractors if c.region == r]
            rec = {"year": self.year, "region": r}
            for f in FIBRES:
                rec[f"harvest_{f}"] = sum(q.intake.get(f, 0.0) for q in qs)
                rec[f"ltmd_{f}"] = self.fmu[r].ltmd[f] if r in self.fmu else 0.0
            rec["harvest"] = sum(rec[f"harvest_{f}"] for f in FIBRES)
            rec["ltmd"] = sum(rec[f"ltmd_{f}"] for f in FIBRES)
            rec["lumber"] = sum(q.out.get("lumber", 0.0) for q in qs)
            rec["mt"] = sum(q.out.get("mt", 0.0) for q in qs)
            rec["panel"] = sum(q.out.get("panel", 0.0) for q in qs)
            rec["panel_local"] = sum(q.out.get("panel_local", 0.0) for q in qs)
            rec["osb"] = sum(q.out.get("osb", 0.0) for q in qs)
            rec["pulp"] = sum(q.out.get("pulp", 0.0) for q in qs)
            rec["lumber_hw"] = sum(q.out.get("lumber_hw", 0.0) for q in qs)
            rec["bioheat_odt"] = sum(q.feed_odt for q in qs if q.tech == "bioheat")
            rec["pellet_odt"] = sum(q.feed_odt for q in qs if q.tech == "pellet")
            rs = self.residue_stats.get(r, {})
            for k, v in rs.items():
                rec[k] = v
            plant_jobs = sum(q.jobs for q in qs)
            harv_jobs = rec["harvest"] / 1000 * p["contractor_jobs"]
            rec["jobs"] = plant_jobs + harv_jobs
            ind_share = p["ind_labour_share"].get(r, 0.0)
            ind_jobs = 0.0
            for q in qs:
                if q.equity_ind >= 0.5:
                    s = max(ind_share, p["ind_owned_hire_share"])
                elif q.equity_ind > 0:
                    s = ind_share + p["ind_partner_hire_bonus"]
                else:
                    s = ind_share
                ind_jobs += q.jobs * s
            ind_sold = sum(c.sold for c in cs if c.indigenous)
            tot_sold = sum(c.sold for c in cs)
            ind_harv_jobs = harv_jobs * (ind_sold / tot_sold if tot_sold > 0 else 0.0)
            ind_jobs += ind_harv_jobs * p["ind_contractor_workforce"] + (harv_jobs - ind_harv_jobs) * ind_share
            rec["ind_jobs"] = ind_jobs
            rec["ind_contractor_vol"] = ind_sold
            rec["ind_equity_income"] = sum(q.equity_ind * q.profit for q in qs)
            rec["ind_contractor_margin"] = sum(c.revenue - c.cost for c in cs if c.indigenous)
            rec["ind_wages"] = ind_jobs * wage
            rec["ind_income"] = rec["ind_equity_income"] + rec["ind_contractor_margin"] + rec["ind_wages"]
            rec["plant_profit"] = sum(q.profit for q in qs)
            rec["contractor_margin"] = sum(c.revenue - c.cost for c in cs)
            rec["wages"] = rec["jobs"] * wage
            rec["value_added"] = rec["plant_profit"] + rec["contractor_margin"] + rec["wages"]
            rec["new_plant_losses"] = sum(min(0.0, q.profit) for q in qs if not q.incumbent)
            # carbon
            cs_, cp_ = p["c_store"], p["c_process"]
            store = (rec["lumber"] * cs_["lumber"] + rec["lumber_hw"] * cs_["lumber"] + rec["mt"] * cs_["mt"]
                     + rec["panel"] * cs_["panel"] + rec["osb"] * cs_["osb"] + rec["pulp"] * cs_["pulp"])
            proc = (rec["lumber"] * cp_["lumber"] + rec["mt"] * cp_["mt"] + rec["panel"] * cp_["panel"]
                    + rec["osb"] * cp_["osb"] + rec["pulp"] * cp_["pulp"] + rec["pellet_odt"] * cp_["pellet_odt"])
            dist = DIST_GTA.get(r, 30.0)
            freight = (rec["mt"] * dist + (rec["panel"] - rec["panel_local"]) * dist + rec["panel_local"] * 100) * p["c_freight"]
            freight += sum(q.out.get("lumber_bought", 0.0) for q in qs) * p["tech"]["mt_urban"]["lumber_haul_km"] * p["c_freight"]
            harv_em = rec["harvest"] * p["c_harvest"]
            avoided = rec["bioheat_odt"] * p["c_fossil_heat_odt"]
            rec["c_storage"], rec["c_emissions"], rec["c_avoided"] = store, proc + freight + harv_em, avoided
            rec["c_net_benefit"] = store + avoided - (proc + freight + harv_em)
            for tech in p["tech"]:
                rec[f"n_{tech}"] = sum(1 for q in self.plants if q.tech == tech and q.region == r and q.active
                                       and q.online_year <= self.year)
            rec["public_cost_cum"] = self.public_cost_region[r]
            rec["price_lumber"] = self.P["lumber"]
            rec["price_mt"] = self.P["mt"]
            rec["w_SW"] = self.w.get((r, "SW"), np.nan)
            rec["w_PO"] = self.w.get((r, "PO"), np.nan)
            rec["w_HW"] = self.w.get((r, "HW"), np.nan)
            self.records.append(rec)

    def run(self) -> pd.DataFrame:
        for _ in YEARS:
            self.step()
        return pd.DataFrame(self.records)

    def plant_summary(self) -> pd.DataFrame:
        rows = [{"pid": q.pid, "tech": q.tech, "region": q.region, "online_year": q.online_year,
                 "active": q.active, "equity_ind": q.equity_ind, "grant": q.grant_paid,
                 "capex_net": q.capex_net, "cum_profit": q.cum_profit}
                for q in self.plants if not q.incumbent]
        return pd.DataFrame(rows, columns=["pid", "tech", "region", "online_year", "active", "equity_ind",
                                           "grant", "capex_net", "cum_profit"])


if __name__ == "__main__":
    import time
    for s in STRATEGIES:
        t0 = time.time()
        df = BiomassABM(s, seed=1).run()
        tot = df.groupby("year")[["harvest", "ltmd", "mt", "panel", "bioheat_odt", "pellet_odt", "jobs", "ind_jobs", "ind_income", "value_added"]].sum()
        print(f"== {s} {STRATEGIES[s]['name']}  ({time.time() - t0:.2f}s)")
        tot["util"] = tot.harvest / tot.ltmd
        print(tot.loc[[2026, 2030, 2035, 2040, 2045]].round(2).to_string())
