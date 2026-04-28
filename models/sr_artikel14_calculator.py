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

import re
from decimal import Decimal, ROUND_HALF_UP

from odoo.exceptions import UserError

# Benodigde parametersleutels voor de calculator
PARAM_KEYS = [
    'belastingvrij_jaar',
    'forfaitaire_pct',
    'forfaitaire_max',
    'brackets',
    's1', 's2', 's3',
    'r1', 'r2', 'r3', 'r4',
    'aov_tarief',
    'aov_franchise_maand',
]

BRACKET_LIMIT_CODE_RE = re.compile(r'^SR_SCHIJF_(\d+)_GRENS$')
BRACKET_RATE_CODE_RE = re.compile(r'^SR_TARIEF_(\d+)$')

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
    'SR_AOV_TARIEF': 'aov_tarief',
    'SR_AOV_FRANCHISE_MAAND': 'aov_franchise_maand',
}

CONFIG_PARAMETER_MAP = {
    'SR_BELASTINGVRIJ_JAAR': ('sr_payroll.belastingvrij_jaar', 0.0),
    'SR_FORFAITAIRE_PCT': ('sr_payroll.forfaitaire_pct', 0.04),
    'SR_FORFAITAIRE_MAX_JAAR': ('sr_payroll.forfaitaire_max_jaar', 4800.0),
    'SR_SCHIJF_1_GRENS': ('sr_payroll.schijf_1_grens', 42000.0),
    'SR_SCHIJF_2_GRENS': ('sr_payroll.schijf_2_grens', 84000.0),
    'SR_SCHIJF_3_GRENS': ('sr_payroll.schijf_3_grens', 126000.0),
    'SR_TARIEF_1': ('sr_payroll.tarief_1', 0.08),
    'SR_TARIEF_2': ('sr_payroll.tarief_2', 0.18),
    'SR_TARIEF_3': ('sr_payroll.tarief_3', 0.28),
    'SR_TARIEF_4': ('sr_payroll.tarief_4', 0.38),
    'SR_AOV_TARIEF': ('sr_payroll.aov_tarief', 0.04),
    'SR_AOV_FRANCHISE_MAAND': ('sr_payroll.aov_franchise_maand', 400.0),
    'SR_KINDBIJ_MAX_KIND_MAAND': ('sr_payroll.akb_per_kind', 250.0),
    'SR_KINDBIJ_MAX_MAAND': ('sr_payroll.akb_max_bedrag', 1000.0),
    'SR_BIJZ_VRIJSTELLING_MAX': ('sr_payroll.bijz_beloning_max', 19500.0),
    'SR_OWK_SCHIJF_1_GRENS': ('sr_payroll.overwerk_schijf_1_grens', 2500.0),
    'SR_OWK_SCHIJF_2_GRENS': ('sr_payroll.overwerk_schijf_2_grens', 7500.0),
    'SR_OWK_TARIEF_1': ('sr_payroll.overwerk_tarief_1', 0.05),
    'SR_OWK_TARIEF_2': ('sr_payroll.overwerk_tarief_2', 0.15),
    'SR_OWK_TARIEF_3': ('sr_payroll.overwerk_tarief_3', 0.25),
    'SR_HEFFINGSKORTING': ('sr_payroll.heffingskorting', 750.0),
}

MONEY_QUANT = Decimal('0.01')
WHOLE_QUANT = Decimal('1')
ZERO = Decimal('0')


def is_missing_parameter_value(value):
    return value is None or value is False or value == ''


def _to_decimal(value):
    if isinstance(value, Decimal):
        return value
    if is_missing_parameter_value(value):
        return ZERO
    return Decimal(str(value))


def _quantize(value, quant=MONEY_QUANT):
    return _to_decimal(value).quantize(quant, rounding=ROUND_HALF_UP)


def round_money(value):
    return float(_quantize(value))


def _round_number(value, digits=2):
    quant = WHOLE_QUANT if digits <= 0 else Decimal('1').scaleb(-digits)
    return _quantize(value, quant)


def _format_number(value, digits=2):
    rounded = _round_number(value, digits)
    return f'{abs(rounded):,.{digits}f}'.replace(',', 'X').replace('.', ',').replace('X', '.')


