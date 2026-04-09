# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Suriname - Payroll (Artikel 14 Wet Loonbelasting)',
    'version': '18.0.1.0.0',
    'author': 'RPBG - Stage Opdracht 2026',
    'countries': ['sr'],
    'category': 'Human Resources/Payroll',
    'summary': 'Loonverwerking conform Artikel 14 Wet Loonbelasting Suriname',
    'description': """
Suriname Payroll Module (Artikel 14 Wet Loonbelasting)
======================================================
Loonbelasting berekening conform Artikel 14 van de Wet Loonbelasting Suriname 2026.

Ondersteunde verloningstypes:
- Maandloon      (12 periodes per jaar)
- Fortnight Loon (26 periodes per jaar)

Berekeningen:
- Bruto loon (maandloon + belastbare toelagen)
- Forfaitaire beroepskosten aftrek (4%% van bruto, max SRD 4.800/jaar)
- Belastingvrije voet (SRD 108.000/jaar)
- Belastbaar jaarloon (na aftrekken)
- Loonbelasting Artikel 14 (schijven: 8%% / 18%% / 28%% / 38%%)
- Heffingskorting (SRD 750/maand)
- AOV bijdrage (4%% over belastbaar minus franchise SRD 400/maand)
- Pensioenpremie bijdrage
- Kinderbijslag (belastingvrij)
- Netto loon
    """,
    'depends': ['hr_payroll'],
    'assets': {
        'web.assets_backend': [
            'l10n_sr_hr_payroll/static/src/css/l10n_sr_payroll.css',
        ],
    },
    'data': [
        'security/ir.model.access.csv',
        'data/hr_payroll_structure_type_data.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_rule_parameter_data.xml',
        'data/hr_salary_rule_data.xml',
        'views/hr_contract_views.xml',
        'views/hr_payroll_dashboard_views.xml',
        'reports/report_payslip_sr.xml',
    ],
    'demo': [],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
