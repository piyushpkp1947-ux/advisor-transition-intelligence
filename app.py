"""Streamlit interface for Advisor Transition Intelligence."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import pandas as pd
import streamlit as st
from advanced_engine import (StrategySpec, default_holdings, default_strategies, historical_returns, historical_metrics,
                             optimise_transition, phased_transition_schedule, rmd_age, tax_efficient_sale_plan)

ROOT=Path(__file__).parent
DATA=ROOT/"data"/"market_monthly_returns_2016_2026.csv"
st.set_page_config(page_title="Advisor Transition Intelligence", page_icon="◈", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Source+Serif+4:wght@500;600&display=swap');
.stApp {background:#f7f8f7;color:#16222d;font-family:'DM Sans',sans-serif}.block-container{padding:1.25rem 2.5rem 3rem;max-width:1540px}
[data-testid="stSidebar"]{background:#102b3b;border-right:1px solid #24495b}[data-testid="stSidebar"] *{color:#edf3f5!important}[data-testid="stSidebar"] .stCaption{color:#b9c8cf!important}[data-testid="stSidebar"] .stDivider{border-color:#31596b!important}
.hero{padding:0 0 1.35rem;border-radius:0;background:transparent;color:#16222d;border-bottom:1px solid #cdd7d7;margin-bottom:1rem}
.hero h1{font-family:'Source Serif 4',Georgia,serif;font-weight:600;margin:.18rem 0 .35rem;font-size:2.3rem;letter-spacing:-.03em}.hero p{margin:0;color:#52616b;font-size:1rem;max-width:760px}.eyebrow{font-size:.68rem;font-weight:700;letter-spacing:.13em;color:#23765f}
.guardrail{background:#f1f6f4;border-left:3px solid #2c7a63;border-top:0;border-right:0;border-bottom:0;border-radius:0;padding:.7rem 1rem;color:#345247;margin:.75rem 0 1.2rem;font-size:.9rem}
.section-label{font-size:.7rem;font-weight:700;letter-spacing:.12em;color:#3c6d68;margin-top:1.2rem}
.stTabs [data-baseweb="tab-list"]{gap:2rem;border-bottom:1px solid #cfd8d9}.stTabs [data-baseweb="tab"]{padding:0 0 .85rem;background:transparent;font-size:.88rem;color:#5c6870}.stTabs [aria-selected="true"]{color:#173e50!important;border-bottom:3px solid #23765f}.stTabs [data-baseweb="tab-highlight"]{background:#23765f}
[data-testid="stMetric"]{background:#fff;border:1px solid #dce4e4;border-radius:3px;padding:1rem 1.1rem;box-shadow:none}[data-testid="stMetricLabel"]{font-size:.72rem;text-transform:uppercase;letter-spacing:.08em;color:#60717b}
.stButton>button{background:#165f50;color:#fff;border:0;border-radius:2px;font-weight:600;padding:.55rem 1rem}.stButton>button:hover{background:#0d4e41;color:#fff;border:0}.stDataFrame{border:1px solid #dce4e4;border-radius:2px}
</style>""",unsafe_allow_html=True)

@st.cache_data(show_spinner=False)
def load_market():
    return pd.read_csv(DATA,parse_dates=["date"])

def money(v): return f"${float(v):,.0f}"

market=load_market()
if "holdings" not in st.session_state: st.session_state.holdings=default_holdings()
if "analysis" not in st.session_state: st.session_state.analysis=None

st.markdown("""<div class="hero"><div class="eyebrow">ADVISOR WORKBENCH · TRANSITION REVIEW</div><h1>Advisor Transition Intelligence</h1><p>A structured review of whether a portfolio transition improves the client’s long-term outcome after costs, taxes, risk, liquidity, and retirement income needs.</p></div>""",unsafe_allow_html=True)
st.markdown("<div class='guardrail'><b>Decision-support only.</b> This prototype is transparent by design: no PII storage, no hidden AI scoring, and no guarantee of outcomes. A licensed advisor and tax professional must validate account details, tax lots, product terms and client suitability.</div>",unsafe_allow_html=True)

