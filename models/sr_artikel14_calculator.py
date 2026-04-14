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


def calculate_lb(bruto_per_periode, periodes, params, aftrek_bv_per_periode=0.0):
    """
    Berekent Artikel 14 loonbelasting en AOV per periode.

    :param bruto_per_periode: Bruto belastbaar loon per periode (GROSS)
    :param periodes: Aantal periodes per jaar (12 of 26)
    :param params: dict met alle belastingparameters (zie PARAM_KEYS)
    :param aftrek_bv_per_periode: Aftrek belastingvrij per periode (Art. 10f pensioenpremie)
    :returns: dict met alle tussenliggende bedragen
    """
    bruto_jaar = bruto_per_periode * periodes
    aftrek_bv_jaar = aftrek_bv_per_periode * periodes

    # Gecorrigeerd bruto na pensioenpremie aftrek (Art. 10f)
    adjusted_bruto_jaar = max(0.0, bruto_jaar - aftrek_bv_jaar)

    # Forfaitaire beroepskosten aftrek (Art. 12) — over gecorrigeerd bruto
    forfaitaire_jaar = min(
        adjusted_bruto_jaar * params['forfaitaire_pct'],
        params['forfaitaire_max'],
    )

    # Belastbaar jaarloon (Art. 13 + Art. 14)
    belastbaar_jaar = max(
        0.0,
        adjusted_bruto_jaar - params['belastingvrij_jaar'] - forfaitaire_jaar,
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

    # Heffingskorting — max gelijk aan bruto LB (geen terugbetaling)
    heffingskorting_jaar = params['hk_maand'] * 12
    heffingskorting_applied = min(heffingskorting_jaar, lb_voor_heffingskorting)

    # Bruto LB per periode (vóór HK) — voor SR_LB salarisregel
    lb_gross_per_periode = lb_voor_heffingskorting / periodes

    # Heffingskorting per periode — voor SR_HK salarisregel
    heffingskorting_per_periode = heffingskorting_applied / periodes

    # Netto LB per periode (na HK) — voor SR_LB_BIJZ marginaal tarief
    lb_jaar_netto = max(0.0, lb_voor_heffingskorting - heffingskorting_applied)
    lb_per_periode = lb_jaar_netto / periodes

    # AOV — ook over gecorrigeerd bruto (Art. 10f aftrek)
    effective_bruto_per_periode = max(0.0, bruto_per_periode - aftrek_bv_per_periode)
    franchise_periode = params['aov_franchise_maand'] if periodes == 12 else 0.0
    aov_grondslag = max(0.0, effective_bruto_per_periode - franchise_periode)
    aov_per_periode = aov_grondslag * params['aov_tarief']

    return {
        'bruto_per_periode': bruto_per_periode,
        'periodes': periodes,
        'bruto_jaar': bruto_jaar,
        'aftrek_bv_per_periode': aftrek_bv_per_periode,
        'aftrek_bv_jaar': aftrek_bv_jaar,
        'adjusted_bruto_jaar': adjusted_bruto_jaar,
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
        'heffingskorting_applied': heffingskorting_applied,
        'lb_gross_per_periode': lb_gross_per_periode,
        'heffingskorting_per_periode': heffingskorting_per_periode,
        'lb_jaar_netto': lb_jaar_netto,
        'lb_per_periode': lb_per_periode,
        # AOV
        'franchise_periode': franchise_periode,
        'aov_grondslag': aov_grondslag,
        'aov_tarief': params['aov_tarief'],
        'aov_per_periode': aov_per_periode,
    }


def generate_breakdown_html(result, wage, periodes, salary_type, kb_split=None,
                            vrijgesteld=0.0, inhoudingen=0.0):
    """
    Genereert een stap-voor-stap berekeningsoverzicht (debug panel) als HTML.

    :param result:        Volledige dict van calculate_lb()
    :param wage:          Basisloon per periode (contract.wage)
    :param periodes:      Aantal periodes (12 of 26)
    :param salary_type:   'monthly' of 'fn'
    :param kb_split:      dict {'belastbaar': x, 'vrijgesteld': y} of None
    :param vrijgesteld:   Vrijgestelde toelagen per periode (transport etc.)
    :param inhoudingen:   Inhoudingen per periode (ziektekostenpremie etc.)
    :returns: HTML string
    """
    def m(n, sign=''):
        """Formatteert getal met duizendpunten en 2 decimalen."""
        s = f"SRD {abs(n):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        if sign == '+':
            clr = '#16a34a' if n >= 0 else '#dc2626'
            prefix = '+' if n >= 0 else '−'
            return f'<span style="color:{clr}; font-weight:600;">{prefix} {s}</span>'
        if sign == '-':
            return f'<span style="color:#dc2626; font-weight:600;">− {s}</span>'
        return f'<span>{s}</span>'

    def row(label, formula, value, style=''):
        bg = f' style="background:{style};"' if style else ''
        return (
            f'<tr{bg}>'
            f'<td style="padding:3px 10px; color:#374151;">{label}</td>'
            f'<td style="padding:3px 10px; color:#6b7280; font-size:0.88em;">{formula}</td>'
            f'<td style="padding:3px 10px; text-align:right; font-family:monospace;">{value}</td>'
            f'</tr>'
        )

    def sep(title):
        return (
            f'<tr style="background:#e2e8f0;">'
            f'<td colspan="3" style="padding:4px 10px; font-weight:bold; color:#1e3a5f; '
            f'font-size:0.88em; letter-spacing:0.5px;">{title}</td>'
            f'</tr>'
        )

    def total_row(label, value, color='#1e40af'):
        return (
            f'<tr style="background:#eff6ff; border-top:2px solid #bfdbfe;">'
            f'<td colspan="2" style="padding:5px 10px; font-weight:bold; color:{color};">{label}</td>'
            f'<td style="padding:5px 10px; text-align:right; font-weight:bold; '
            f'font-family:monospace; color:{color}; font-size:1.05em;">'
            f'SRD {abs(result.get(value, 0)):,.2f}'.replace(",", "X").replace(".", ",").replace("X", ".") +
            f'</td></tr>'
        )

    def total_val(label, val_num, color='#1e40af'):
        s = f"SRD {abs(val_num):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return (
            f'<tr style="background:#eff6ff; border-top:2px solid #bfdbfe;">'
            f'<td colspan="2" style="padding:5px 10px; font-weight:bold; color:{color};">{label}</td>'
            f'<td style="padding:5px 10px; text-align:right; font-weight:bold; '
            f'font-family:monospace; color:{color}; font-size:1.05em;">{s}</td></tr>'
        )

    r = result
    loon_type_str = 'Maandloon (12×/jaar)' if salary_type == 'monthly' else 'Fortnight (26×/jaar)'
    kb = kb_split or {'belastbaar': 0.0, 'vrijgesteld': 0.0}
    kb_b = kb.get('belastbaar', 0.0)
    kb_v = kb.get('vrijgesteld', 0.0)
    gross_per_periode = wage + r.get('aftrek_bv_per_periode', 0.0) + 0.0  # original gross before aftrek

    # Netto berekening
    netto = (
        wage
        + kb_b + kb_v + vrijgesteld
        + r['heffingskorting_per_periode']
        - r['lb_gross_per_periode']
        - r['aov_per_periode']
        - inhoudingen
        - r.get('aftrek_bv_per_periode', 0.0)
    )

    rows = []

    # ─── Sectie 1: Bruto ───────────────────────────
    rows.append(sep('① BRUTO LOON (per periode)'))
    rows.append(row('Loontype', loon_type_str, m(wage)))
    if kb_b > 0 or kb_v > 0:
        rows.append(row('Kinderbijslag belastbaar deel', f'KB &gt; {periodes}×SRD 125/kind', m(kb_b)))
        rows.append(row('Kinderbijslag vrijgesteld deel', f'max SRD 125/kind/mnd', m(kb_v)))
    if vrijgesteld > 0:
        rows.append(row('Vrijgestelde toelagen', '(transport, maaltijd, ...)', m(vrijgesteld)))
    if r.get('aftrek_bv_per_periode', 0.0) > 0:
        rows.append(row('Pensioenpremie inhouding', 'aftrek_belastingvrij', m(r['aftrek_bv_per_periode'])))
    rows.append(row('<strong>GROSS belastbaar</strong>', f'{periodes} → jaarloon',
                    m(r['bruto_per_periode']), '#f0f9ff'))

    # ─── Sectie 2: Jaarloon & Forfaitair ───────────
    rows.append(sep('② BELASTBAAR JAARLOON (Art. 12 + 13)'))
    rows.append(row('Bruto jaarloon',
                    f"SRD {r['bruto_per_periode']:,.2f} × {periodes}".replace(",", "."),
                    m(r['bruto_jaar'])))
    if r.get('aftrek_bv_jaar', 0.0) > 0:
        rows.append(row('Aftrek belastingvrij (Art. 10f)',
                        f"SRD {r.get('aftrek_bv_per_periode', 0):.2f} × {periodes}",
                        m(r['aftrek_bv_jaar'], '-')))
        rows.append(row('Gecorrigeerd bruto', '(na aftrek)',
                        m(r['adjusted_bruto_jaar']), '#f0f9ff'))
    rows.append(row('Forfaitaire aftrek (Art. 12)',
                    f"{r['forfaitaire_pct']*100:.0f}% van jaarloon (max SRD {r.get('forfaitaire_jaar',0):,.0f})".replace(",", "."),
                    m(r['forfaitaire_jaar'], '-')))
    rows.append(row('Belastingvrije som (Art. 13)',
                    f"SRD {r['belastingvrij_jaar']:,.0f}/jaar".replace(",", "."),
                    m(r['belastingvrij_jaar'], '-')))
    rows.append(total_val('= Belastbaar Jaarloon', r['belastbaar_jaar']))

    # ─── Sectie 3: LB Schijven ─────────────────────
    rows.append(sep('③ LOONBELASTING SCHIJVEN (Art. 14)'))
    if r['s1_basis'] > 0:
        rows.append(row(f"Schijf 1 ({r['r1']*100:.0f}%)",
                        f"SRD {r['s1_basis']:,.0f} × {r['r1']*100:.0f}%".replace(",", "."),
                        m(r['lb_s1'])))
    if r['s2_basis'] > 0:
        rows.append(row(f"Schijf 2 ({r['r2']*100:.0f}%)",
                        f"SRD {r['s2_basis']:,.0f} × {r['r2']*100:.0f}%".replace(",", "."),
                        m(r['lb_s2'])))
    if r['s3_basis'] > 0:
        rows.append(row(f"Schijf 3 ({r['r3']*100:.0f}%)",
                        f"SRD {r['s3_basis']:,.0f} × {r['r3']*100:.0f}%".replace(",", "."),
                        m(r['lb_s3'])))
    if r['s4_basis'] > 0:
        rows.append(row(f"Schijf 4 ({r['r4']*100:.0f}%)",
                        f"SRD {r['s4_basis']:,.0f} × {r['r4']*100:.0f}%".replace(",", "."),
                        m(r['lb_s4'])))
    rows.append(row('<strong>LB jaar (vóór HK)</strong>', 'som schijven',
                    m(r['lb_voor_heffingskorting']), '#f0f9ff'))
    rows.append(row('Heffingskorting jaar',
                    f"min(SRD 750 × 12, LB jaar) = min(9.000, {r['lb_voor_heffingskorting']:,.0f})".replace(",", "."),
                    m(r['heffingskorting_applied'], '-')))
    rows.append(row('= LB jaar (netto, na HK)',
                    f"{r['lb_voor_heffingskorting']:,.0f} − {r['heffingskorting_applied']:,.0f}".replace(",", "."),
                    m(r['lb_jaar_netto'])))
    rows.append(row('──────────────────', 'Op loonstrook verschijnen SR_LB (bruto) + SR_HK (korting) apart:', ''))
    rows.append(row('<strong>SR_LB op loonstrook (bruto, vóór HK)</strong>',
                    f"{r['lb_voor_heffingskorting']:,.0f} ÷ {periodes} (SR_LB regel)".replace(",", "."),
                    m(r['lb_gross_per_periode']), '#fef9c3'))
    rows.append(row('<strong>SR_HK op loonstrook (korting)</strong>',
                    f"{r['heffingskorting_applied']:,.0f} ÷ {periodes} (SR_HK regel)".replace(",", "."),
                    m(r['heffingskorting_per_periode']), '#f0fdf4'))
    rows.append(row('Netto LB effect per periode',
                    f"{r['lb_gross_per_periode']:,.2f} − {r['heffingskorting_per_periode']:,.2f}".replace(",", "."),
                    m(r['lb_per_periode']), '#f0f9ff'))

    # ─── Sectie 4: AOV ─────────────────────────────
    rows.append(sep('④ AOV BIJDRAGE (4%)'))
    franchise_label = f"AOV franchise − SRD {r['franchise_periode']:,.0f}/periode".replace(",", ".") \
        if r['franchise_periode'] > 0 else 'Geen AOV franchise (Fortnight)'
    rows.append(row('Bruto per periode', '', m(r['bruto_per_periode'] - r.get('aftrek_bv_per_periode', 0.0))))
    if r['franchise_periode'] > 0:
        rows.append(row('Franchise (Art. 4 AOV)', franchise_label, m(r['franchise_periode'], '-')))
    rows.append(row('AOV grondslag', '', m(r['aov_grondslag']), '#f0f9ff'))
    rows.append(row('<strong>AOV per periode</strong>',
                    f"{r['aov_tarief']*100:.0f}% × SRD {r['aov_grondslag']:,.2f}".replace(",", "."),
                    m(r['aov_per_periode']), '#fef9c3'))

    # ─── Sectie 5: Netto Berekening ────────────────
    rows.append(sep('⑤ GESCHAT NETTOLOON PER PERIODE'))
    rows.append(row('Basisloon', '', m(wage, '+')))
    if kb_b > 0:
        rows.append(row('+ KB belastbaar deel', '', m(kb_b, '+')))
    if kb_v > 0:
        rows.append(row('+ KB vrijgesteld deel', '', m(kb_v, '+')))
    if vrijgesteld > 0:
        rows.append(row('+ Vrijgestelde toelagen', '', m(vrijgesteld, '+')))
    rows.append(row('− LB (Art. 14)', '', m(r['lb_gross_per_periode'], '-')))
    rows.append(row('+ Heffingskorting', '', m(r['heffingskorting_per_periode'], '+')))
    rows.append(row('− AOV (4%)', '', m(r['aov_per_periode'], '-')))
    if inhoudingen > 0:
        rows.append(row('− Inhoudingen (netto)', '', m(inhoudingen, '-')))
    if r.get('aftrek_bv_per_periode', 0.0) > 0:
        rows.append(row('− Aftrek belastingvrij', '(pensioenpremie e.d.)', m(r['aftrek_bv_per_periode'], '-')))
    rows.append(total_val('= Geschat Netto Loon', netto, '#065f46'))

    rows_html = ''.join(rows)
    return (
        '<div style="background:#0f172a; color:#e2e8f0; border-radius:6px; '
        'padding:8px 12px; margin-bottom:4px; font-size:0.82em; font-family:monospace;">'
        '<strong style="color:#7dd3fc;">&#9998; Art. 14 Berekening Debug Panel</strong>'
        '</div>'
        '<table style="width:100%; border-collapse:collapse; font-size:0.88em;">'
        '<thead>'
        '<tr style="background:#1e3a5f;">'
        '<th style="padding:4px 10px; text-align:left; color:#bfdbfe; width:38%;">Stap</th>'
        '<th style="padding:4px 10px; text-align:left; color:#bfdbfe; width:38%;">Formule</th>'
        '<th style="padding:4px 10px; text-align:right; color:#bfdbfe; width:24%;">Bedrag</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )


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
