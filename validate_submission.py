"""Pre-submission gate for required LPL competition deliverables."""
from pathlib import Path
import csv
import json
import sys
import zipfile
from pypdf import PdfReader

ROOT=Path(__file__).parent; REP=ROOT/"reports"; OUT=ROOT/"outputs"; DATA=ROOT/"data"
checks=[]
def check(name,condition,detail=""):
    checks.append((name,bool(condition),detail))

required=[ROOT/"app.py",ROOT/"advanced_engine.py",ROOT/"README.md",ROOT/"requirements.txt",ROOT/"launch_app.bat",ROOT/"tests"/"test_advanced_engine.py",DATA/"market_monthly_returns_2016_2026.csv",DATA/"data_sources.csv",OUT/"results.csv",OUT/"results.json",OUT/"inter_iit_lpl_submission_source.zip",OUT/"InterIIT_LPL_Submission.zip"]
for path in required: check(f"Exists: {path.name}",path.exists(),str(path))
for filename,limit in {"plan_and_solution_design.pdf":5,"technical_report.pdf":10,"client_proposal.pdf":5}.items():
    p=REP/filename
    pages=len(PdfReader(str(p)).pages) if p.exists() else 0
    check(f"Page limit: {filename}",0 < pages <= limit,f"{pages} pages / limit {limit}")

with open(OUT/"results.csv",newline="",encoding="utf-8") as f:
    rows=list(csv.DictReader(f))
schema={"strategy","transition_fraction","score","total_transition_cost","age90_median","age90_success","annualized_return","volatility","max_drawdown","liquidity"}
check("Results fixed schema",bool(rows) and schema.issubset(rows[0].keys()),f"{len(rows)} ranked options")
payload=json.loads((OUT/"results.json").read_text(encoding="utf-8"))
check("Results JSON explainability","persona" in payload and "ranking" in payload and "transition_cost_detail" in payload,"persona/ranking/cost detail present")
with zipfile.ZipFile(OUT/"inter_iit_lpl_submission_source.zip") as z:
    names=set(z.namelist())
check("Source bundle includes advanced engine",{"app.py","advanced_engine.py","README.md","tests/test_advanced_engine.py"}.issubset(names),"core source files included")
with zipfile.ZipFile(OUT/"InterIIT_LPL_Submission.zip") as z:
    names=set(z.namelist())
expected={"reports/plan_and_solution_design.pdf","reports/technical_report.pdf","reports/client_proposal.pdf","reports/final_presentation.pptx","outputs/inter_iit_lpl_submission_source.zip","outputs/results.csv","README.md","data/market_monthly_returns_2016_2026.csv"}
check("Final package includes deliverables",expected.issubset(names),f"{len(names)} packaged files")

for name,passed,detail in checks:
    print(f"{'PASS' if passed else 'FAIL'} | {name} | {detail}")
failed=[x for x in checks if not x[1]]
sys.exit(1 if failed else 0)

