"""Competition-grade, explainable transition modelling primitives.

This module deliberately exposes assumptions rather than hiding them in an
opaque optimiser. It is decision support only and is not tax, legal, or
investment advice.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Iterable
import math
import numpy as np
import pandas as pd

ORDINARY_2026 = {
    "Single": [(0, .10), (12400, .12), (50400, .22), (105700, .24), (201775, .32), (256225, .35), (640600, .37)],
    "Married filing jointly": [(0, .10), (24800, .12), (100800, .22), (211400, .24), (403550, .32), (512450, .35), (768700, .37)],
}
STANDARD_DEDUCTION_2026 = {"Single": 16100, "Married filing jointly": 32200}
LTCG_2026 = {"Single": [(0, .00), (49250, .15), (542500, .20)], "Married filing jointly": [(0, .00), (98500, .15), (610700, .20)]}
NIIT_THRESHOLD = {"Single": 200000, "Married filing jointly": 250000}


@dataclass(frozen=True)
class StrategySpec:
    name: str
    weights: tuple[float, float, float, float]  # US, bonds, international, REIT
    annual_fee: float
    liquidity: float
    description: str
    implementation_cost: float = 0.0


def progressive_tax(taxable_income: float, brackets: list[tuple[float, float]]) -> float:
    taxable_income = max(0.0, float(taxable_income))
    total = 0.0
    for i, (floor, rate) in enumerate(brackets):
        ceiling = brackets[i + 1][0] if i + 1 < len(brackets) else math.inf
        total += max(0.0, min(taxable_income, ceiling) - floor) * rate
    return total


def ordinary_income_tax(income: float, filing_status: str) -> float:
    taxable = max(0.0, income - STANDARD_DEDUCTION_2026[filing_status])
    return progressive_tax(taxable, ORDINARY_2026[filing_status])


def long_term_capital_gains_tax(ordinary_income: float, gains: float, filing_status: str) -> float:
    """Incremental US federal LTCG estimate using 2026 threshold assumptions."""
    gains = max(0.0, gains)
    ordinary_taxable = max(0.0, ordinary_income - STANDARD_DEDUCTION_2026[filing_status])
    tax = 0.0
    remaining = gains
    for i, (floor, rate) in enumerate(LTCG_2026[filing_status]):
        ceiling = LTCG_2026[filing_status][i + 1][0] if i + 1 < len(LTCG_2026[filing_status]) else math.inf
        room = max(0.0, ceiling - max(floor, ordinary_taxable))
        allocated = min(remaining, room)
        tax += allocated * rate
        remaining -= allocated
        ordinary_taxable = max(ordinary_taxable, ceiling)
        if remaining <= 0:
            break
    return tax


def niit(ordinary_income: float, investment_income: float, filing_status: str) -> float:
    excess_magi = max(0.0, ordinary_income + investment_income - NIIT_THRESHOLD[filing_status])
    return .038 * min(max(0.0, investment_income), excess_magi)


def rmd_age(current_age: int, current_year: int = 2026) -> int:
    """SECURE 2.0 schedule: people reaching 74 after 2032 use age 75."""
    birth_year = current_year - current_age
    return 75 if birth_year >= 1959 else 73


def uniform_lifetime_divisor(age: int) -> float:
    # IRS Uniform Lifetime Table approximation for ages used by this prototype.
    table = {73: 26.5, 74: 25.5, 75: 24.6, 76: 23.7, 77: 22.9, 78: 22.0, 79: 21.1,
             80: 20.2, 81: 19.4, 82: 18.5, 83: 17.7, 84: 16.8, 85: 16.0, 86: 15.2,
             87: 14.4, 88: 13.7, 89: 12.9, 90: 12.2}
    return table.get(age, max(1.9, 12.2 - .7 * (age - 90)))


def default_strategies() -> Dict[str, StrategySpec]:
    return {
        "Current - Active 60/40": StrategySpec("Current - Active 60/40", (.45, .40, .10, .05), .0125, .82, "Existing diversified mutual-fund allocation"),
        "Proposed - Advisory Core": StrategySpec("Proposed - Advisory Core", (.55, .28, .12, .05), .0090, .90, "Tax-aware advisory core with broader equity exposure", .0025),
        "Research - Low-cost ETF Core": StrategySpec("Research - Low-cost ETF Core", (.50, .35, .10, .05), .0035, .96, "Low-cost ETF candidate with high liquidity", .0015),
    }


def transition_cost(holdings: pd.DataFrame, fraction: float, income: float, filing_status: str, state_tax_rate: float) -> dict:
    """Calculate transition frictions from account-aware holdings.

    Required holding columns: value, basis, account_type, exit_cost_rate,
    transaction_cost_rate. Account types: Taxable, Traditional IRA, Roth IRA,
    Annuity. Annuity gains are conservatively treated as ordinary income.
    """
    fraction = float(np.clip(fraction, 0, 1))
    h = holdings.copy()
    for col, default in {"basis": 0, "exit_cost_rate": 0, "transaction_cost_rate": 0, "holding_period": "Long-term"}.items():
        if col not in h: h[col] = default
    h["value"] = pd.to_numeric(h["value"], errors="coerce").fillna(0).clip(lower=0)
    h["basis"] = pd.to_numeric(h["basis"], errors="coerce").fillna(0).clip(lower=0)
    sold_value = h.value * fraction
    realised = (h.value - h.basis) * fraction
    taxable = h.account_type.eq("Taxable")
    long_term = taxable & h.holding_period.eq("Long-term")
    short_term = taxable & h.holding_period.eq("Short-term")
    lt_gain = realised.where(long_term, 0).clip(lower=0).sum()
    st_gain = realised.where(short_term, 0).clip(lower=0).sum()
    tax_losses = -realised.where(taxable, 0).clip(upper=0).sum()
    # Losses offset short-term gain first, then long-term gain. Carryovers and wash sales are flagged, not inferred.
    net_st = max(0.0, st_gain - tax_losses)
    net_lt = max(0.0, lt_gain - max(0.0, tax_losses - st_gain))
    annuity_gains = realised.where(h.account_type.eq("Annuity"), 0).clip(lower=0).sum()
    ltcg = long_term_capital_gains_tax(income, net_lt, filing_status)
    ordinary = ordinary_income_tax(income + annuity_gains + net_st, filing_status) - ordinary_income_tax(income, filing_status)
    investment_surtax = niit(income, net_lt + net_st + annuity_gains, filing_status)
    state = state_tax_rate * (net_lt + net_st + annuity_gains)
    exits = float((sold_value * h.exit_cost_rate).sum())
    transaction = float((sold_value * h.transaction_cost_rate).sum())
    return {"sold_value": float(sold_value.sum()), "long_term_taxable_gains": float(lt_gain), "short_term_taxable_gains": float(st_gain), "tax_losses_harvested": float(tax_losses), "taxable_gains": float(net_lt + net_st), "annuity_gains": float(annuity_gains),
            "capital_gains_tax": ltcg, "ordinary_tax_on_annuity": ordinary, "niit": investment_surtax,
            "state_tax": state, "exit_cost": exits, "transaction_cost": transaction,
            "total": float(ltcg + ordinary + investment_surtax + state + exits + transaction)}


def historical_returns(strategy: StrategySpec, market: pd.DataFrame) -> pd.Series:
    cols = ["us_equity", "bonds", "intl_equity", "reit"]
    gross = market[cols].mul(np.array(strategy.weights), axis=1).sum(axis=1)
    return gross - strategy.annual_fee / 12


def historical_metrics(returns: pd.Series) -> dict:
    growth = (1 + returns).cumprod()
    years = max(len(returns) / 12, 1 / 12)
    annualized = growth.iloc[-1] ** (1 / years) - 1
    drawdown = (growth / growth.cummax() - 1).min()
    downside = returns[returns < 0]
    return {"annualized_return": float(annualized), "cumulative_return": float(growth.iloc[-1] - 1),
            "volatility": float(returns.std(ddof=1) * np.sqrt(12)), "max_drawdown": float(drawdown),
            "sortino_proxy": float((returns.mean() * 12) / max(1e-6, downside.std(ddof=1) * np.sqrt(12))) if len(downside) > 1 else 0.0}


def stress_scenarios(strategy: StrategySpec, market: pd.DataFrame) -> pd.DataFrame:
    r = historical_returns(strategy, market)
    dated = pd.DataFrame({"date": pd.to_datetime(market.date), "return": r})
    windows = {"COVID selloff (Feb-Mar 2020)": ("2020-02-01", "2020-03-31"),
               "Inflation / rate shock (2022)": ("2022-01-01", "2022-12-31"),
               "Latest 12 months": (str(dated.date.max() - pd.DateOffset(months=11)), str(dated.date.max()))}
    rows=[]
    for name,(start,end) in windows.items():
        vals=dated[(dated.date>=start)&(dated.date<=end)]["return"]
        if len(vals): rows.append({"scenario":name,"return":float((1+vals).prod()-1),"months":len(vals)})
    return pd.DataFrame(rows)


def bootstrap_retirement(strategy: StrategySpec, market: pd.DataFrame, start_value: float, current_age: int,
                         retirement_age: int, spending: float, inflation: float, filing_status: str,
                         ordinary_income_at_retirement: float, social_security: float, ss_start_age: int,
                         traditional_ira_share: float, transition_cost_total: float, n_paths: int = 1500,
                         seed: int = 42) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Block-bootstrap historical monthly returns to preserve observed cross-asset behaviour."""
    rng=np.random.default_rng(seed)
    base=historical_returns(strategy, market).to_numpy()
    months=(90-current_age)*12
    values=np.zeros((n_paths, months+1)); values[:,0]=max(0,start_value-transition_cost_total)
    annual_rmd=np.zeros((n_paths, months+1)); ages=np.arange(current_age, 90+1/12, 1/12)
    rmd_start=rmd_age(current_age)
    block_starts=rng.integers(0,len(base),size=n_paths)
    for m in range(1, months+1):
        # Sample contiguous 12-month historical blocks to retain local return structure.
        if (m - 1) % 12 == 0:
            block_starts=rng.integers(0,len(base),size=n_paths)
        index=(block_starts+(m-1)%12) % len(base)
        values[:,m]=values[:,m-1]*(1+base[index])
        age=ages[m]
        if age>=retirement_age:
            annual_need=spending*((1+inflation)**(age-retirement_age))
            ss=social_security*((1+inflation)**max(0,age-ss_start_age)) if age>=ss_start_age else 0
            net_need=max(0,annual_need-ss)/12
            distribution_tax_rate=min(.42, ordinary_income_tax(ordinary_income_at_retirement+annual_need,filing_status)/max(1,ordinary_income_at_retirement+annual_need))
            withdrawal=net_need/max(.55,1-distribution_tax_rate)
            if age>=rmd_start:
                divisor=uniform_lifetime_divisor(int(age))
                rmd=(values[:,m-1]*traditional_ira_share/divisor)/12
                withdrawal=np.maximum(withdrawal,rmd)
                annual_rmd[:,m]=rmd*12
            values[:,m]=np.maximum(0,values[:,m]-withdrawal)
    checkpoints=[]
    for age in [retirement_age,70,80,90]:
        idx=min(months,int(round((age-current_age)*12)))
        if idx>=0:
            checkpoints.append({"age":age,"p10":np.percentile(values[:,idx],10),"median":np.percentile(values[:,idx],50),
                                "p90":np.percentile(values[:,idx],90),"success_rate":float(np.mean(values[:,idx]>0)),
                                "median_rmd":np.median(annual_rmd[:,idx])})
    trajectory=[]
    for age in range(current_age,91):
        idx=min(months,(age-current_age)*12)
        trajectory.append({"age":age,"p10":np.percentile(values[:,idx],10),"median":np.percentile(values[:,idx],50),"p90":np.percentile(values[:,idx],90),"success_rate":float(np.mean(values[:,idx]>0))})
    return pd.DataFrame(trajectory), pd.DataFrame(checkpoints)


