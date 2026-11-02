"""Generate the complete Inter IIT / LPL submission pack from the v2 model."""
from pathlib import Path
import json, zipfile
import pandas as pd
from advanced_engine import default_holdings, optimise_transition, default_strategies, historical_returns, historical_metrics, rmd_age

ROOT=Path(__file__).parent; DATA=ROOT/"data"; REP=ROOT/"reports"; OUT=ROOT/"outputs"; REP.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
persona={"name":"Jordan & Casey - Near-retirement","current_age":52,"retirement_age":60,"annual_income":180000,"filing_status":"Married filing jointly","state_tax_rate":.04,"annual_withdrawal":70000,"inflation":.025,"social_security":42000,"ss_start_age":67,"retirement_other_income":0,"traditional_ira_share":300000/700000,"portfolio_value":700000}
holdings=default_holdings(); market=pd.read_csv(DATA/"market_monthly_returns_2016_2026.csv",parse_dates=["date"])
ranking,best=optimise_transition(persona,market,holdings)
ranking.to_csv(OUT/"results.csv",index=False)
(OUT/"results.json").write_text(json.dumps({"persona":persona,"ranking":ranking.to_dict(orient="records"),"recommended":best["strategy"],"transition_cost_detail":best["cost_detail"],"data_source":market.source.iloc[0]},indent=2,default=str),encoding="utf-8")

def money(x): return f"${float(x):,.0f}"
def pdf(path,title,subtitle,sections):
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak
    s=getSampleStyleSheet(); s.add(ParagraphStyle(name="Title2",parent=s["Title"],fontSize=24,leading=29,textColor=colors.HexColor("#123F63"),alignment=TA_CENTER)); s.add(ParagraphStyle(name="H2",parent=s["Heading2"],fontSize=14,leading=17,textColor=colors.HexColor("#0B1F3A"),spaceBefore=8,spaceAfter=5)); s.add(ParagraphStyle(name="Body2",parent=s["BodyText"],fontSize=8.7,leading=11.5,spaceAfter=4))
    story=[Spacer(1,60),Paragraph(title,s["Title2"]),Spacer(1,10),Paragraph(subtitle,s["Body2"]),Spacer(1,10),Paragraph("INTER IIT TECH MEET 15.0 · LPL FINANCIAL",s["Body2"]),PageBreak()]
    for heading,blocks in sections:
        story.append(Paragraph(heading,s["H2"]))
        for block in blocks:
            if isinstance(block,tuple) and block[0]=="table":
                rows=block[1]; data=[[Paragraph(str(v),s["Body2"]) for v in r] for r in rows]; t=Table(data,repeatRows=1)
                t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#123F63")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.HexColor("#CBD5E1")),("VALIGN",(0,0),(-1,-1),"TOP"),("LEFTPADDING",(0,0),(-1,-1),5),("RIGHTPADDING",(0,0),(-1,-1),5),("TOPPADDING",(0,0),(-1,-1),4),("BOTTOMPADDING",(0,0),(-1,-1),4)])); story.extend([t,Spacer(1,8)])
            else: story.append(Paragraph(block,s["Body2"]))
    story.extend([Spacer(1,12),Paragraph("Important: This competition prototype is decision support only. It is not financial, tax, legal or investment advice, and its results are not guarantees.",s["Body2"])])
    SimpleDocTemplate(str(path),pagesize=A4,leftMargin=40,rightMargin=40,topMargin=35,bottomMargin=35).build(story)

table=[["Strategy","Transition","Age-90 median","Resilience","Friction"],*[[r.strategy,f"{r.transition_fraction:.0%}",money(r.age90_median),f"{r.age90_success:.0%}",money(r.total_transition_cost)] for _,r in ranking.iterrows()]]
cost=best["cost_detail"]
cost_table=[["Component","Estimate"],["Taxable gains realised",money(cost["taxable_gains"])],["Annuity gains",money(cost["annuity_gains"])],["Federal capital-gains tax",money(cost["capital_gains_tax"])],["Ordinary tax on annuity gain",money(cost["ordinary_tax_on_annuity"])],["NIIT + state tax",money(cost["niit"]+cost["state_tax"])],["Exit + transaction costs",money(cost["exit_cost"]+cost["transaction_cost"])],["Total transition friction",money(cost["total"])]]