def format_srd(value, digits=2):
    return f'SRD {_format_number(value, digits)}'


def get_config_parameter_key(code):
    return CONFIG_PARAMETER_MAP.get(code, (None, None))[0]


def get_config_parameter_default(code):
    return CONFIG_PARAMETER_MAP.get(code, (None, None))[1]


def normalize_config_parameter_value(code, value):
    if is_missing_parameter_value(value):
        return value
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return value

    if code == 'SR_BELASTINGVRIJ_JAAR' and numeric_value == 108000.0 and get_config_parameter_default(code) == 0.0:
        return 0.0
    return numeric_value


def get_config_parameter_value(env, code, default=None):
    config_key = get_config_parameter_key(code)
    if not config_key:
        return default

    fallback = get_config_parameter_default(code) if default is None else default
    value = env['ir.config_parameter'].sudo().get_param(config_key)
    if is_missing_parameter_value(value):
        return fallback
    normalized_value = normalize_config_parameter_value(code, value)
    try:
        return float(normalized_value)
    except (TypeError, ValueError):
        return fallback


def get_sr_parameter_value(env, code, ref_date, default=None, raise_if_not_found=True):
    value = env['hr.rule.parameter']._get_parameter_from_code(
        code, ref_date, raise_if_not_found=False,
    )
    if not is_missing_parameter_value(value):
        return value

    config_value = get_config_parameter_value(env, code, default=None)
    if config_value is not None:
        return config_value

    if default is not None:
        return default
    if raise_if_not_found:
        raise UserError(f'Missing parameter: {code}')
    if is_missing_parameter_value(value):
        return default
    return value


def _raise_configuration_error(code, context_label, original_error=None):
    config_key = get_config_parameter_key(code)
    message = f"SR Payroll configuratieparameter '{code}' ontbreekt of is ongeldig"
    if config_key:
        message += f" (verwachte sleutel: '{config_key}')"
    if context_label:
        message += f" voor {context_label}"
    message += '. Controleer SR Payroll Instellingen of de referentieparameterhistorie.'
    raise UserError(message) from original_error


def _collect_dynamic_brackets(code_names, get_value):
    """
    Bouwt de reguliere Art. 14 schijven dynamisch op uit SR_SCHIJF_* en
    SR_TARIEF_* parameters zodat extra schijven via nieuwe records mogelijk zijn.
    """
    threshold_entries = []
    rate_entries = []

    for code in code_names:
        threshold_match = BRACKET_LIMIT_CODE_RE.match(code)
        if threshold_match:
            try:
                value = get_value(code)
            except UserError:
                # Reserve/toekomstige schijfcodes zonder actuele waarde
                # mogen de huidige payrollberekening niet blokkeren.
                continue
            if value is None or value is False or value == '':
                continue
            threshold_entries.append((int(threshold_match.group(1)), value))
            continue

        rate_match = BRACKET_RATE_CODE_RE.match(code)
        if rate_match:
            try:
                value = get_value(code)
            except UserError:
                continue
            if value is None or value is False or value == '':
                continue
            rate_entries.append((int(rate_match.group(1)), value))

    threshold_entries.sort(key=lambda item: item[0])
    rate_entries.sort(key=lambda item: item[0])

    if not threshold_entries or not rate_entries:
        raise UserError('SR Art. 14 parameters ontbreken: schijfgrenzen of tarieven niet gevonden.')

    expected_threshold_indexes = list(range(1, len(threshold_entries) + 1))
    actual_threshold_indexes = [index for index, _value in threshold_entries]
    if actual_threshold_indexes != expected_threshold_indexes:
        raise UserError(
            'SR Art. 14 schijfgrenzen moeten opeenvolgend genummerd zijn '
            '(SR_SCHIJF_1_GRENS, SR_SCHIJF_2_GRENS, ...).'
        )

    expected_rate_indexes = list(range(1, len(rate_entries) + 1))
    actual_rate_indexes = [index for index, _value in rate_entries]
    if actual_rate_indexes != expected_rate_indexes:
        raise UserError(
            'SR Art. 14 tarieven moeten opeenvolgend genummerd zijn '
            '(SR_TARIEF_1, SR_TARIEF_2, ...).'
        )

    thresholds = [value for _index, value in threshold_entries]
    rates = [value for _index, value in rate_entries]

    if len(rates) != len(thresholds) + 1:
        raise UserError(
            'SR Art. 14 configuratie ongeldig: aantal tarieven moet exact één hoger '
            'zijn dan het aantal schijfgrenzen.'
        )

    previous_threshold = None
    for threshold in thresholds:
        if previous_threshold is not None and threshold <= previous_threshold:
            raise UserError('SR Art. 14 schijfgrenzen moeten strikt oplopend zijn.')
        previous_threshold = threshold

    brackets = []
    previous_lower = 0.0
    for index, rate in enumerate(rates, start=1):
        upper = thresholds[index - 1] if index <= len(thresholds) else None
        brackets.append({
            'index': index,
            'lower': previous_lower,
            'upper': upper,
            'rate': rate,
        })
        if upper is not None:
            previous_lower = upper

    return brackets