def blend(current: StrategySpec, proposed: StrategySpec, fraction: float) -> StrategySpec:
    f=float(np.clip(fraction,0,1))
    w=tuple((1-f)*a+f*b for a,b in zip(current.weights,proposed.weights))
    return StrategySpec(f"Partial transition - {f:.0%} proposed",w,(1-f)*current.annual_fee+f*proposed.annual_fee,(1-f)*current.liquidity+f*proposed.liquidity,"Optimised partial transition",proposed.implementation_cost*f)


def evaluate(strategy: StrategySpec, persona: dict, market: pd.DataFrame, holdings: pd.DataFrame, transition_fraction: float) -> dict:
    cost=transition_cost(holdings,transition_fraction,persona["annual_income"],persona["filing_status"],persona["state_tax_rate"])
    cost["total"] += persona["portfolio_value"]*strategy.implementation_cost*transition_fraction
    trajectory,checkpoints=bootstrap_retirement(strategy,market,persona["portfolio_value"],persona["current_age"],persona["retirement_age"],persona["annual_withdrawal"],persona["inflation"],persona["filing_status"],persona.get("retirement_other_income",0),persona.get("social_security",0),persona.get("ss_start_age",67),persona.get("traditional_ira_share",.5),cost["total"])
    hist=historical_metrics(historical_returns(strategy,market))
    age90=checkpoints[checkpoints.age==90].iloc[0]
    ret=checkpoints[checkpoints.age==persona["retirement_age"]].iloc[0]
    score=(.40*age90["median"]/max(1,persona["portfolio_value"])+.30*age90["success_rate"]+.12*ret["median"]/max(1,persona["portfolio_value"])+.10*strategy.liquidity+.08*max(0,hist["sortino_proxy"]))
    return {"strategy":strategy.name,"score":float(score),"transition_fraction":transition_fraction,"total_transition_cost":cost["total"],"age90_median":age90["median"],"age90_success":age90["success_rate"],"retirement_median":ret["median"],"annualized_return":hist["annualized_return"],"volatility":hist["volatility"],"max_drawdown":hist["max_drawdown"],"liquidity":strategy.liquidity,"cost_detail":cost,"trajectory":trajectory,"checkpoints":checkpoints,"stress":stress_scenarios(strategy,market)}