pdf(REP/"plan_and_solution_design.pdf","Advisor Transition Intelligence","Plan & Solution Design · transparent net-benefit decisions",[
 ("The decision problem",["A transition that wins on return can lose after taxes, surrender costs, fees, liquidity constraints and retirement sustainability. We build a reusable decision layer that makes these trade-offs visible."]),
 ("End-to-end workflow",["Persona and goals → holdings and tax lots → strategy candidates → account-aware transition friction → real-data back-test and stress tests → historical block-bootstrap retirement resilience → full/partial transition ranking → client-ready explanation.",("table",[["Layer","Design choice","Why it matters"],["Data","Account-aware holdings + cached public market proxies","Avoids a generic return-only comparison"],["Analytics","Visible tax/cost/risk/retirement calculations","Explainable and auditable"],["Decision","Current, full options and partial proposed blends","Can recommend nuance, not a forced switch"],["Safety","No PII storage, deterministic model, human review triggers","Responsible AI by construction"]])]),
 ("Success metrics",["Better net age-90 wealth, higher probability of non-depletion, transparent cost recovery, acceptable stress loss, strong liquidity, and an advisor-readable reason for the result."]),
 ("Data architecture",["The deliverable caches un-authenticated public monthly adjusted-close proxies (SPY, AGG, VXUS, VNQ) for reproducibility. Production use should replace these with licensed total-return data, product disclosures and account-level tax-lot feeds."])
])

pdf(REP/"technical_report.pdf","Advisor Transition Intelligence","Technical Report · implementation, assumptions and evaluation",[
 ("Implementation",["The Streamlit application collects an account-aware portfolio and persona, then invokes a deterministic Python engine. It evaluates the current strategy, two alternative strategies and three partial-transition levels. Automated unit tests cover progressive tax behaviour, RMD cohort timing, transition friction and optimiser output."]),
 ("Financial modelling",["Taxable sales distinguish long-term gains, short-term gains and realised losses (losses offset short-term gains first, then long-term gains). The model applies approximate 2026 federal schedules, NIIT and a state-rate input. Annuity gain is modelled as ordinary income; qualified-account transitions are not automatically taxed. Wash sales, loss carryforwards, municipal-bond treatment and contract-specific annuity riders are explicitly marked unsupported without specialist data. Retirement paths use 1,500 contiguous historical block-bootstrap samples of monthly factor returns, with inflation-linked spending, Social Security offset and RMD guardrails."]),
 ("Demo result",[("table",table),"The ranked result is scenario-specific. The product highlights when the score margin is narrow and requires a human to check tax lots, suitability, liquidity and product restrictions before acting."]),
 ("Historical evidence",["Metrics include annualised and cumulative return, volatility, maximum drawdown and a downside proxy. Stress windows include the February–March 2020 selloff and the 2022 inflation/rate shock. Historical evidence is explicitly framed as context, never a prediction."]),
 ("Sources and limitations",["IRS 2026 adjustments: https://www.irs.gov/irb/2025-45_IRB · IRS NIIT: https://www.irs.gov/taxtopics/tc559 · IRS RMD FAQ: https://www.irs.gov/retirement-plans/retirement-plan-and-ira-required-minimum-distributions-faqs · Data registry: `data/data_sources.csv`. Adjusted-close ETF proxies are a public demo dataset, not licensed client-reporting data."]),
 ("Responsible AI and compliance",["Before ranking, the model applies visible client constraints: transition-friction budget, maximum transition percentage and maximum historic-volatility ceiling. The app can export an advisor-acknowledged decision record with a model version and cryptographic audit hash. AI-assisted development is disclosed; the model makes no autonomous trade, has no PII persistence, displays assumptions and sources, and produces human-review triggers rather than false certainty."])
])

top=ranking.iloc[0]
pdf(REP/"client_proposal.pdf","Your investment-transition decision","Investor-ready scenario proposal · Jordan & Casey",[
 ("Your question",[f"Does moving a {money(persona['portfolio_value'])} portfolio create a better lifetime outcome after costs, taxes, risk and retirement income—not merely a better headline return?"]),
 ("Current model recommendation",[f"The leading scenario is **{top.strategy}** at a {top.transition_fraction:.0%} transition level. It estimates {money(top.total_transition_cost)} of all-in transition friction, a median age-90 portfolio value of {money(top.age90_median)}, and a {top.age90_success:.0%} probability of avoiding depletion in the simulated retirement paths.",("table",table)]),
 ("What we counted",[("table",cost_table),"We also compare historical volatility, maximum drawdown, liquidity and stress periods. Taxes, charges and product details must be checked against actual client records before a recommendation is implemented."]),
 ("What could change the answer",["Different tax lots or holding periods; state residency; annuity contract terms; actual surrender schedules; a lower risk tolerance; a larger liquidity reserve; changes to retirement spending, inflation or Social Security; or any product/account restriction."]),
 ("Next advisor actions",["Validate holdings and tax lots. Obtain product disclosures and surrender schedules. Confirm account-registration and rollover treatment. Review suitability and liquidity needs. Re-run the scenario with validated inputs and document the decision rationale."])
])

