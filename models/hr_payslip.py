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
        berekeningen te voorkomen wanneer SR_LB, SR_HK en SR_AOV regels
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
        Berekent Artikel 14 loonbelasting BRUTO per periode (vóór heffingskorting).

        Wordt aangeroepen door de SR_LB salarisregel.
        Gebruikt de centrale calculator zodat de berekening altijd
        overeenkomt met de contract preview.

        :param gross_per_periode: Bruto belastbaar loon per periode (categories['GROSS'])
        :param aftrek_bv: Aftrek belastingvrij per periode (Art. 10f, bijv. pensioenpremie)
        :returns: positief bedrag loonbelasting BRUTO per periode
        """
        return self._sr_get_cached_result(gross_per_periode, aftrek_bv)['lb_gross_per_periode']

    def _sr_artikel14_hk(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent de heffingskorting per periode.

        Wordt aangeroepen door de SR_HK salarisregel.
        De heffingskorting wordt apart teruggegeven zodat de loonstrook
        de bruto LB en de HK transparant kan tonen.

        :param gross_per_periode: Bruto belastbaar loon per periode (categories['GROSS'])
        :param aftrek_bv: Aftrek belastingvrij per periode (Art. 10f)
        :returns: positief bedrag heffingskorting per periode
        """
        return self._sr_get_cached_result(gross_per_periode, aftrek_bv)['heffingskorting_per_periode']

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
        kinderbijslag = _line_total('SR_KINDBIJ')
        pensioen = abs(_line_total('SR_PENSIOEN'))

        # ── Calculator aanroepen ──────────────────────────────────────────────
        # Gebruik basic + toelagen als Art. 14 grondslag — dit is dezelfde waarde
        # die de SR_LB regel gebruikt (categories['GROSS'] op seq 30, vóór SR_KINDBIJ).
        # Hierdoor klopt het rapport altijd met de werkelijke SR_LB berekening.
        gross = basic + toelagen
        params = calc.fetch_params_from_payslip(self)
        r = calc.calculate_lb(gross, periodes, params)

        totaal_inhoudingen = r['lb_per_periode'] + r['aov_per_periode'] + pensioen
        netto = basic + toelagen + kinderbijslag - totaal_inhoudingen

        return {
            # Basis
            'periodes': periodes,
            'is_fn': periodes == 26,
            'basic': basic,
            'toelagen': toelagen,
            'kinderbijslag': kinderbijslag,
            'bruto_per_periode': gross,
            'bruto_totaal': basic + toelagen + kinderbijslag,
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
            'lb_voor_heffingskorting': r['lb_voor_heffingskorting'],
            'heffingskorting_jaar': r['heffingskorting_jaar'],
            'lb_jaar_netto': r['lb_jaar_netto'],
            'lb_per_periode': r['lb_per_periode'],
            'lb_gross_per_periode': r['lb_gross_per_periode'],
            'heffingskorting_per_periode': r['heffingskorting_per_periode'],
            # AOV
            'franchise_periode': r['franchise_periode'],
            'aov_grondslag': r['aov_grondslag'],
            'aov_tarief_pct': r['aov_tarief'] * 100,
            'aov_per_periode': r['aov_per_periode'],
            # Samenvatting
            'pensioen': pensioen,
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