def _pad_legacy_bracket_fields(params):
    """Behoudt de bestaande s1/s2/s3 en r1/r2/r3/r4 sleutels voor compatibiliteit."""
    brackets = params['brackets']
    threshold_values = [row['upper'] for row in brackets if row['upper'] is not None]

    for index in range(1, 4):
        params[f's{index}'] = threshold_values[index - 1] if len(threshold_values) >= index else 0.0

    for index in range(1, 5):
        params[f'r{index}'] = brackets[index - 1]['rate'] if len(brackets) >= index else 0.0

    return params


def _legacy_bracket_fields(result, bracket_rows):
    """Vult de bestaande breakdown-sleutels voor de eerste vier schijven op."""
    threshold_values = [row['upper'] for row in bracket_rows if row['upper'] is not None]

    for index in range(1, 4):
        result[f's{index}'] = threshold_values[index - 1] if len(threshold_values) >= index else 0.0

    for index in range(1, 5):
        row = bracket_rows[index - 1] if len(bracket_rows) >= index else None
        result[f'r{index}'] = row['rate'] if row else 0.0
        result[f's{index}_basis'] = row['basis'] if row else 0.0
        result[f'lb_s{index}'] = row['tax'] if row else 0.0

    return result


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
        try:
            params[key] = get_sr_parameter_value(
                env, code, ref_date, raise_if_not_found=True,
            )
        except UserError as error:
            _raise_configuration_error(code, ref_date.isoformat(), error)
    code_names = RuleParam.search([('code', 'like', 'SR_')]).mapped('code')
    try:
        params['brackets'] = _collect_dynamic_brackets(
            code_names,
            lambda code: get_sr_parameter_value(env, code, ref_date, raise_if_not_found=True),
        )
    except UserError as error:
        raise UserError(
            f'SR Payroll schijfconfiguratie is ongeldig voor {ref_date.isoformat()}. {error}'
        ) from error
    return _pad_legacy_bracket_fields(params)


def fetch_params_from_payslip(payslip):
    """
    Haalt alle benodigde Art. 14 parameters op via payslip._rule_parameter().

    :param payslip: hr.payslip singleton
    :returns: dict met calculator-sleutels
    """
    params = {}
    for code, key in PARAM_CODE_MAP.items():
        try:
            params[key] = payslip._rule_parameter(code)
        except (UserError, KeyError, TypeError, ValueError) as error:
            context_label = payslip.date_to.isoformat() if payslip.date_to else 'deze loonstrook'
            _raise_configuration_error(code, context_label, error)
    code_names = payslip.env['hr.rule.parameter'].search([('code', 'like', 'SR_')]).mapped('code')
    try:
        params['brackets'] = _collect_dynamic_brackets(
            code_names,
            payslip._rule_parameter,
        )
    except UserError as error:
        context_label = payslip.date_to.isoformat() if payslip.date_to else 'deze loonstrook'
        raise UserError(
            f'SR Payroll schijfconfiguratie is ongeldig voor {context_label}. {error}'
        ) from error
    return _pad_legacy_bracket_fields(params)


