# Advisor Transition Intelligence

Competition-grade decision-support prototype for the Inter IIT Tech Meet 15.0 LPL Financial Advisor Investment Transition Solution challenge.

## What makes this different

The product does not equate a higher projected return with a better decision. It evaluates the **net client outcome** after account-aware taxes, surrender and transaction friction, advisory fees, liquidity, risk, historical evidence, retirement spending, Social Security, RMD timing and portfolio longevity.

It compares:

1. Current active 60/40 portfolio.
2. Full proposed advisory core.
3. Independent low-cost ETF research candidate.
4. 25%, 50% and 75% partial transitions to the proposed strategy.

## Run the app

Double-click `launch_app.bat`, or run:

```powershell
cd "E:\Inter IIT Tech Meet Competition\advisor_transition_intelligence"
python -m pip install -r requirements.txt
streamlit run app.py
```

## Public demo

This repository is designed to be deployable on Streamlit Community Cloud using `app.py` as the entry point. The public demo should be used with synthetic or anonymized information only. See [`PUBLIC_DEMO_NOTICE.md`](PUBLIC_DEMO_NOTICE.md) before sharing the link.

The hosted URL is created by Streamlit after the repository is connected to an authorized GitHub account; no API key is required for the deterministic modelling engine.

## Model overview

- **Portfolio intake:** per holding value, cost basis, account type, surrender cost and transaction cost.
- **Tax friction:** explicit long-term/short-term taxable gains, realised loss offsets, annuity gain, approximate 2026 federal ordinary-income/long-term-capital-gains/NIIT logic, and a user-entered state rate. Traditional/Roth IRA transitions are not presumed taxable sales.
- **Historic evidence:** cached monthly SPY, AGG, VXUS and VNQ adjusted-close proxies from Feb 2016 through Oct 2026.
- **Risk:** annualised return, volatility, maximum drawdown, downside proxy, and named stress windows (COVID selloff and 2022 rate shock).
- **Retirement:** 1,500 historical block-bootstrap paths to age 90; inflation-linked spending, Social Security offset, and RMD timing are represented.
- **Recommendation:** transparent composite ranking across wealth, non-depletion resilience, retirement wealth, liquidity and risk-adjusted historic evidence, after hard client constraints for tax budget, maximum transition size and risk ceiling.

## Data and provenance

`data/market_monthly_returns_2016_2026.csv` is a cached public demo dataset generated from Yahoo Finance adjusted-close data with `yfinance` on 2026-11-03. See `data/data_sources.csv` and `data/market_data_dictionary.csv`.

This cache improves reproducibility but is **not licensed client-reporting data**. Before any real-client use, validate data licensing, dividend/corporate-action methodology, product disclosures, holdings, tax lots and assumptions.

## Guardrails

This is decision support—not financial, tax, legal or investment advice. It intentionally surfaces human-review triggers. It does not store PII, connect to client accounts, send data to an LLM, or autonomously execute transactions.

The following remain deliberately unsupported without specialist inputs and are shown as review gates: wash sales and tax-loss carryforwards, municipal-bond tax treatment, contract-specific annuity riders/MVA provisions, and state-specific exceptions. The exportable advisor-acknowledged decision record includes a model version and audit hash.

## Tests

```powershell
python -m unittest discover -s tests -v
```

## AI disclosure

AI-assisted development was used for code scaffolding, design iteration and drafting. The team is responsible for independent review, factual validation, data licensing, source verification, financial modelling and every submitted claim.

