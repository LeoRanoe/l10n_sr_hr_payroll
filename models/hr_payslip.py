# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models

from . import sr_artikel14_calculator as calc

# Module-level cache for Art. 14 calculations per compute cycle.
# Keyed on (payslip_id, gross, aftrek_bv). Cleared before each compute_sheet.
_sr_calc_cache = {}


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
        res = super().compute_sheet()
        _sr_calc_cache.clear()
        return res

    def _sr_get_periodes(self):
        """Bepaalt het aantal periodes per jaar: 12 (maandloon) of 26 (fortnight)."""
        self.ensure_one()
        contract = self.contract_id
        return 26 if getattr(contract, 'sr_salary_type', 'monthly') == 'fn' else 12

    def _sr_get_cached_result(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent Artikel 14 één keer per (payslip, gross, aftrek_bv) combinatie
        en cached het resultaat in een module-level dict om redundante
        berekeningen te voorkomen wanneer SR_LB en SR_AOV regels
        achtereenvolgens dezelfde waarden opvragen.
        """
        self.ensure_one()
        global _sr_calc_cache
        cache_key = (self.id, round(gross_per_periode, 2), round(aftrek_bv, 2))
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
        # Gebruik de werkelijke GROSS grondslag van de payslip
        gross = _line_total('GROSS')
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
        netto = bruto_totaal - totaal_inhoudingen - aftrek_bv

        return {
            # Basis
            'periodes': periodes,
            'is_fn': periodes == 26,
            'basic': basic,
            'toelagen': toelagen,
            'kinderbijslag': kinderbijslag,
            'vrijgesteld_contract': vrijgesteld_contract,
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
            'belastbaar_jaarloon': r['belastbaar_jaar'],
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