def calculate_lb(
    bruto_per_periode,
    periodes,
    params,
    aftrek_bv_per_periode=0.0,
    heffingskorting_per_periode=0.0,
):
    """
    Berekent Artikel 14 loonbelasting en AOV per periode.

    :param bruto_per_periode: Bruto belastbaar loon per periode (GROSS)
    :param periodes: Aantal periodes per jaar (12 of 26)
    :param params: dict met alle belastingparameters (zie PARAM_KEYS)
    :param aftrek_bv_per_periode: Aftrek belastingvrij per periode (Art. 10f pensioenpremie)
    :returns: dict met alle tussenliggende bedragen
    """
    if periodes <= 0:
        raise UserError('SR Art. 14 berekening vereist een positief aantal periodes per jaar.')

    bruto_per_periode_dec = _to_decimal(bruto_per_periode)
    periodes_dec = _to_decimal(periodes)
    aftrek_bv_per_periode_dec = _to_decimal(aftrek_bv_per_periode)
    heffingskorting_per_periode_dec = _to_decimal(heffingskorting_per_periode)
    forfaitaire_pct = _to_decimal(params['forfaitaire_pct'])
    forfaitaire_max = _to_decimal(params['forfaitaire_max'])
    belastingvrij_jaar = _to_decimal(params['belastingvrij_jaar'])
    aov_tarief = _to_decimal(params['aov_tarief'])
    aov_franchise_maand = _to_decimal(params['aov_franchise_maand'])

    bruto_jaar = bruto_per_periode_dec * periodes_dec
    aftrek_bv_jaar = aftrek_bv_per_periode_dec * periodes_dec
    adjusted_bruto_per_periode = max(ZERO, bruto_per_periode_dec - aftrek_bv_per_periode_dec)

    # Gecorrigeerd bruto na pensioenpremie aftrek (Art. 10f)
    adjusted_bruto_jaar = max(ZERO, bruto_jaar - aftrek_bv_jaar)

    # Forfaitaire beroepskosten aftrek (Art. 12) — over gecorrigeerd bruto
    forfaitaire_jaar = min(
        adjusted_bruto_jaar * forfaitaire_pct,
        forfaitaire_max,
    )
    forfaitaire_per_periode = forfaitaire_jaar / periodes_dec
    forfaitaire_max_per_periode = forfaitaire_max / periodes_dec
    grondslag_belasting_jaar = max(ZERO, adjusted_bruto_jaar - forfaitaire_jaar)
    grondslag_belasting_per_periode = max(ZERO, adjusted_bruto_per_periode - forfaitaire_per_periode)

    # Belastbaar jaarloon (Art. 13 + Art. 14)
    belastbaar_jaar = max(
        ZERO,
        grondslag_belasting_jaar - belastingvrij_jaar,
    )

    # Tariefschijven (Art. 14) — dynamisch uit parameterrecords opgebouwd.
    previous_upper = ZERO
    bracket_rows = []
    for bracket in params['brackets']:
        upper = None if bracket['upper'] is None else _to_decimal(bracket['upper'])
        rate = _to_decimal(bracket['rate'])

        if upper is None:
            basis = max(ZERO, belastbaar_jaar - previous_upper)
        else:
            basis = max(ZERO, min(belastbaar_jaar, upper) - previous_upper)

        tax = basis * rate
        bracket_rows.append({
            'index': bracket['index'],
            'lower': previous_upper,
            'upper': upper,
            'rate': rate,
            'basis': basis,
            'tax': tax,
        })

        if upper is not None:
            previous_upper = upper

    lb_voor_heffingskorting_jaar = sum(row['tax'] for row in bracket_rows)
    lb_voor_heffingskorting_per_periode = lb_voor_heffingskorting_jaar / periodes_dec
    heffingskorting_jaar = heffingskorting_per_periode_dec * periodes_dec
    lb_jaar = max(ZERO, lb_voor_heffingskorting_jaar - heffingskorting_jaar)
    lb_per_periode = max(ZERO, lb_voor_heffingskorting_per_periode - heffingskorting_per_periode_dec)

    # AOV — ook over gecorrigeerd bruto (Art. 10f aftrek)
    effective_bruto_per_periode = max(ZERO, bruto_per_periode_dec - aftrek_bv_per_periode_dec)
    franchise_periode = aov_franchise_maand if periodes == 12 else ZERO
    aov_grondslag = max(ZERO, effective_bruto_per_periode - franchise_periode)
    aov_per_periode = aov_grondslag * aov_tarief

    serialized_bracket_rows = []
    for row in bracket_rows:
        serialized_bracket_rows.append({
            'index': row['index'],
            'lower': round_money(row['lower']),
            'upper': None if row['upper'] is None else round_money(row['upper']),
            'rate': float(row['rate']),
            'basis': round_money(row['basis']),
            'tax': round_money(row['tax']),
        })

    result = {
        'bruto_per_periode': round_money(bruto_per_periode_dec),
        'periodes': periodes,
        'bruto_jaar': round_money(bruto_jaar),
        'aftrek_bv_per_periode': round_money(aftrek_bv_per_periode_dec),
        'aftrek_bv_jaar': round_money(aftrek_bv_jaar),
        'adjusted_bruto_per_periode': round_money(adjusted_bruto_per_periode),
        'adjusted_bruto_jaar': round_money(adjusted_bruto_jaar),
        'forfaitaire_pct': float(forfaitaire_pct),
        'forfaitaire_per_periode': round_money(forfaitaire_per_periode),
        'forfaitaire_jaar': round_money(forfaitaire_jaar),
        'forfaitaire_max_per_periode': round_money(forfaitaire_max_per_periode),
        'forfaitaire_max': round_money(forfaitaire_max),
        'grondslag_belasting_per_periode': round_money(grondslag_belasting_per_periode),
        'grondslag_belasting_jaar': round_money(grondslag_belasting_jaar),
        'belastingvrij_jaar': round_money(belastingvrij_jaar),
        'belastbaar_jaar': round_money(belastbaar_jaar),
        'tax_brackets': serialized_bracket_rows,
        'lb_voor_heffingskorting_jaar': round_money(lb_voor_heffingskorting_jaar),
        'lb_voor_heffingskorting_per_periode': round_money(lb_voor_heffingskorting_per_periode),
        'heffingskorting_per_periode': round_money(heffingskorting_per_periode_dec),
        'heffingskorting_jaar': round_money(heffingskorting_jaar),
        'lb_jaar': round_money(lb_jaar),
        'lb_per_periode': round_money(lb_per_periode),
        # AOV
        'franchise_periode': round_money(franchise_periode),
        'aov_grondslag': round_money(aov_grondslag),
        'aov_tarief': float(aov_tarief),
        'aov_per_periode': round_money(aov_per_periode),
    }

    return _legacy_bracket_fields(result, serialized_bracket_rows)