with st.sidebar:
    st.header("Client scenario")
    name=st.text_input("Client / household", "Jordan & Casey — Near-retirement")
    col1,col2=st.columns(2)
    age=col1.number_input("Current age",30,80,52)
    retire=col2.number_input("Retire at",int(age)+1,90,60)
    filing=st.selectbox("Filing status",["Married filing jointly","Single"])
    income=st.number_input("Current ordinary income ($)",0,2_000_000,180_000,5_000)
    state_tax=st.slider("State income tax rate",0.0,.15,.04,.005,format="%.1f%%")
    st.divider(); st.caption("Retirement-income assumptions")
    spending=st.number_input("Annual spending need ($)",0,500_000,70_000,5_000)
    social_security=st.number_input("Annual Social Security ($)",0,200_000,42_000,1_000)
    ss_age=st.number_input("Social Security start age",62,70,67)
    inflation=st.slider("Inflation",0.0,.08,.025,.005,format="%.1f%%")
    with st.expander("Configure proposed strategy"):
        st.caption("Enter the proposed allocation and implementation assumptions. We compare it with the current portfolio and the independent low-cost research model.")
        proposed_us=st.number_input("Proposed US equity (%)",0,100,55)
        proposed_bond=st.number_input("Proposed bonds (%)",0,100,28)
        proposed_intl=st.number_input("Proposed international equity (%)",0,100,12)
        proposed_reit=st.number_input("Proposed REIT (%)",0,100,5)
        proposed_fee=st.number_input("Proposed annual fee (%)",0.0,5.0,.90,.05)
        proposed_liquidity=st.slider("Proposed liquidity score",0.0,1.0,.90,.05)
    with st.expander("Client constraints (hard guardrails)"):
        tax_budget=st.number_input("Maximum transition-friction budget ($)",0,1_000_000,35_000,1_000)
        max_transition=st.slider("Maximum portfolio transition",0.0,1.0,1.0,.05,format="%.0f%%")
        max_volatility=st.slider("Maximum historic volatility",.01,.50,.20,.01,format="%.0f%%")
    st.caption("Tax calculation uses documented 2026 federal approximations; confirm actual tax treatment.")

proposed_total=proposed_us+proposed_bond+proposed_intl+proposed_reit
strategies=default_strategies()
strategies["Proposed - Advisory Core"]=StrategySpec("Proposed - Custom Advisory Core",(proposed_us/100,proposed_bond/100,proposed_intl/100,proposed_reit/100),proposed_fee/100,proposed_liquidity,"Advisor-configured proposed allocation",.0025)

tabs=st.tabs(["1 · Portfolio intake","2 · Decision cockpit","3 · Evidence & stress","4 · Retirement resilience","5 · Audit trail"])
with tabs[0]:
    st.subheader("Account-aware portfolio intake")
    st.write("Add the current holdings, cost basis and account type. Transition taxes are applied only where appropriate; qualified-account rollovers are not automatically treated as taxable sales.")
    edited=st.data_editor(st.session_state.holdings, num_rows="dynamic", use_container_width=True,
        column_config={"value":st.column_config.NumberColumn("Value",min_value=0,format="$%d"),"basis":st.column_config.NumberColumn("Cost basis",min_value=0,format="$%d"),"exit_cost_rate":st.column_config.NumberColumn("Exit / surrender rate",min_value=0,max_value=.30,format="%.2f%%"),"transaction_cost_rate":st.column_config.NumberColumn("Transaction rate",min_value=0,max_value=.10,format="%.2f%%"),"account_type":st.column_config.SelectboxColumn("Account type",options=["Taxable","Traditional IRA","Roth IRA","Annuity"]),"holding_period":st.column_config.SelectboxColumn("Tax holding period",options=["Long-term","Short-term","N/A"])},key="holdings_editor")
    st.session_state.holdings=edited
    total=float(pd.to_numeric(edited.value,errors="coerce").fillna(0).sum())
    ira_share=float(edited.loc[edited.account_type.eq("Traditional IRA"),"value"].sum()/total) if total else 0
    a,b,c=st.columns(3); a.metric("Mapped portfolio",money(total)); b.metric("Traditional IRA share",f"{ira_share:.0%}"); c.metric("RMD starting age",rmd_age(int(age)))
    issues=[]
    if total<=0: issues.append("Portfolio value must be greater than zero.")
    if (edited.basis>edited.value).any(): issues.append("One or more bases exceeds holding value; verify unrealised loss/tax-lot treatment.")
    if proposed_total != 100: issues.append(f"Proposed allocation totals {proposed_total}%; it must total 100%.")
    if not issues: st.success("Intake passed basic completeness checks. The next step evaluates full and partial transitions.")
    else:
        for issue in issues: st.error(issue)
    if st.button("Run full transition analysis",type="primary",disabled=bool(issues),use_container_width=True):
        persona={"name":name,"current_age":int(age),"retirement_age":int(retire),"portfolio_value":total,"annual_income":float(income),"filing_status":filing,"state_tax_rate":float(state_tax),"annual_withdrawal":float(spending),"inflation":float(inflation),"social_security":float(social_security),"ss_start_age":int(ss_age),"retirement_other_income":0,"traditional_ira_share":ira_share,"tax_budget":float(tax_budget),"max_transition_fraction":float(max_transition),"max_volatility":float(max_volatility)}
        with st.spinner("Running account-aware taxes, historic bootstrap paths, partial-transition optimisation and stress tests..."):
            ranking,best=optimise_transition(persona,market,edited,strategies)
        st.session_state.analysis={"persona":persona,"ranking":ranking,"best":best,"holdings":edited,"strategies":strategies}
        st.rerun()