def optimise_transition(persona: dict, market: pd.DataFrame, holdings: pd.DataFrame, strategies: Dict[str,StrategySpec]|None=None) -> tuple[pd.DataFrame, dict]:
    strategies=strategies or default_strategies()
    current=strategies["Current - Active 60/40"]
    candidates=[(current,0.0), (strategies["Proposed - Advisory Core"],1.0), (strategies["Research - Low-cost ETF Core"],1.0)]
    proposed=strategies["Proposed - Advisory Core"]
    candidates += [(blend(current,proposed,f),float(f)) for f in np.arange(.25,1,.25)]
    outcomes=[evaluate(s,persona,market,holdings,f) for s,f in candidates]
    table=pd.DataFrame([{k:v for k,v in x.items() if k not in {"cost_detail","trajectory","checkpoints","stress"}} for x in outcomes])
    tax_budget=persona.get("tax_budget",math.inf)
    max_transition=persona.get("max_transition_fraction",1.0)
    max_volatility=persona.get("max_volatility",math.inf)
    table["eligible"]=(table.total_transition_cost<=tax_budget+1e-9)&(table.transition_fraction<=max_transition+1e-9)&(table.volatility<=max_volatility+1e-9)
    table["constraint_reason"]="Eligible"
    table.loc[table.total_transition_cost>tax_budget+1e-9,"constraint_reason"]="Exceeds tax budget"
    table.loc[table.transition_fraction>max_transition+1e-9,"constraint_reason"]="Exceeds maximum transition"
    table.loc[table.volatility>max_volatility+1e-9,"constraint_reason"]="Exceeds risk ceiling"
    table=table.sort_values(["eligible","score"],ascending=[False,False]).reset_index(drop=True)
    selected_name=table.iloc[0].strategy
    selected=next(x for x in outcomes if x["strategy"]==selected_name)
    return table,selected