def generate_breakdown_html(result, wage, periodes, salary_type, kb_split=None,
                            vrijgesteld=0.0, inhoudingen=0.0,
                            belastbaar_toelagen=0.0,
                            bruto_totaal=None, netto_totaal=None,
                            heffingskorting=0.0):
    """
    Genereert een stap-voor-stap berekeningsoverzicht (debug panel) als HTML.

    :param result:        Volledige dict van calculate_lb()
    :param wage:          Basisloon per periode (contract.wage)
    :param periodes:      Aantal periodes (12 of 26)
    :param salary_type:   'monthly' of 'fn'
    :param kb_split:      dict {'belastbaar': x, 'vrijgesteld': y} of None
    :param vrijgesteld:   Vrijgestelde toelagen per periode (transport etc.)
    :param inhoudingen:   Inhoudingen per periode (ziektekostenpremie etc.)
    :param belastbaar_toelagen: Belastbare toelagen per periode (contract regels)
    :param bruto_totaal:  Reeds berekend contract-bruto per periode
    :param netto_totaal:  Reeds berekend contract-netto per periode
    :returns: HTML string
    """
    def m(n, sign=''):
        """Formatteert getal met duizendpunten en 2 decimalen."""
        s = format_srd(abs(n))
        if sign == '+':
            clr = '#16a34a' if n >= 0 else '#dc2626'
            prefix = '+' if n >= 0 else '−'
            return f'<span style="color:{clr}; font-weight:600;">{prefix} {s}</span>'
        if sign == '-':
            return f'<span style="color:#dc2626; font-weight:600;">− {s}</span>'
        return f'<span>{s}</span>'

    def row(label, formula, value, style=''):
        css_cls = ' class="table-info"' if style else ''
        return (
            f'<tr{css_cls}>'
            f'<td>{label}</td>'
            f'<td class="text-muted small">{formula}</td>'
            f'<td class="text-end font-monospace">{value}</td>'
            f'</tr>'
        )

    def sep(title):
        return (
            f'<tr class="table-secondary">'
            f'<td colspan="3" class="fw-bold small">{title}</td>'
            f'</tr>'
        )

    def total_val(label, val_num, color='#1e40af'):
        s = format_srd(abs(val_num))
        return (
            f'<tr class="table-primary">'
            f'<td colspan="2" class="fw-bold">{label}</td>'
            f'<td class="text-end fw-bold font-monospace">{s}</td></tr>'
        )

    r = result
    loon_type_str = 'Maandloon (12×/jaar)' if salary_type == 'monthly' else 'Fortnight (26×/jaar)'
    kb = kb_split or {'belastbaar': 0.0, 'vrijgesteld': 0.0}
    kb_b = kb.get('belastbaar', 0.0)
    kb_v = kb.get('vrijgesteld', 0.0)
    gross_per_periode = wage + r.get('aftrek_bv_per_periode', 0.0) + 0.0  # original gross before aftrek

    bruto_display = bruto_totaal if bruto_totaal is not None else (
        wage
        + belastbaar_toelagen
        + kb_b + kb_v + vrijgesteld
    )

    netto = netto_totaal if netto_totaal is not None else (
        bruto_display
        - r['lb_per_periode']
        - r['aov_per_periode']
        - inhoudingen
        - r.get('aftrek_bv_per_periode', 0.0)
    )

    rows = []

    # ─── Sectie 1: Bruto ───────────────────────────
    rows.append(sep('① BRUTO LOON (per periode)'))
    rows.append(row('Loontype', loon_type_str, m(wage)))
    if belastbaar_toelagen > 0:
        rows.append(row('Belastbare toelagen', '(contract regels)', m(belastbaar_toelagen)))
    if vrijgesteld > 0:
        rows.append(row('Vrijgestelde toelagen', '(transport, maaltijd, ...)', m(vrijgesteld)))
    if r.get('aftrek_bv_per_periode', 0.0) > 0:
        rows.append(row('Pensioenpremie inhouding', 'aftrek_belastingvrij', m(r['aftrek_bv_per_periode'])))
    rows.append(row('<strong>GROSS belastbaar</strong>', 'Basisloon + belastbare toelagen',
                    m(r['bruto_per_periode']), '#f0f9ff'))

    if kb_b > 0 or kb_v > 0:
        rows.append(sep('② OVERIGE VERDIENSTEN (buiten GROSS)'))
        rows.append(row('Kinderbijslag belastbaar deel', 'apart getoond, niet in bruto belastbaar loon', m(kb_b)))
        rows.append(row('Kinderbijslag vrijgesteld deel', 'vrijstelling volgens SR Payroll Instellingen', m(kb_v)))

    # ─── Sectie 2: Grondslag ───────────────────────
    rows.append(sep('③ GRONDSLAG VOOR BELASTING'))
    rows.append(row('Bruto loon per periode', '', m(r['bruto_per_periode'])))
    if r.get('aftrek_bv_jaar', 0.0) > 0:
        rows.append(row('Aftrek belastingvrij (Art. 10f)',
                        'verlaagt bruto vóór forfaitaire aftrek',
                        m(r['aftrek_bv_per_periode'], '-')))
    rows.append(row('Forfaitaire aftrek (Art. 12)',
                    f'{_format_number(r["forfaitaire_pct"] * 100, 0)}% van bruto (max {format_srd(r.get("forfaitaire_max_per_periode", 0))}/periode)',
                    m(r['forfaitaire_per_periode'], '-')))
    rows.append(total_val('= Grondslag voor Belasting', r['grondslag_belasting_per_periode']))
    rows.append(row('Grondslag voor Belasting per jaar',
                    f'{format_srd(r["grondslag_belasting_per_periode"])} × {periodes}',
                    m(r['grondslag_belasting_jaar'])))
    if r['belastingvrij_jaar'] > 0:
        rows.append(row('Belastingvrije som (Art. 13)',
                        f'{format_srd(r["belastingvrij_jaar"], 0)}/jaar',
                        m(r['belastingvrij_jaar'], '-')))
    rows.append(total_val('= Belastbaar Jaarloon', r['belastbaar_jaar']))

    # ─── Sectie 3: LB Schijven ─────────────────────
    rows.append(sep('④ LOONBELASTING SCHIJVEN (Art. 14)'))
    for bracket in r.get('tax_brackets', []):
        if bracket['basis'] <= 0:
            continue
        if bracket['upper'] is None:
            formula = (
                f'Boven {format_srd(bracket["lower"], 0)} × {_format_number(bracket["rate"] * 100, 0)}%'
            )
        else:
            formula = (
                f'{format_srd(bracket["basis"], 0)} × {_format_number(bracket["rate"] * 100, 0)}%'
            )
        rows.append(row(
            f'Schijf {bracket["index"]} ({_format_number(bracket["rate"] * 100, 0)}%)',
            formula,
            m(bracket['tax']),
        ))
    rows.append(row('<strong>LB vóór heffingskorting</strong>', 'som schijven',
                    m(r['lb_voor_heffingskorting_jaar']), '#f0f9ff'))
    rows.append(row('LB vóór heffingskorting per periode',
                    f'{format_srd(r["lb_voor_heffingskorting_jaar"], 0)} ÷ {periodes}',
                    m(r['lb_voor_heffingskorting_per_periode'])))
    if r.get('heffingskorting_per_periode', 0.0) > 0:
        rows.append(row('Heffingskorting',
                        f'{format_srd(r["heffingskorting_per_periode"])} per periode',
                        m(r['heffingskorting_per_periode'], '-')))
    rows.append(row('<strong>In te houden Loonbelasting</strong>',
                    'na heffingskorting',
                    m(r['lb_per_periode']), '#fef9c3'))

    # ─── Sectie 4: AOV ─────────────────────────────
    rows.append(sep('⑤ AOV BIJDRAGE (4%)'))
    franchise_label = f'AOV franchise − {format_srd(r["franchise_periode"], 0)}/periode' \
        if r['franchise_periode'] > 0 else 'Geen AOV franchise (Fortnight)'
    rows.append(row('Bruto belastbaar loon per periode', '', m(r['bruto_per_periode'])))
    if r.get('aftrek_bv_per_periode', 0.0) > 0:
        rows.append(row('Aftrek belastingvrij (Art. 10f)',
                        'verlaagt AOV-grondslag vóór franchise',
                        m(r['aftrek_bv_per_periode'], '-')))
    rows.append(row('Belastbaar loon vóór franchise', '', m(r['adjusted_bruto_per_periode']), '#f0f9ff'))
    if r['franchise_periode'] > 0:
        rows.append(row('Franchise (Art. 4 AOV)', franchise_label, m(r['franchise_periode'], '-')))
    rows.append(row('AOV grondslag',
                    f'{format_srd(r["adjusted_bruto_per_periode"])} - {format_srd(r["franchise_periode"])}' if r['franchise_periode'] > 0 else 'geen franchise bij fortnight',
                    m(r['aov_grondslag']), '#f0f9ff'))
    rows.append(row('<strong>AOV inhouding per periode</strong>',
                    f'{_format_number(r["aov_tarief"] * 100, 0)}% × {format_srd(r["aov_grondslag"])}',
                    m(r['aov_per_periode']), '#fef9c3'))

    # ─── Sectie 5: Netto Berekening ────────────────
    rows.append(sep('⑥ GESCHAT NETTOLOON PER PERIODE'))
    rows.append(row('Basisloon', '', m(wage, '+')))
    if belastbaar_toelagen > 0:
        rows.append(row('+ Belastbare toelagen', '', m(belastbaar_toelagen, '+')))
    if kb_b > 0:
        rows.append(row('+ KB belastbaar deel', '', m(kb_b, '+')))
    if kb_v > 0:
        rows.append(row('+ KB vrijgesteld deel', '', m(kb_v, '+')))
    if vrijgesteld > 0:
        rows.append(row('+ Vrijgestelde toelagen', '', m(vrijgesteld, '+')))
    rows.append(row('<strong>= Bruto per periode</strong>', '', m(bruto_display), '#f0f9ff'))
    rows.append(row('− LB (Art. 14)', '', m(r['lb_per_periode'], '-')))
    rows.append(row('− AOV (4%)', '', m(r['aov_per_periode'], '-')))
    if inhoudingen > 0:
        rows.append(row('− Andere inhoudingen', '', m(inhoudingen, '-')))
    if r.get('aftrek_bv_per_periode', 0.0) > 0:
        rows.append(row('− Aftrek belastingvrij', '(pensioenpremie e.d.)', m(r['aftrek_bv_per_periode'], '-')))
    rows.append(total_val('= Geschat Netto Loon', netto, '#065f46'))

    rows_html = ''.join(rows)
    return (
        '<div class="alert alert-info py-1 px-2 mb-1 small">'
        '<strong>&#9998; Art. 14 Berekening — Stap-voor-Stap</strong>'
        '</div>'
        '<table class="table table-sm table-bordered" style="font-size:0.88em;">'
        '<thead class="table-light">'
        '<tr>'
        '<th style="width:38%;">Stap</th>'
        '<th style="width:38%;">Formule</th>'
        '<th style="width:24%; text-align:right;">Bedrag</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
    )