analysis=st.session_state.analysis
if analysis is None:
    for tab in tabs[1:]:
        with tab: st.info("Complete the intake and select **Run full transition analysis** to populate this view.")
else:
    persona,ranking,best,analysed_strategies=analysis["persona"],analysis["ranking"],analysis["best"],analysis["strategies"]
    with tabs[1]:
        st.subheader("Decision cockpit")
        top=ranking.iloc[0]
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Recommended path",top.strategy)
        c2.metric("Transition level",f"{top.transition_fraction:.0%}")
        c3.metric("Age-90 median wealth",money(top.age90_median))
        c4.metric("Age-90 resilience",f"{top.age90_success:.0%}")
        st.success(f"Recommendation: **{top.strategy}**. It clears the configured guardrails and incorporates {money(top.total_transition_cost)} of estimated all-in transition friction before projecting retirement outcomes. This is a comparative scenario result, not a guarantee.")
        display=ranking[["strategy","eligible","constraint_reason","transition_fraction","score","total_transition_cost","retirement_median","age90_median","age90_success","annualized_return","volatility","max_drawdown","liquidity"]].copy()
        display.columns=["Strategy","Eligible","Constraint status","Transition","Decision score","All-in friction","Median at retirement","Median at age 90","Age-90 resilience","Historic annualised","Historic volatility","Historic max drawdown","Liquidity"]
        st.dataframe(display.style.format({"Transition":"{:.0%}","Decision score":"{:.3f}","All-in friction":"${:,.0f}","Median at retirement":"${:,.0f}","Median at age 90":"${:,.0f}","Age-90 resilience":"{:.0%}","Historic annualised":"{:.1%}","Historic volatility":"{:.1%}","Historic max drawdown":"{:.1%}","Liquidity":"{:.0%}"}),hide_index=True,use_container_width=True)
        d=best["cost_detail"]
        st.markdown("<div class='section-label'>ESTIMATED TRANSITION FRICTION</div>",unsafe_allow_html=True)
        cost=pd.DataFrame({"Component":["Long-term gains realised","Short-term gains realised","Tax losses harvested","Annuity gains (ordinary income)","Federal capital-gains tax","Ordinary tax on short-term / annuity gain","NIIT","State tax","Exit / surrender cost","Transaction cost","Total"],"Value":[d["long_term_taxable_gains"],d["short_term_taxable_gains"],d["tax_losses_harvested"],d["annuity_gains"],d["capital_gains_tax"],d["ordinary_tax_on_annuity"],d["niit"],d["state_tax"],d["exit_cost"],d["transaction_cost"],d["total"]]})
        st.dataframe(cost.style.format({"Value":"${:,.0f}"}),hide_index=True,use_container_width=True)
        if top.transition_fraction > 0:
            st.markdown("<div class='section-label'>TAX-AWARE IMPLEMENTATION PLAN</div>",unsafe_allow_html=True)
            lot_plan=tax_efficient_sale_plan(analysis["holdings"],top.transition_fraction*persona["portfolio_value"],persona["annual_income"],persona["filing_status"],persona["state_tax_rate"])
            if len(lot_plan):
                st.caption("Lot-selection heuristic sells taxable losses first, then lowest embedded gains. It is a planning aid; wash-sale and carryforward review remains required.")
                st.dataframe(lot_plan.style.format({"sell_value":"${:,.0f}","realised_gain":"${:,.0f}","estimated_total_tax_friction":"${:,.0f}"}),hide_index=True,use_container_width=True)
            phases=phased_transition_schedule(analysis["holdings"],top.transition_fraction,persona["tax_budget"],persona["annual_income"],persona["filing_status"],persona["state_tax_rate"])
            if len(phases) and phases.portfolio_fraction.sum()>0:
                st.caption("Phased schedule respects the entered annual tax-friction budget.")
                st.dataframe(phases.style.format({"portfolio_fraction":"{:.1%}","estimated_friction":"${:,.0f}","cumulative_fraction":"{:.1%}"}),hide_index=True,use_container_width=True)
        st.markdown("<div class='section-label'>ADVISOR REVIEW AND AUDIT RECORD</div>",unsafe_allow_html=True)
        reviewer=st.text_input("Advisor reviewer name",key="advisor_reviewer")
        acknowledged=st.checkbox("I verified this is decision support only and must be checked against actual tax lots, product disclosures, suitability and client objectives before any action.",key="advisor_ack")
        export={"model_version":"ATI-2.1","persona":persona,"ranking":ranking.to_dict(orient="records"),"recommended_strategy":best["strategy"],"transition_cost_detail":d,"data_source":str(market.source.iloc[0]),"advisor_reviewer":reviewer,"advisor_acknowledged":acknowledged,"unsupported_cases":["wash sales and loss carryforwards","municipal-bond tax treatment","annuity rider/MVA terms without contract data","state-specific exceptions"]}
        export["audit_hash"]=hashlib.sha256(json.dumps(export,sort_keys=True,default=str).encode()).hexdigest()
        st.download_button("Download signed decision record (JSON)",json.dumps(export,indent=2,default=str),"decision_record.json","application/json",disabled=not (reviewer and acknowledged))
    with tabs[2]:
        st.subheader("Historical evidence and stress tests")
        st.caption("Cached public ETF adjusted-close history, monthly, Feb 2016–Oct 2026. It provides evidence, not a forecast; dividend/corporate-action methodology must be independently validated before client use.")
        metrics=[]
        for spec in analysed_strategies.values():
            m=historical_metrics(historical_returns(spec,market)); metrics.append({"Strategy":spec.name,**m})
        hist=pd.DataFrame(metrics)
        st.dataframe(hist.style.format({"annualized_return":"{:.1%}","cumulative_return":"{:.1%}","volatility":"{:.1%}","max_drawdown":"{:.1%}","sortino_proxy":"{:.2f}"}),hide_index=True,use_container_width=True)
        st.markdown("<div class='section-label'>STRESS WINDOWS FOR THE RECOMMENDED PATH</div>",unsafe_allow_html=True)
        st.dataframe(best["stress"].style.format({"return":"{:.1%}"}),hide_index=True,use_container_width=True)
        st.warning("Advisor review trigger: if the client cannot tolerate the displayed stress loss, the risk profile or transition size should change even if the composite score is highest.")
    with tabs[3]:
        st.subheader("Retirement resilience")
        trajectory=best["trajectory"].set_index("age")
        st.line_chart(trajectory[["p10","median","p90"]])
        st.dataframe(best["checkpoints"].style.format({"p10":"${:,.0f}","median":"${:,.0f}","p90":"${:,.0f}","success_rate":"{:.0%}","median_rmd":"${:,.0f}"}),hide_index=True,use_container_width=True)
        st.info(f"Method: 1,500 historical block-bootstrap paths from the cached market history; spending is inflation-linked, Social Security offsets retirement spending from age {persona['ss_start_age']}, and Traditional IRA RMDs begin at age {rmd_age(persona['current_age'])}. The output communicates a range, not a single future value.")
    with tabs[4]:
        st.subheader("Audit trail and human review")
        st.markdown("""
        **Inputs captured:** holdings, basis, account type, exit and transaction costs, age, filing status, income, state rate, retirement age, spending, Social Security and inflation.

        **Decision logic:** account-aware transition friction + real historic monthly proxy data + block-bootstrap retirement paths + transparent composite ranking. We compare current, full proposed, research candidate and 25%/50%/75% proposed blends.

        **Data provenance:** `market_monthly_returns_2016_2026.csv` was generated from un-authenticated Yahoo Finance adjusted-close data through `yfinance`, downloaded on 2026-11-03. It is cached with the app for repeatability. It is a demo market proxy, not licensed client-reporting data.

        **Human checks required before action:** actual tax lots and holding period; specific product fees and surrender schedules; whether an IRA transaction is a non-taxable rollover; annuity contract rules; state residency; RMD birth-year treatment; benefits; suitability; and any restrictions or liquidity needs.

        **AI guardrail:** AI may assist workflow and explanation, but calculations are deterministic and assumptions are visible. No client PII should be placed in a model or transmitted to a third party without appropriate consent and controls.
        """)

st.divider(); st.caption("Advisor Transition Intelligence · transparent competition prototype · not financial, tax, legal or investment advice")

