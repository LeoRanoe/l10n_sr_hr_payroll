# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as dt_date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import sr_artikel14_calculator as calc

# Module-level cache for Art. 14 calculations per compute cycle.
# Keyed on (payslip_id, gross, aftrek_bv). Cleared before each compute_sheet.
_sr_calc_cache = {}
_SR_MONEY_QUANT = Decimal('0.01')
_SR_HOURLY_RATE_QUANT = Decimal('0.000001')

SR_FN_2026_PERIODS = (
    {'indicator': '202601', 'label': '2026FN1', 'date_from': dt_date(2026, 1, 1), 'date_to': dt_date(2026, 1, 14)},
    {'indicator': '202602', 'label': '2026FN2', 'date_from': dt_date(2026, 1, 15), 'date_to': dt_date(2026, 1, 28)},
    {'indicator': '202603', 'label': '2026FN3', 'date_from': dt_date(2026, 1, 29), 'date_to': dt_date(2026, 2, 11)},
    {'indicator': '202604', 'label': '2026FN4', 'date_from': dt_date(2026, 2, 12), 'date_to': dt_date(2026, 2, 25)},
    {'indicator': '202605', 'label': '2026FN5', 'date_from': dt_date(2026, 2, 26), 'date_to': dt_date(2026, 3, 11)},
    {'indicator': '202606', 'label': '2026FN6', 'date_from': dt_date(2026, 3, 12), 'date_to': dt_date(2026, 3, 25)},
    {'indicator': '202607', 'label': '2026FN7', 'date_from': dt_date(2026, 3, 26), 'date_to': dt_date(2026, 4, 8)},
    {'indicator': '202608', 'label': '2026FN8', 'date_from': dt_date(2026, 4, 9), 'date_to': dt_date(2026, 4, 22)},
    {'indicator': '202609', 'label': '2026FN9', 'date_from': dt_date(2026, 4, 23), 'date_to': dt_date(2026, 5, 6)},
    {'indicator': '202610', 'label': '2026FN10', 'date_from': dt_date(2026, 5, 7), 'date_to': dt_date(2026, 5, 20)},
    {'indicator': '202611', 'label': '2026FN11', 'date_from': dt_date(2026, 5, 21), 'date_to': dt_date(2026, 6, 3)},
    {'indicator': '202612', 'label': '2026FN12', 'date_from': dt_date(2026, 6, 4), 'date_to': dt_date(2026, 6, 17)},
    {'indicator': '202613', 'label': '2026FN13', 'date_from': dt_date(2026, 6, 18), 'date_to': dt_date(2026, 7, 1)},
    {'indicator': '202614', 'label': '2026FN14', 'date_from': dt_date(2026, 7, 2), 'date_to': dt_date(2026, 7, 15)},
    {'indicator': '202615', 'label': '2026FN15', 'date_from': dt_date(2026, 7, 16), 'date_to': dt_date(2026, 7, 29)},
    {'indicator': '202616', 'label': '2026FN16', 'date_from': dt_date(2026, 7, 30), 'date_to': dt_date(2026, 8, 12)},
    {'indicator': '202617', 'label': '2026FN17', 'date_from': dt_date(2026, 8, 13), 'date_to': dt_date(2026, 8, 26)},
    {'indicator': '202618', 'label': '2026FN18', 'date_from': dt_date(2026, 8, 27), 'date_to': dt_date(2026, 9, 9)},
    {'indicator': '202619', 'label': '2026FN19', 'date_from': dt_date(2026, 9, 10), 'date_to': dt_date(2026, 9, 23)},
    {'indicator': '202620', 'label': '2026FN20', 'date_from': dt_date(2026, 9, 24), 'date_to': dt_date(2026, 10, 7)},
    {'indicator': '202621', 'label': '2026FN21', 'date_from': dt_date(2026, 10, 8), 'date_to': dt_date(2026, 10, 21)},
    {'indicator': '202622', 'label': '2026FN22', 'date_from': dt_date(2026, 10, 22), 'date_to': dt_date(2026, 11, 4)},
    {'indicator': '202623', 'label': '2026FN23', 'date_from': dt_date(2026, 11, 5), 'date_to': dt_date(2026, 11, 18)},
    {'indicator': '202624', 'label': '2026FN24', 'date_from': dt_date(2026, 11, 19), 'date_to': dt_date(2026, 12, 2)},
    {'indicator': '202625', 'label': '2026FN25', 'date_from': dt_date(2026, 12, 3), 'date_to': dt_date(2026, 12, 16)},
    {'indicator': '202626', 'label': '2026FN26', 'date_from': dt_date(2026, 12, 17), 'date_to': dt_date(2026, 12, 30)},
)


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    sr_is_sr_struct = fields.Boolean(
        compute='_compute_sr_is_sr_struct',
        string='SR Structuur',
        store=True,
        compute_sudo=True,
    )

    @api.depends('struct_id')
    def _compute_sr_is_sr_struct(self):
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        for slip in self:
            slip.sr_is_sr_struct = sr_struct and slip.struct_id == sr_struct

    def compute_sheet(self):
        """Clear Art. 14 calculation cache before computing salary rules."""
        global _sr_calc_cache
        _sr_calc_cache.clear()
        for slip in self:
            slip._sr_validate_contract_period_integrity()
            slip._sr_validate_fn_period_2026()
            slip._sr_sync_overtime_inputs_from_work_entries()
        res = super().compute_sheet()
        _sr_calc_cache.clear()
        return res

    def action_payslip_done(self):
        for slip in self:
            slip._sr_validate_contract_period_integrity()
        return super().action_payslip_done()

    def _rule_parameter(self, code):
        self.ensure_one()
        config_key = calc.get_config_parameter_key(code)
        if config_key:
            value = self.env['ir.config_parameter'].sudo().get_param(config_key)
            if value not in (None, False, ''):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
            default = calc.get_config_parameter_default(code)
            if default is not None:
                return default
        return super()._rule_parameter(code)

    def _sr_money_quantize(self, value, quant=_SR_MONEY_QUANT):
        self.ensure_one()
        if value in (None, False, ''):
            return Decimal('0').quantize(quant, rounding=ROUND_HALF_UP)
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)

    def _sr_validate_contract_period_integrity(self):
        self.ensure_one()
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        if self.struct_id != sr_struct or not self.contract_id or not self.employee_id or not self.date_from or not self.date_to:
            return

        contract = self.contract_id
        if contract.date_start and self.date_from < contract.date_start:
            raise UserError(
                'SR-loonstroken mogen niet voor de startdatum van het gekozen contract vallen. '
                'Maak aparte loonstroken per contractsegment.'
            )
        if contract.date_end and self.date_to > contract.date_end:
            raise UserError(
                'SR-loonstroken mogen niet doorlopen na de einddatum van het gekozen contract. '
                'Maak aparte loonstroken per contractsegment.'
            )

        overlapping_contracts = self.env['hr.contract'].search([
            ('employee_id', '=', self.employee_id.id),
            ('id', '!=', contract.id),
            ('date_start', '<=', self.date_to),
            '|', ('date_end', '=', False), ('date_end', '>=', self.date_from),
            ('state', '!=', 'cancel'),
        ])
        if overlapping_contracts:
            contract_names = ', '.join(overlapping_contracts.mapped('name'))
            raise UserError(
                'Deze SR-loonstrook overlapt meerdere contracten voor dezelfde werknemer '
                f'({contract_names}). Maak aparte loonstroken per contractperiode zodat '
                'maandloon/Fortnight en vaste regels niet door elkaar lopen.'
            )

    def _sr_get_hourly_rate(self):
        self.ensure_one()
        wage = self.contract_id.wage or 0.0
        if not wage:
            return 0.0
        divisor = Decimal('80') if self._sr_get_periodes() == 26 else Decimal('173.333333')
        hourly_rate = Decimal(str(wage)) / divisor
        return float(hourly_rate.quantize(_SR_HOURLY_RATE_QUANT, rounding=ROUND_HALF_UP))

    def _sr_sync_overtime_inputs_from_work_entries(self):
        self.ensure_one()

        generated_inputs = self.input_line_ids.filtered('sr_generated_from_work_entry')
        if generated_inputs:
            generated_inputs.unlink()

        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        overtime_type = self.env.ref('l10n_sr_hr_payroll.sr_input_overwerk', raise_if_not_found=False)
        if self.struct_id != sr_struct or not overtime_type or not self.contract_id or not self.date_from or not self.date_to:
            return

        period_start = datetime.combine(self.date_from, time.min)
        period_stop = datetime.combine(self.date_to + timedelta(days=1), time.min)
        hourly_rate = self._sr_get_hourly_rate()
        if hourly_rate <= 0:
            return

        work_entries = self.env['hr.work.entry'].search([
            ('contract_id', '=', self.contract_id.id),
            ('date_start', '<', period_stop),
            ('date_stop', '>', period_start),
            ('state', '=', 'validated'),
            ('work_entry_type_id.sr_is_overtime', '=', True),
        ], order='date_start, id')

        for entry in work_entries:
            effective_start = max(entry.date_start, period_start)
            effective_stop = min(entry.date_stop, period_stop)
            hours = max(0.0, (effective_stop - effective_start).total_seconds() / 3600.0)
            if hours <= 0:
                continue
            multiplier = entry.work_entry_type_id.sr_overtime_multiplier or 1.0
            amount = float(self._sr_money_quantize(Decimal(str(hours)) * Decimal(str(hourly_rate)) * Decimal(str(multiplier))))
            if amount <= 0:
                continue
            self.env['hr.payslip.input'].create({
                'payslip_id': self.id,
                'name': f'{entry.work_entry_type_id.name} ({hours:.2f}u)',
                'input_type_id': overtime_type.id,
                'amount': amount,
                'sr_generated_from_work_entry': True,
                'sr_work_entry_id': entry.id,
            })

    def _sr_get_periodes(self):
        """Bepaalt het aantal periodes per jaar: 12 (maandloon) of 26 (fortnight)."""
        self.ensure_one()
        contract = self.contract_id
        return 26 if getattr(contract, 'sr_salary_type', 'monthly') == 'fn' else 12

    def _sr_get_fn_period_2026(self):
        """Geeft het 2026 fortnight-tijdvak terug volgens de modulecontext."""
        self.ensure_one()
        if not self.date_from or not self.date_to:
            return False
        for period in SR_FN_2026_PERIODS:
            if self.date_from == period['date_from'] and self.date_to == period['date_to']:
                return period
        return False

    def _sr_validate_fn_period_2026(self):
        """Forceer voor 2026 exact de 26 gedocumenteerde fortnight-periodes."""
        self.ensure_one()
        contract = self.contract_id
        if getattr(contract, 'sr_salary_type', 'monthly') != 'fn':
            return
        if not self.date_from or not self.date_to:
            return
        if self.date_from.year != 2026 and self.date_to.year != 2026:
            return
        if self._sr_get_fn_period_2026():
            return
        raise UserError(
            'Fortnight-loonstroken in 2026 moeten exact overeenkomen met de '
            'gedocumenteerde 26 tijdvakken uit de Suriname context.'
        )

    def _sr_get_cached_result(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent Artikel 14 één keer per (payslip, gross, aftrek_bv) combinatie
        en cached het resultaat in een module-level dict om redundante
        berekeningen te voorkomen wanneer SR_LB en SR_AOV regels
        achtereenvolgens dezelfde waarden opvragen.
        """
        self.ensure_one()
        global _sr_calc_cache
        cache_key = (
            self.id,
            str(self._sr_money_quantize(gross_per_periode)),
            str(self._sr_money_quantize(aftrek_bv)),
        )
        if cache_key in _sr_calc_cache:
            return _sr_calc_cache[cache_key]
        params = calc.fetch_params_from_payslip(self)
        periodes = self._sr_get_periodes()
        result = calc.calculate_lb(
            gross_per_periode, periodes, params,
            aftrek_bv_per_periode=aftrek_bv,
        )
        _sr_calc_cache[cache_key] = result
        return result

    def _sr_artikel14_lb(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent Artikel 14 loonbelasting per periode.

        Wordt aangeroepen door de SR_LB salarisregel.
        Gebruikt de centrale calculator zodat de berekening altijd
        overeenkomt met de contract preview.

        :param gross_per_periode: Bruto belastbaar loon per periode (categories['GROSS'])
        :param aftrek_bv: Aftrek belastingvrij per periode (Art. 10f, bijv. pensioenpremie)
        :returns: positief bedrag loonbelasting per periode
        """
        return self._sr_get_cached_result(gross_per_periode, aftrek_bv)['lb_per_periode']

    def _sr_artikel14_aov(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent AOV bijdrage per periode.

        Wordt aangeroepen door de SR_AOV salarisregel.

        :param gross_per_periode: Bruto belastbaar loon per periode
        :param aftrek_bv: Aftrek belastingvrij per periode (Art. 10f)
        :returns: positief bedrag AOV per periode
        """
        return self._sr_get_cached_result(gross_per_periode, aftrek_bv)['aov_per_periode']

    def _sr_bijz_gratificatie_cap(self, vrijstelling_max):
        """Berekent de slip-specifieke gratificatievrijstelling met pro-rata dienstjaar."""
        self.ensure_one()
        contract = self.contract_id
        wage_maand = (contract.wage or 0.0) * self._sr_get_periodes() / 12
        cap = min(wage_maand, vrijstelling_max)
        if self.date_to and contract.date_start:
            year_start = self.date_to.replace(month=1, day=1)
            service_start = max(contract.date_start, year_start)
            months = (self.date_to.year - service_start.year) * 12 + self.date_to.month - service_start.month + 1
            months = min(12, max(1, months))
            cap = cap * months / 12
        return cap

    def _sr_bijz_usage_summary(self, remaining_caps=None, vrijstelling_max=None):
        """Geeft vrijgesteld, belastbaar en resterende jaarcaps terug voor Art. 17 inputs."""
        self.ensure_one()
        contract = self.contract_id
        if vrijstelling_max is None:
            vrijstelling_max = self._rule_parameter('SR_BIJZ_VRIJSTELLING_MAX')
        if remaining_caps is None:
            remaining_caps = {
                'vakantie': vrijstelling_max,
                'gratificatie': vrijstelling_max,
            }
        else:
            remaining_caps = {
                'vakantie': remaining_caps.get('vakantie', vrijstelling_max),
                'gratificatie': remaining_caps.get('gratificatie', vrijstelling_max),
            }

        wage_maand = (contract.wage or 0.0) * self._sr_get_periodes() / 12
        vrijgesteld_used = 0.0
        belastbaar_totaal = 0.0

        for inp in self.input_line_ids.sorted(lambda line: line.id or 0):
            cat = inp.input_type_id.sr_categorie
            bruto = inp.amount
            if cat not in ('vakantie', 'gratificatie', 'bijz_beloning') or bruto <= 0:
                continue

            if cat == 'vakantie':
                vrijstelling = min(2 * wage_maand, remaining_caps['vakantie'])
            elif cat == 'gratificatie':
                vrijstelling = min(
                    self._sr_bijz_gratificatie_cap(vrijstelling_max),
                    remaining_caps['gratificatie'],
                )
            else:
                vrijstelling = 0.0

            actual_vrijstelling = min(vrijstelling, bruto)
            if cat in remaining_caps:
                remaining_caps[cat] = max(0.0, remaining_caps[cat] - actual_vrijstelling)
            vrijgesteld_used += actual_vrijstelling
            belastbaar_totaal += max(0.0, bruto - actual_vrijstelling)

        return {
            'vrijgesteld': vrijgesteld_used,
            'belastbaar': belastbaar_totaal,
            'remaining_caps': remaining_caps,
        }

    def _sr_bijz_belastbaar_totaal(self):
        """
        Bereken het totale belastbare bedrag van bijzondere beloningen (Art. 17).

        Handelt YTD-cap-lookup en vrijstellingsberekening af zodat
        de logica in salarisregels SR_LB_BIJZ en SR_AOV_BIJZ niet
        gedupliceerd hoeft te worden.

        :returns: float belastbaar_bijz_totaal (>= 0)
        """
        self.ensure_one()
        vrijstelling_max = self._rule_parameter('SR_BIJZ_VRIJSTELLING_MAX')

        # ── Year-to-date cap lookup ─────────────────────────────────────
        year_start = self.date_from.replace(month=1, day=1) if self.date_from else False
        remaining_caps = {
            'vakantie': vrijstelling_max,
            'gratificatie': vrijstelling_max,
        }
        if year_start:
            prev_slips = self.env['hr.payslip'].search([
                ('employee_id', '=', self.employee_id.id),
                ('date_from', '>=', year_start),
                ('date_from', '<', self.date_from),
                ('state', 'in', ['done', 'paid']),
                ('id', '!=', self.id),
            ], order='date_from, id')
            for ps in prev_slips:
                usage = ps._sr_bijz_usage_summary(
                    remaining_caps=remaining_caps,
                    vrijstelling_max=vrijstelling_max,
                )
                remaining_caps = usage['remaining_caps']

        current_usage = self._sr_bijz_usage_summary(
            remaining_caps=remaining_caps,
            vrijstelling_max=vrijstelling_max,
        )
        return current_usage['belastbaar']

    def _get_sr_artikel14_breakdown(self):
        """
        Berekent de tussenliggende Artikel 14 stappen voor weergave op de loonstrook.

        Gebruikt de centrale calculator zodat het rapport altijd
        overeenkomt met de werkelijke berekening.
        Geeft een leeg dict terug als de loonstrook nog geen regels heeft.
        """
        self.ensure_one()

        if not self.date_from or not self.line_ids:
            return {}

        contract = self.contract_id
        periodes = self._sr_get_periodes()
        fn_period = self._sr_get_fn_period_2026() if periodes == 26 else False

        # ── Loonstrookregels ophalen ──────────────────────────────────────────
        # sum(mapped('total')) is veilig als meerdere regels met dezelfde code bestaan
        # (bijv. wanneer Odoo een default GROSS regel heeft gekopieerd bij aanmaken structuur)
        def _line_total(code):
            lines = self.line_ids.filtered(lambda l: l.code == code)
            return sum(lines.mapped('total')) if lines else 0.0

        basic = _line_total('BASIC')
        toelagen = _line_total('SR_ALW')
        kb_belastbaar = _line_total('SR_KB_BELAST')
        kb_vrijgesteld = _line_total('SR_KB_VRIJ')
        input_belastbaar = _line_total('SR_INPUT_BELASTB')
        input_vrijgesteld = _line_total('SR_INPUT_VRIJ')
        heffingskorting = _line_total('SR_HK')
        pensioen = abs(_line_total('SR_PENSIOEN'))
        input_aftrek = abs(_line_total('SR_INPUT_AFTREK'))
        aftrek_bv = abs(_line_total('SR_AFTREK_BV'))
        vrijgesteld_contract = _line_total('SR_KINDBIJ')  # Vaste vrijgestelde vergoedingen (excl. KB)

        # Post-GROSS positieve inkomsten
        overwerk = _line_total('SR_OVERWERK')
        vakantie = _line_total('SR_VAKANTIE')
        gratificatie = _line_total('SR_GRAT')
        bijz_beloning = _line_total('SR_BIJZ')
        uitkering_ineens = _line_total('SR_UITK_INEENS')

        # Werkelijke LB/AOV van de payslip regels (inclusief bijzondere/overwerk/17a)
        lb_per_periode = abs(_line_total('SR_LB'))
        lb_bijz = abs(_line_total('SR_LB_BIJZ'))
        lb_17a = abs(_line_total('SR_LB_17A'))
        aov_per_periode = abs(_line_total('SR_AOV'))
        aov_bijz = abs(_line_total('SR_AOV_BIJZ'))
        aov_17a = abs(_line_total('SR_AOV_17A'))
        lb_overwerk = abs(_line_total('SR_LB_OVERWERK'))
        aov_overwerk = abs(_line_total('SR_AOV_OVERWERK'))

        # ── Calculator voor Art. 14 stap-detail ──────────────────────────────
        # Herleid de wettelijke Art. 14 grondslag uit de expliciete belastbare
        # looncomponenten. Historische SR_HK-regels kunnen het GROSS/NET totaal
        # op bestaande slips verhogen, maar horen niet in de LB/AOV-grondslag.
        gross = basic + toelagen + kb_belastbaar + input_belastbaar
        params = calc.fetch_params_from_payslip(self)
        r = calc.calculate_lb(gross, periodes, params, aftrek_bv_per_periode=aftrek_bv)

        # Totalen van alle feitelijke debet-regels
        totaal_lb = lb_per_periode + lb_bijz + lb_17a + lb_overwerk
        totaal_aov = aov_per_periode + aov_bijz + aov_17a + aov_overwerk
        totaal_inhoudingen = totaal_lb + totaal_aov + pensioen + input_aftrek

        kinderbijslag = kb_belastbaar + kb_vrijgesteld
        bruto_totaal = (
            basic + toelagen + kinderbijslag
            + vrijgesteld_contract
            + input_belastbaar + input_vrijgesteld
            + overwerk + vakantie + gratificatie + bijz_beloning + uitkering_ineens
        )
        netto = bruto_totaal + heffingskorting - totaal_inhoudingen - aftrek_bv

        contract_inhoudingen = []
        for line in contract.sr_vaste_regels.filtered(lambda record: record._sr_effective_category() == 'inhouding'):
            amount = contract._sr_resolve_line_amount(line)
            if amount > 0:
                contract_inhoudingen.append({'name': line.name, 'amount': amount})

        input_inhoudingen = []
        for input_line in self.input_line_ids.filtered(
            lambda record: record.input_type_id.sr_categorie == 'inhouding' and record.amount > 0
        ):
            input_inhoudingen.append({
                'name': input_line.input_type_id.name or input_line.name or 'Payslip input',
                'amount': input_line.amount,
            })

        return {
            # Basis
            'periodes': periodes,
            'is_fn': periodes == 26,
            'fn_period_indicator': fn_period['indicator'] if fn_period else False,
            'fn_period_label': fn_period['label'] if fn_period else False,
            'basic': basic,
            'toelagen': toelagen,
            'kinderbijslag': kinderbijslag,
            'kb_belastbaar': kb_belastbaar,
            'kb_vrijgesteld': kb_vrijgesteld,
            'vrijgesteld_contract': vrijgesteld_contract,
            'heffingskorting': heffingskorting,
            'overwerk': overwerk,
            'vakantie': vakantie,
            'gratificatie': gratificatie,
            'bijz_beloning': bijz_beloning,
            'uitkering_ineens': uitkering_ineens,
            'bruto_per_periode': gross,
            'bruto_totaal': bruto_totaal,
            # Artikel 14 stappen
            'bruto_jaarloon': r['bruto_jaar'],
            'belastingvrij_jaar': r['belastingvrij_jaar'],
            'forfaitaire_pct': r['forfaitaire_pct'] * 100,
            'forfaitaire_jaar': r['forfaitaire_jaar'],
            'forfaitaire_max_jaar': params.get('forfaitaire_max', 4800),
            'belastbaar_jaarloon': r['belastbaar_jaar'],
            'tax_brackets': r.get('tax_brackets', []),
            # Schijfgrenzen
            's1_grens': r['s1'],
            's2_grens': r['s2'],
            's3_grens': r['s3'],
            # Schijfbedragen
            's1_basis': r['s1_basis'],
            's2_basis': r['s2_basis'],
            's3_basis': r['s3_basis'],
            's4_basis': r['s4_basis'],
            # Belasting per schijf
            'r1_pct': r['r1'] * 100,
            'r2_pct': r['r2'] * 100,
            'r3_pct': r['r3'] * 100,
            'r4_pct': r['r4'] * 100,
            'lb_s1': r['lb_s1'],
            'lb_s2': r['lb_s2'],
            'lb_s3': r['lb_s3'],
            'lb_s4': r['lb_s4'],
            'lb_jaar': r['lb_jaar'],
            'lb_per_periode': lb_per_periode,
            # Bijzondere + overwerk + 17a componenten
            'lb_bijz': lb_bijz,
            'lb_17a': lb_17a,
            'lb_overwerk': lb_overwerk,
            'aov_bijz': aov_bijz,
            'aov_17a': aov_17a,
            'aov_overwerk': aov_overwerk,
            # AOV
            'franchise_periode': r['franchise_periode'],
            'aov_grondslag': r['aov_grondslag'],
            'aov_tarief_pct': r['aov_tarief'] * 100,
            'aov_per_periode': aov_per_periode,
            # Samenvatting
            'aftrek_bv': aftrek_bv,
            'pensioen': pensioen,
            'input_aftrek': input_aftrek,
            'contract_inhoudingen': contract_inhoudingen,
            'input_inhoudingen': input_inhoudingen,
            'totaal_lb': totaal_lb,
            'totaal_aov': totaal_aov,
            'totaal_inhoudingen': totaal_inhoudingen,
            'netto': netto,
        }

    def action_print_sr_payslip(self):
        """Print de Surinaamse Loonstrook als PDF (Artikel 14 WLB)."""
        self.ensure_one()
        return self.env.ref('l10n_sr_hr_payroll.action_report_payslip_sr').report_action(self)

    def action_preview_sr_payslip(self):
        """Bekijk de Surinaamse Loonstrook als HTML preview."""
        self.ensure_one()
        return self.env.ref('l10n_sr_hr_payroll.action_report_payslip_sr_preview').report_action(self)
