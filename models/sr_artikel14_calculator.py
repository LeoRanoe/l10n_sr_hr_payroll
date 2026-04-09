# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Artikel 14 Wet Loonbelasting Suriname — Centrale Calculator

Eén implementatie van het Art. 14 tariefmechanisme, gebruikt door:
  - hr.contract._compute_sr_preview()       (contract tab)
  - hr.payslip._get_sr_artikel14_breakdown() (loonstrook rapport)
  - hr.payslip._sr_artikel14_lb()           (SR_LB salarisregel)

Parameters worden door de aanroeper verstrekt zodat deze module
geen afhankelijkheid heeft op hr.rule.parameter of andere Odoo modellen.
"""

# Benodigde parametersleutels voor de calculator
PARAM_KEYS = [
    'belastingvrij_jaar',
    'forfaitaire_pct',
    'forfaitaire_max',
    's1', 's2', 's3',
    'r1', 'r2', 'r3', 'r4',
    'hk_maand',
    'aov_tarief',
    'aov_franchise_maand',
]

# Mapping van hr.rule.parameter codes naar calculator-sleutels
PARAM_CODE_MAP = {
    'SR_BELASTINGVRIJ_JAAR': 'belastingvrij_jaar',
    'SR_FORFAITAIRE_PCT': 'forfaitaire_pct',
    'SR_FORFAITAIRE_MAX_JAAR': 'forfaitaire_max',
    'SR_SCHIJF_1_GRENS': 's1',
    'SR_SCHIJF_2_GRENS': 's2',
    'SR_SCHIJF_3_GRENS': 's3',
    'SR_TARIEF_1': 'r1',
    'SR_TARIEF_2': 'r2',
    'SR_TARIEF_3': 'r3',
    'SR_TARIEF_4': 'r4',
    'SR_HEFFINGSKORTING_MAAND': 'hk_maand',
    'SR_AOV_TARIEF': 'aov_tarief',
    'SR_AOV_FRANCHISE_MAAND': 'aov_franchise_maand',
}


def fetch_params_from_rule_parameter(env, ref_date):
    """
    Haalt alle benodigde Art. 14 parameters op via hr.rule.parameter.

    :param env: Odoo Environment
    :param ref_date: Datum voor parameter lookup
    :returns: dict met calculator-sleutels
    :raises: UserError als een parameter ontbreekt
    """
    RuleParam = env['hr.rule.parameter']
    params = {}
    for code, key in PARAM_CODE_MAP.items():
        params[key] = RuleParam._get_parameter_from_code(
            code, ref_date, raise_if_not_found=True,
        )
    return params


def fetch_params_from_payslip(payslip):
    """
    Haalt alle benodigde Art. 14 parameters op via payslip._rule_parameter().

    :param payslip: hr.payslip singleton
    :returns: dict met calculator-sleutels
    """
    params = {}
    for code, key in PARAM_CODE_MAP.items():
        params[key] = payslip._rule_parameter(code)
    return params


def calculate_lb(bruto_per_periode, periodes, params):
    """
    Berekent Artikel 14 loonbelasting en AOV per periode.

    :param bruto_per_periode: Bruto belastbaar loon per periode (GROSS)
    :param periodes: Aantal periodes per jaar (12 of 26)
    :param params: dict met alle belastingparameters (zie PARAM_KEYS)
    :returns: dict met alle tussenliggende bedragen
    """
    bruto_jaar = bruto_per_periode * periodes

    # Forfaitaire beroepskosten aftrek (Art. 12)
    forfaitaire_jaar = min(
        bruto_jaar * params['forfaitaire_pct'],
        params['forfaitaire_max'],
    )

    # Belastbaar jaarloon (Art. 13 + Art. 14)
    belastbaar_jaar = max(
        0.0,
        bruto_jaar - params['belastingvrij_jaar'] - forfaitaire_jaar,
    )

    # Tariefschijven (Art. 14)
    s1 = params['s1']
    s2 = params['s2']
    s3 = params['s3']
    r1 = params['r1']
    r2 = params['r2']
    r3 = params['r3']
    r4 = params['r4']

    s1_basis = min(belastbaar_jaar, s1)
    s2_basis = max(0.0, min(belastbaar_jaar - s1, s2 - s1))
    s3_basis = max(0.0, min(belastbaar_jaar - s2, s3 - s2))
    s4_basis = max(0.0, belastbaar_jaar - s3)

    lb_s1 = s1_basis * r1
    lb_s2 = s2_basis * r2
    lb_s3 = s3_basis * r3
    lb_s4 = s4_basis * r4
    lb_voor_heffingskorting = lb_s1 + lb_s2 + lb_s3 + lb_s4

    # Heffingskorting
    heffingskorting_jaar = params['hk_maand'] * 12
    lb_jaar_netto = max(0.0, lb_voor_heffingskorting - heffingskorting_jaar)
    lb_per_periode = lb_jaar_netto / periodes

    # AOV
    franchise_periode = params['aov_franchise_maand'] if periodes == 12 else 0.0
    aov_grondslag = max(0.0, bruto_per_periode - franchise_periode)
    aov_per_periode = aov_grondslag * params['aov_tarief']

    return {
        'bruto_per_periode': bruto_per_periode,
        'periodes': periodes,
        'bruto_jaar': bruto_jaar,
        'forfaitaire_pct': params['forfaitaire_pct'],
        'forfaitaire_jaar': forfaitaire_jaar,
        'belastingvrij_jaar': params['belastingvrij_jaar'],
        'belastbaar_jaar': belastbaar_jaar,
        # Schijfgrenzen
        's1': s1, 's2': s2, 's3': s3,
        # Tarieven
        'r1': r1, 'r2': r2, 'r3': r3, 'r4': r4,
        # Schijfbedragen
        's1_basis': s1_basis,
        's2_basis': s2_basis,
        's3_basis': s3_basis,
        's4_basis': s4_basis,
        # Belasting per schijf
        'lb_s1': lb_s1,
        'lb_s2': lb_s2,
        'lb_s3': lb_s3,
        'lb_s4': lb_s4,
        'lb_voor_heffingskorting': lb_voor_heffingskorting,
        'heffingskorting_jaar': heffingskorting_jaar,
        'lb_jaar_netto': lb_jaar_netto,
        'lb_per_periode': lb_per_periode,
        # AOV
        'franchise_periode': franchise_periode,
        'aov_grondslag': aov_grondslag,
        'aov_tarief': params['aov_tarief'],
        'aov_per_periode': aov_per_periode,
    }


def generate_tax_bracket_html(params):
    """
    Genereert een HTML-tabel van de tariefschijven op basis van parameters.

    :param params: dict met s1, s2, s3, r1, r2, r3, r4, belastingvrij_jaar,
                   forfaitaire_pct, forfaitaire_max, hk_maand
    :returns: HTML string
    """
    def fmt(n):
        """Format number as SRD with thousand separator."""
        return f"SRD {n:,.0f}".replace(",", ".")

    def pct(n):
        return f"{n * 100:.0f}%"

    colors = ['#16a34a', '#d97706', '#dc2626', '#7c3aed']
    rows_data = [
        ('1', f"t/m {fmt(params['s1'])}", pct(params['r1']), colors[0]),
        ('2', f"{fmt(params['s1'] + 1)} – {fmt(params['s2'])}", pct(params['r2']), colors[1]),
        ('3', f"{fmt(params['s2'] + 1)} – {fmt(params['s3'])}", pct(params['r3']), colors[2]),
        ('4', f"Boven {fmt(params['s3'])}", pct(params['r4']), colors[3]),
    ]

    rows_html = ""
    for i, (schijf, bereik, tarief, color) in enumerate(rows_data):
        bg = ' style="background: #f8fafc;"' if i % 2 == 1 else ''
        rows_html += (
            f'<tr{bg}>'
            f'<td style="padding: 4px 10px; border: 1px solid #e2e8f0;">{schijf}</td>'
            f'<td style="padding: 4px 10px; border: 1px solid #e2e8f0;">{bereik}</td>'
            f'<td style="padding: 4px 10px; text-align: center; border: 1px solid #e2e8f0; '
            f'font-weight: bold; color: {color};">{tarief}</td>'
            f'</tr>'
        )

    forfaitaire_max = params.get('forfaitaire_max', 0)

    return (
        '<table style="width: 100%; border-collapse: collapse; font-size: 0.9em;">'
        '<thead>'
        '<tr style="background: #f1f5f9; font-weight: bold; color: #475569;">'
        '<th style="padding: 5px 10px; text-align: left; border: 1px solid #e2e8f0;">Schijf</th>'
        '<th style="padding: 5px 10px; text-align: left; border: 1px solid #e2e8f0;">Belastbaar Jaarloon</th>'
        '<th style="padding: 5px 10px; text-align: center; border: 1px solid #e2e8f0;">Tarief</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
        '<p class="text-muted" style="font-size: 0.85em; margin-top: 6px; margin-bottom: 0;">'
        f'<strong>Art. 12:</strong> Forfaitaire aftrek {pct(params["forfaitaire_pct"])} van jaarloon '
        f'(max {fmt(forfaitaire_max)}) · '
        f'<strong>Art. 13:</strong> Belastingvrije som {fmt(params["belastingvrij_jaar"])}/jaar · '
        f'<strong>Heffingskorting:</strong> {fmt(params["hk_maand"])}/maand · '
        '<strong>Overwerk Art. 17c:</strong> 5% / 15% / 25%'
        '</p>'
    )
