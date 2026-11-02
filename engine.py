"""Core financial modelling engine for Advisor Transition Intelligence.

This prototype is intentionally deterministic and explainable. It is not
personal financial advice and uses user-provided assumptions plus a labelled
synthetic return history for the demo dataset.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple
import math
import numpy as np
import pandas as pd


TAX_BRACKETS_2026_SINGLE = [
    (0, 0.10), (12400, 0.12), (50400, 0.22), (105700, 0.24),
    (201775, 0.32), (256225, 0.35), (640600, 0.37)
]
TAX_BRACKETS_2026_MFJ = [
    (0, 0.10), (24800, 0.12), (100800, 0.22), (211400, 0.24),
    (403550, 0.32), (512450, 0.35), (768700, 0.37)
]


@dataclass
class Strategy:
    name: str
    expected_return: float
    volatility: float
    annual_fee: float
    equity_weight: float
    bond_weight: float
    liquidity_score: float = 1.0
    exit_cost: float = 0.0
    transaction_cost: float = 0.0
    tax_drag: float = 0.0
    description: str = ""

    @property
    def total_transition_cost(self) -> float:
        return self.exit_cost + self.transaction_cost


def marginal_income_tax(income: float, filing_status: str = "Single") -> float:
    """Approximate federal tax using 2026 ordinary-income brackets."""
    brackets = TAX_BRACKETS_2026_MFJ if filing_status == "Married filing jointly" else TAX_BRACKETS_2026_SINGLE
    income = max(0.0, float(income))
    tax = 0.0
    for idx, (floor, rate) in enumerate(brackets):
        ceiling = brackets[idx + 1][0] if idx + 1 < len(brackets) else math.inf
        if income > floor:
            tax += (min(income, ceiling) - floor) * rate
    return tax


def effective_tax_rate(income: float, filing_status: str, capital_gains: float = 0.0,
                       state_tax_rate: float = 0.0) -> float:
    ordinary_tax = marginal_income_tax(income, filing_status)
    long_term_cap_gains_tax = max(0.0, capital_gains) * 0.15
    niit_threshold = 250000 if filing_status == "Married filing jointly" else 200000
    niit = max(0.0, min(max(0.0, capital_gains), income + capital_gains - niit_threshold)) * 0.038
    total = ordinary_tax + long_term_cap_gains_tax + niit + max(0.0, state_tax_rate) * max(0.0, income + capital_gains)
    base = max(1.0, income + capital_gains)
    return min(0.60, total / base)


def create_demo_strategies() -> Dict[str, Strategy]:
    return {
        "Current - Balanced Mutual Funds": Strategy(
            "Current - Balanced Mutual Funds", 0.065, 0.115, 0.0125, 0.60, 0.40,
            liquidity_score=0.85, description="60/40 diversified mutual-fund portfolio"
        ),
        "Proposed - Advisory Core": Strategy(
            "Proposed - Advisory Core", 0.074, 0.125, 0.0090, 0.70, 0.30,
            liquidity_score=0.90, exit_cost=15000, transaction_cost=5000,
            description="Tax-aware advisory portfolio with broader diversification"
        ),
        "Research - Low-cost ETF Core": Strategy(
            "Research - Low-cost ETF Core", 0.071, 0.105, 0.0035, 0.65, 0.35,
            liquidity_score=0.95, exit_cost=15000, transaction_cost=2500,
            description="Research candidate: low-cost, liquid ETF implementation"
        ),
    }


def generate_synthetic_history(path: str, periods: int = 120, seed: int = 7) -> pd.DataFrame:
    """Create reproducible monthly proxy returns for a transparent demo."""
    rng = np.random.default_rng(seed)
    months = pd.date_range(end=pd.Timestamp.today().normalize(), periods=periods, freq="ME")
    regime = np.where(np.arange(periods) % 48 < 6, -1, 1)
    equity = rng.normal(0.006, 0.045, periods) + np.where(regime < 0, -0.025, 0)
    bonds = rng.normal(0.0025, 0.012, periods) + np.where(regime < 0, 0.004, 0)
    intl = rng.normal(0.005, 0.050, periods) + np.where(regime < 0, -0.028, 0)
    reit = rng.normal(0.004, 0.038, periods) + np.where(regime < 0, -0.020, 0)
    return pd.DataFrame({"date": months, "us_equity": equity, "bonds": bonds, "intl_equity": intl, "reit": reit,
                         "source": "Synthetic proxy history - replace with licensed/public data for final submission"})


def strategy_history_returns(strategy: Strategy, history: pd.DataFrame) -> pd.Series:
    equity = 0.72 * history.us_equity + 0.18 * history.intl_equity + 0.10 * history.reit
    gross = strategy.equity_weight * equity + strategy.bond_weight * history.bonds
    return gross - strategy.annual_fee / 12


def max_drawdown(values: pd.Series) -> float:
    peak = values.cummax()
    return float((values / peak - 1).min())


def backtest(strategies: Dict[str, Strategy], history: pd.DataFrame, periods=(12, 36, 60, 120)) -> pd.DataFrame:
    rows = []
    for name, strategy in strategies.items():
        r = strategy_history_returns(strategy, history)
        for n in periods:
            sample = r.tail(min(n, len(r)))
            growth = (1 + sample).cumprod()
            cumulative = float(growth.iloc[-1] - 1)
            annualized = float((1 + cumulative) ** (12 / len(sample)) - 1)
            downside = float(sample[sample < 0].mean()) if (sample < 0).any() else 0.0
            rows.append({"strategy": name, "period_years": round(len(sample) / 12, 1),
                         "cumulative_return": cumulative, "annualized_return": annualized,
                         "volatility": float(sample.std() * np.sqrt(12)), "downside_monthly": downside,
                         "max_drawdown": max_drawdown(growth), "transition_cost": strategy.total_transition_cost})
    return pd.DataFrame(rows)


def simulate_retirement(strategy: Strategy, initial_value: float, current_age: int, retirement_age: int,
                        end_age: int, annual_withdrawal: float, inflation: float,
                        tax_rate: float, n_paths: int = 500, seed: int = 19) -> Tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    ages = np.arange(current_age, end_age + 1)
    years = len(ages) - 1
    values = np.zeros((n_paths, len(ages)))
    withdrawals = np.zeros((n_paths, len(ages)))
    values[:, 0] = max(0, initial_value - strategy.total_transition_cost)
    for y in range(1, len(ages)):
        age = ages[y]
        mean = strategy.expected_return if age <= retirement_age else strategy.expected_return - 0.005
        returns = rng.normal(mean, strategy.volatility, n_paths)
        pre = values[:, y - 1] * (1 + returns)
        if age >= retirement_age:
            w = annual_withdrawal * ((1 + inflation) ** (age - retirement_age))
            withdrawals[:, y] = w
            pre = pre - w / max(0.5, 1 - tax_rate)
        values[:, y] = np.maximum(0, pre)
    summary = pd.DataFrame({"age": ages,
                            "p10": np.percentile(values, 10, axis=0),
                            "median": np.percentile(values, 50, axis=0),
                            "p90": np.percentile(values, 90, axis=0),
                            "success_rate": np.mean(values > 0, axis=0)})
    path_df = pd.DataFrame(values, columns=[f"age_{a}" for a in ages])
    return summary, path_df


def compare_strategies(strategies: Dict[str, Strategy], persona: dict, history: pd.DataFrame,
                       retirement_age: int = 60, end_age: int = 90) -> Tuple[pd.DataFrame, Dict[str, dict]]:
    results = []
    details = {}
    tax_rate = effective_tax_rate(persona["annual_income"], persona["filing_status"], persona.get("capital_gains", 0), persona.get("state_tax_rate", 0.0))
    for name, strategy in strategies.items():
        summary, paths = simulate_retirement(strategy, persona["portfolio_value"], persona["current_age"], retirement_age,
                                              end_age, persona["annual_withdrawal"], persona["inflation"], tax_rate)
        at = {int(row.age): row for _, row in summary.iterrows()}
        terminal = at[end_age]
        at_ret = at[retirement_age]
        break_even = None
        score = (0.45 * float(terminal["median"]) / max(1, persona["portfolio_value"]) +
                 0.30 * float(terminal["success_rate"]) +
                 0.15 * float(at_ret["median"]) / max(1, persona["portfolio_value"]) +
                 0.10 * strategy.liquidity_score - 0.20 * strategy.volatility)
        results.append({"strategy": name, "score": score, "median_at_retirement": float(at_ret["median"]),
                        "median_at_70": float(at[70]["median"]), "median_at_80": float(at[80]["median"]),
                        "median_at_90": float(terminal["median"]), "success_at_90": float(terminal["success_rate"]),
                        "transition_cost": strategy.total_transition_cost, "tax_rate_used": tax_rate,
                        "liquidity_score": strategy.liquidity_score, "volatility": strategy.volatility,
                        "break_even_years": break_even})
        details[name] = {"summary": summary, "paths": paths}
    frame = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    current_name = next((n for n in strategies if n.startswith("Current")), None)
    if current_name:
        baseline = details[current_name]["summary"].set_index("age")["median"]
        for idx, result in frame.iterrows():
            if not result["strategy"].startswith("Current") and result["transition_cost"] > 0:
                candidate = details[result["strategy"]]["summary"].set_index("age")["median"]
                recovered = (candidate - baseline)
                recovered = recovered[recovered >= result["transition_cost"]]
                if len(recovered):
                    frame.loc[idx, "break_even_years"] = int(recovered.index[0] - persona["current_age"])
    frame["rank"] = np.arange(1, len(frame) + 1)
    return frame, details


def recommendation_text(results: pd.DataFrame, persona: dict) -> str:
    top = results.iloc[0]
    second = results.iloc[1] if len(results) > 1 else None
    if top["strategy"].startswith("Current"):
        decision = "retain the current strategy"
    elif top["strategy"].startswith("Research"):
        decision = "prefer the low-cost research candidate, subject to due diligence"
    else:
        decision = "transition to the proposed strategy"
    gap = (top["score"] - second["score"]) if second is not None else 0
    return (f"For {persona['name']}, the model currently recommends {decision}. "
            f"The leading strategy ranks first on the transparent composite score ({top['score']:.3f}) "
            f"with median age-90 wealth of ${top['median_at_90']:,.0f} and a {top['success_at_90']:.0%} "
            f"probability of avoiding portfolio depletion under the simulated withdrawal plan. "
            f"The score advantage over the next option is {gap:.3f}; this is evidence for a review, not a guarantee. "
            "Revisit the decision if the client's spending need, tax profile, liquidity need, or market assumptions change.")