def default_holdings() -> pd.DataFrame:
    return pd.DataFrame([
        {"holding":"Taxable mutual funds","value":230000,"basis":155000,"account_type":"Taxable","holding_period":"Long-term","exit_cost_rate":0,"transaction_cost_rate":.0010},
        {"holding":"Traditional IRA","value":300000,"basis":300000,"account_type":"Traditional IRA","holding_period":"N/A","exit_cost_rate":0,"transaction_cost_rate":.0005},
        {"holding":"Deferred annuity","value":120000,"basis":95000,"account_type":"Annuity","holding_period":"N/A","exit_cost_rate":.030,"transaction_cost_rate":.0010},
        {"holding":"Roth IRA","value":50000,"basis":50000,"account_type":"Roth IRA","holding_period":"N/A","exit_cost_rate":0,"transaction_cost_rate":.0005},
    ])


def tax_efficient_sale_plan(lots: pd.DataFrame, target_sale: float, ordinary_income: float,
                            filing_status: str, state_tax_rate: float) -> pd.DataFrame:
    """Select taxable lots to sell with a transparent minimise-tax heuristic.

    Lots with losses are sold first, followed by the lowest gain-per-dollar lots.
    This is a deterministic planning aid; wash sales, carryforwards and product
    restrictions remain explicit review gates.
    """
    df=lots.copy()
    for col, default in {"basis":0,"holding_period":"Long-term","account_type":"Taxable"}.items():
        if col not in df: df[col]=default
    df["value"]=pd.to_numeric(df.value,errors="coerce").fillna(0).clip(lower=0)
    df["basis"]=pd.to_numeric(df.basis,errors="coerce").fillna(0).clip(lower=0)
    df["unrealised_gain"]=df.value-df.basis
    taxable=df.account_type.eq("Taxable")
    # Losses first; then lowest embedded gain ratio; non-taxable accounts are left untouched.
    df["tax_priority"]=np.where(taxable,df.unrealised_gain/df.value.replace(0,np.nan),np.inf)
    df=df.sort_values(["tax_priority","value"],ascending=[True,False]).reset_index(drop=True)
    remaining=max(0.0,float(target_sale)); rows=[]
    for _,row in df.iterrows():
        if remaining<=0 or row.account_type != "Taxable":
            continue
        sell=min(float(row.value),remaining); fraction=sell/max(1,float(row.value))
        realised=float(row.unrealised_gain)*fraction
        rows.append({"holding":row.get("holding",f"Lot {len(rows)+1}"),"account_type":row.account_type,"holding_period":row.holding_period,"sell_value":sell,"realised_gain":realised,"reason":"Tax-loss harvest" if realised<0 else "Lowest embedded gain available"})
        remaining-=sell
    plan=pd.DataFrame(rows)
    if len(plan):
        planned=plan.assign(value=plan.sell_value,basis=plan.sell_value-plan.realised_gain,exit_cost_rate=0,transaction_cost_rate=0)
        estimate=transition_cost(planned,1,ordinary_income,filing_status,state_tax_rate)
        plan["estimated_total_tax_friction"]=estimate["total"]
    return plan


def phased_transition_schedule(holdings: pd.DataFrame, total_fraction: float, annual_tax_budget: float,
                               income: float, filing_status: str, state_tax_rate: float) -> pd.DataFrame:
    """Create a bounded annual transition schedule using the tax-budget constraint."""
    steps=[]; completed=0.0; year=1; total_fraction=float(np.clip(total_fraction,0,1))
    while completed < total_fraction-1e-9 and year<=10:
        lo,hi=0.0,total_fraction-completed
        for _ in range(24):
            mid=(lo+hi)/2
            friction=transition_cost(holdings,mid,income,filing_status,state_tax_rate)["total"]
            if friction<=annual_tax_budget: lo=mid
            else: hi=mid
        if lo<1e-5: break
        friction=transition_cost(holdings,lo,income,filing_status,state_tax_rate)["total"]
        steps.append({"phase_year":year,"portfolio_fraction":lo,"estimated_friction":friction,"cumulative_fraction":completed+lo})
        completed+=lo; year+=1
    if completed < total_fraction-1e-9:
        steps.append({"phase_year":year,"portfolio_fraction":0.0,"estimated_friction":0.0,"cumulative_fraction":completed,"status":"Remaining transition exceeds current annual tax budget"})
    return pd.DataFrame(steps)

