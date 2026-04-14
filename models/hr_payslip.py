# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models

from . import sr_artikel14_calculator as calc


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _sr_get_periodes(self):
        """Bepaalt het aantal periodes per jaar: 12 (maandloon) of 26 (fortnight)."""
        self.ensure_one()
        contract = self.contract_id
        return 26 if getattr(contract, 'sr_salary_type', 'monthly') == 'fn' else 12

    def _sr_artikel14_lb(self, gross_per_periode):
        """
        Berekent Artikel 14 loonbelasting per periode.

        Wordt aangeroepen door de SR_LB salarisregel.
        Gebruikt de centrale calculator zodat de berekening altijd
        overeenkomt met de contract preview.

        :param gross_per_periode: Bruto belastbaar loon per periode (categories['GROSS'])
        :returns: positief bedrag loonbelasting per periode
        """
        self.ensure_one()
        params = calc.fetch_params_from_payslip(self)
        periodes = self._sr_get_periodes()
        result = calc.calculate_lb(gross_per_periode, periodes, params)
        return result['lb_per_periode']

    def _sr_artikel14_aov(self, gross_per_periode):
        """
        Berekent AOV bijdrage per periode.

        Wordt aangeroepen door de SR_AOV salarisregel.

        :param gross_per_periode: Bruto belastbaar loon per periode
        :returns: positief bedrag AOV per periode
        """
        self.ensure_one()
        params = calc.fetch_params_from_payslip(self)
        periodes = self._sr_get_periodes()
        result = calc.calculate_lb(gross_per_periode, periodes, params)
        return result['aov_per_periode']

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