from pptx import Presentation
from pptx.util import Inches,Pt
from pptx.dml.color import RGBColor
prs=Presentation(); prs.slide_width=Inches(13.333); prs.slide_height=Inches(7.5); NAVY=RGBColor(8,28,52); BLUE=RGBColor(17,80,122); WHITE=RGBColor(255,255,255)
def slide(title,points,kicker="INTER IIT TECH MEET 15.0 · LPL FINANCIAL"):
    sl=prs.slides.add_slide(prs.slide_layouts[6]); b=sl.background.fill; b.solid(); b.fore_color.rgb=WHITE
    bar=sl.shapes.add_shape(1,0,0,Inches(13.333),Inches(.55)); bar.fill.solid(); bar.fill.fore_color.rgb=NAVY; bar.line.fill.background()
    t=sl.shapes.add_textbox(Inches(.65),Inches(.12),Inches(12),Inches(.3)).text_frame.paragraphs[0]; t.text=kicker; t.font.size=Pt(10); t.font.bold=True; t.font.color.rgb=WHITE
    h=sl.shapes.add_textbox(Inches(.7),Inches(.9),Inches(12),Inches(.8)).text_frame.paragraphs[0]; h.text=title; h.font.size=Pt(29); h.font.bold=True; h.font.color.rgb=NAVY
    tf=sl.shapes.add_textbox(Inches(.85),Inches(1.9),Inches(11.7),Inches(4.8)).text_frame; tf.word_wrap=True
    for i,pnt in enumerate(points):
        p=tf.paragraphs[0] if i==0 else tf.add_paragraph(); p.text=pnt; p.font.size=Pt(17 if i==0 else 15); p.font.color.rgb=BLUE if i==0 else NAVY; p.space_after=Pt(17)
slide("Advisor Transition Intelligence",["A transparent answer to: is this transition truly better for the client?","Net outcomes · account-aware taxes · retirement resilience · explainable trade-offs"])
slide("The advisor’s blind spot",["Higher expected returns are insufficient.","Taxes, surrender charges, advisory fees, liquidity, drawdowns and retirement income can reverse the decision."])
slide("Our solution",["One workflow: holdings → friction → evidence → retirement paths → recommendation.","It compares retain, full transition, research alternative and partial transition—not a binary switch."])
slide("Account-aware by design",["Taxable gains, annuity gains, IRAs, Roth assets, exit costs and transaction costs are modelled distinctly.","The decision record makes every material friction inspectable."])
slide("Evidence, not a promise",["Cached public adjusted-close proxies: SPY, AGG, VXUS, VNQ; Feb 2016–Oct 2026.","Annualised return, volatility, max drawdown and named stress windows are shown as evidence—not forecasts."])
slide("Retirement resilience",["1,500 historical block-bootstrap paths to age 90.","Inflation-linked spending, Social Security and RMD timing make the decision about sustainable income, not terminal value alone."])
slide("Partial transition optimisation",["The engine evaluates 0%, 25%, 50%, 75% and 100% proposed allocation.","This supports a more realistic response when taxes or risk make an all-or-nothing switch suboptimal."])
slide("Demo outcome",[f"Recommended: {top.strategy} ({top.transition_fraction:.0%} transition).",f"Estimated friction: {money(top.total_transition_cost)} · Median age-90 value: {money(top.age90_median)} · Resilience: {top.age90_success:.0%}","It remains a scenario, so advisor review triggers are shown—not hidden."])
slide("Responsible AI and governance",["No PII storage. Deterministic calculations. Visible sources and assumptions. No autonomous action.","The product prompts human validation of tax lots, disclosures, state treatment, suitability and liquidity."])
slide("Why this wins",["It solves the entire brief: financial rigor, allocation choice, back-test, tax, retirement, data transparency and an investor-ready explanation.","Live demo: change a cost, tax or spending assumption and watch the reasoned recommendation change."])
prs.save(REP/"final_presentation.pptx")

source_files=[ROOT/"app.py",ROOT/"advanced_engine.py",ROOT/"engine.py",ROOT/"build_submission.py",ROOT/"validate_submission.py",ROOT/"README.md",ROOT/"requirements.txt",ROOT/"launch_app.bat",ROOT/"tests"/"test_advanced_engine.py",DATA/"market_monthly_returns_2016_2026.csv",DATA/"market_data_dictionary.csv",DATA/"data_sources.csv",DATA/"synthetic_monthly_returns.csv",DATA/"data_dictionary.csv"]
with zipfile.ZipFile(OUT/"inter_iit_lpl_submission_source.zip","w",zipfile.ZIP_DEFLATED) as z:
    for f in source_files: z.write(f,f.relative_to(ROOT))
with zipfile.ZipFile(OUT/"InterIIT_LPL_Submission.zip","w",zipfile.ZIP_DEFLATED) as z:
    for f in [REP/"plan_and_solution_design.pdf",REP/"technical_report.pdf",REP/"client_proposal.pdf",REP/"final_presentation.pptx",OUT/"inter_iit_lpl_submission_source.zip",OUT/"results.csv",OUT/"results.json",ROOT/"README.md",DATA/"market_monthly_returns_2016_2026.csv",DATA/"market_data_dictionary.csv",DATA/"data_sources.csv"]: z.write(f,f.relative_to(ROOT))
print("Submission pack rebuilt.")

