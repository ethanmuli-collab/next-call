# Insights - who converts and when

_Narrative written by: offline template. Numbers computed by the EDA tool._

## Business summary

- The dataset holds **9,240 leads**; **38.5%** converted.
- **Engagement is the clearest signal:** leads who spent > 15 min on the site convert at 69.8%, versus 41.8% for 0 (never visited).
- **Lead origin:** lead_add_form converts at 92.5%, lead_import at 23.6%.
- **Occupation:** working_professional converts at 91.6%, unknown at 13.8%.
- **Source:** welingak_website converts at 98.6%, facebook at 23.6%.
- **Recommendation:** rank leads by predicted conversion instead of calling in list order, and treat time on site and lead origin as the first things a rep looks at.

## Facts used

| fact | value |
|---|---|
| rows | 9240 |
| labelled | 9240 |
| open_leads | 0 |
| conversion_rate | 0.3854 |
| median_time_on_site_sec | 248.0 |

**rate by lead origin**: lead_add_form 92.5%, landing_page_submission 36.2%, api 31.1%, lead_import 23.6%

**rate by lead source**: welingak_website 98.6%, reference 91.8%, unknown 80.6%, google 39.9%, organic_search 37.8%, direct_traffic 32.2%, olark_chat 25.5%, referral_sites 24.8%, facebook 23.6%

**rate by occupation**: working_professional 91.6%, unemployed 43.6%, student 37.1%, unknown 13.8%

**rate by specialization**: healthcare_management 49.7%, banking_investment_and_insurance 49.4%, marketing_management 48.7%, operations_management 47.3%, human_resource_management 45.8%, finance_management 44.7%, business_administration 44.4%, supply_chain_management 43.3%, rural_and_agribusiness 42.5%, hospitality_management 42.1%, media_and_advertising 41.9%, it_projects_management 38.2%, e_business 36.8%, international_business 36.0%, e_commerce 35.7%, travel_and_tourism 35.5%, retail_management 34.0%, not_selected 28.7%, services_excellence 27.5%

**rate by do not email**: 0 40.5%, 1 16.1%

**rate by free copy requested**: 0 39.9%, 1 35.7%

**rate by time on site**: 0 (never visited) 41.8%, < 1 min 13.7%, 1-5 min 14.1%, 5-15 min 32.0%, > 15 min 69.8%

Full charts: `eda_report.html`.
