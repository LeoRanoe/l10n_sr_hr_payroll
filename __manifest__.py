# Part of Odoo. See LICENSE file for full copyright and licensing details.
{
    'name': 'Suriname - Payroll (Wet Loonbelasting)',
    'version': '18.0.2.1.0',
    'author': 'RPBG - Stage Opdracht 2026',
    'countries': ['sr'],
    'category': 'Human Resources/Payroll',
    'summary': 'Loonverwerking conform de Wet Loonbelasting Suriname',
    'description': """
Suriname Payroll Module (Wet Loonbelasting)
============================================
Loonbelasting berekening conform de Wet Loonbelasting Suriname 2026
(Art. 14 progressief tarief, Art. 17 bijzondere beloningen,
Art. 17c overwerk, Art. 10 vrijstellingen).

Ondersteunde verloningstypes:
- Maandloon      (12 periodes per jaar)
- Fortnight Loon (26 periodes per jaar)

Berekeningen:
- Bruto loon (maandloon + belastbare toelagen)
- Forfaitaire beroepskosten aftrek (4%% van bruto, max SRD 4.800/jaar)
- Belastingvrije voet (SRD 108.000/jaar)
- Belastbaar jaarloon (na aftrekken)
- Loonbelasting Artikel 14 (progressieve schijven via SR-parameters)
- AOV bijdrage (actief tarief en franchise via SR-parameters)
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
        'data/hr_payslip_input_type_data.xml',
        'data/hr_contract_sr_line_type_data.xml',
        'views/hr_contract_views.xml',
        'views/hr_payslip_input_type_views.xml',
        'views/hr_payroll_dashboard_views.xml',
        'views/hr_payroll_config_sr_views.xml',
        'views/hr_work_entry_views.xml',
        'views/hr_payroll_help_views.xml',
        'views/sr_help_template.xml',
        'reports/report_payslip_sr.xml',
    ],
    'demo': [],
    'license': 'LGPL-3',
    'installable': True,
    'auto_install': False,
    'application': False,
}
