import unittest
from pathlib import Path
import pandas as pd
from advanced_engine import (ordinary_income_tax, long_term_capital_gains_tax, niit, rmd_age,
                             transition_cost, default_holdings, optimise_transition)

ROOT=Path(__file__).resolve().parents[1]

class FinancialModelTests(unittest.TestCase):
    def test_progressive_tax_increases(self):
        self.assertGreater(ordinary_income_tax(200000,"Single"), ordinary_income_tax(100000,"Single"))

    def test_ltcg_and_niit_are_non_negative(self):
        self.assertGreaterEqual(long_term_capital_gains_tax(180000,50000,"Married filing jointly"),0)
        self.assertGreaterEqual(niit(300000,50000,"Married filing jointly"),0)

    def test_rmd_age_by_birth_cohort(self):
        self.assertEqual(rmd_age(52),75)
        self.assertEqual(rmd_age(74),73)

    def test_taxable_transition_has_friction(self):
        cost=transition_cost(default_holdings(),1,180000,"Married filing jointly",.04)
        self.assertGreater(cost["total"],0)
        self.assertGreater(cost["capital_gains_tax"],0)

    def test_tax_losses_offset_taxable_gains(self):
        lots=pd.DataFrame([
            {"holding":"gain","value":200,"basis":100,"account_type":"Taxable","holding_period":"Long-term","exit_cost_rate":0,"transaction_cost_rate":0},
            {"holding":"loss","value":100,"basis":180,"account_type":"Taxable","holding_period":"Long-term","exit_cost_rate":0,"transaction_cost_rate":0},
        ])
        cost=transition_cost(lots,1,100000,"Single",0)
        self.assertEqual(cost["tax_losses_harvested"],80)
        self.assertLess(cost["capital_gains_tax"],long_term_capital_gains_tax(100000,100,"Single"))

    def test_optimizer_returns_a_ranked_result(self):
        market=pd.read_csv(ROOT/"data"/"market_monthly_returns_2016_2026.csv")
        persona={"current_age":52,"retirement_age":60,"portfolio_value":700000,"annual_income":180000,
                 "filing_status":"Married filing jointly","state_tax_rate":.04,"annual_withdrawal":70000,
                 "inflation":.025,"social_security":42000,"ss_start_age":67,"retirement_other_income":0,
                 "traditional_ira_share":300000/700000}
        ranking,best=optimise_transition(persona,market,default_holdings())
        self.assertEqual(len(ranking),6)
        self.assertIn("strategy",best)
        self.assertGreaterEqual(best["age90_success"],0)

    def test_constraints_keep_ineligible_options_from_winning(self):
        market=pd.read_csv(ROOT/"data"/"market_monthly_returns_2016_2026.csv")
        persona={"current_age":52,"retirement_age":60,"portfolio_value":700000,"annual_income":180000,"filing_status":"Married filing jointly","state_tax_rate":.04,"annual_withdrawal":70000,"inflation":.025,"social_security":42000,"ss_start_age":67,"retirement_other_income":0,"traditional_ira_share":300000/700000,"tax_budget":0,"max_transition_fraction":1,"max_volatility":.5}
        ranking,best=optimise_transition(persona,market,default_holdings())
        self.assertTrue(ranking.iloc[0].eligible)
        self.assertEqual(best["transition_fraction"],0)

if __name__ == "__main__":
    unittest.main()