def generate_tax_bracket_html(params):
    """
    Genereert een HTML-tabel van de tariefschijven op basis van parameters.

    :param params: dict met brackets, belastingvrij_jaar, forfaitaire_pct, forfaitaire_max
    :returns: HTML string
    """
    def fmt(n):
        """Format number as SRD with thousand separator."""
        return format_srd(n, 0)

    def pct(n):
        return f'{_format_number(_to_decimal(n) * 100, 0)}%'

    rows_html = ""
    colors = ['#16a34a', '#d97706', '#dc2626', '#7c3aed', '#0f766e', '#b45309']
    for index, bracket in enumerate(params.get('brackets', []), start=1):
        lower = bracket['lower'] if 'lower' in bracket else 0.0
        upper = bracket['upper']
        color = colors[(index - 1) % len(colors)]
        if upper is None:
            bereik = f"Boven {fmt(lower)}"
        elif lower <= 0:
            bereik = f"t/m {fmt(upper)}"
        else:
            bereik = f'{fmt(_to_decimal(lower) + 1)} – {fmt(upper)}'
        rows_html += (
            f'<tr>'
            f'<td>{index}</td>'
            f'<td>{bereik}</td>'
            f'<td class="text-center fw-bold" style="color:{color};">{pct(bracket["rate"])}</td>'
            f'</tr>'
        )

    forfaitaire_max = params.get('forfaitaire_max', 0)

    return (
        '<table class="table table-sm table-bordered" style="font-size:0.9em;">'
        '<thead class="table-light">'
        '<tr>'
        '<th>Schijf</th>'
        '<th>Belastbaar Jaarloon</th>'
        '<th class="text-center">Tarief</th>'
        '</tr>'
        '</thead>'
        f'<tbody>{rows_html}</tbody>'
        '</table>'
        '<p class="text-muted small mb-0">'
        f'<strong>Art. 12:</strong> Forfaitaire aftrek {pct(params["forfaitaire_pct"])} van jaarloon '
        f'(max {fmt(forfaitaire_max)}) · '
        f'<strong>Art. 13:</strong> Belastingvrije som {fmt(params["belastingvrij_jaar"])}/jaar · '
        '<strong>Overwerk Art. 17c:</strong> 5% / 15% / 25%'
        '</p>'
    )
