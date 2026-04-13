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

    def _sr_get_aftrek_bv(self):
        """
        Berekent het totale aftrek belastingvrij bedrag per periode.

        Optelsom van vaste contractregels met categorie 'aftrek_belastingvrij'
        (Art. 10f — pensioenpremie etc.).
        """
        self.ensure_one()
        return self.contract_id._sr_resolve_regels('aftrek_belastingvrij')

    def _sr_artikel14_lb(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent Artikel 14 BRUTO loonbelasting per periode (vóór heffingskorting).

        Wordt aangeroepen door de SR_LB salarisregel.

        :param gross_per_periode: Bruto belastbaar loon per periode (categories['GROSS'])
        :param aftrek_bv: Aftrek belastingvrij per periode (Art. 10f pensioenpremie)
        :returns: positief bedrag bruto loonbelasting per periode
        """
        self.ensure_one()
        params = calc.fetch_params_from_payslip(self)
        periodes = self._sr_get_periodes()
        result = calc.calculate_lb(gross_per_periode, periodes, params,
                                   aftrek_bv_per_periode=aftrek_bv)
        return result['lb_gross_per_periode']

    def _sr_artikel14_hk(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent heffingskorting per periode.

        Wordt aangeroepen door de SR_HK salarisregel.

        :param gross_per_periode: Bruto belastbaar loon per periode
        :param aftrek_bv: Aftrek belastingvrij per periode
        :returns: positief bedrag heffingskorting per periode
        """
        self.ensure_one()
        params = calc.fetch_params_from_payslip(self)
        periodes = self._sr_get_periodes()
        result = calc.calculate_lb(gross_per_periode, periodes, params,
                                   aftrek_bv_per_periode=aftrek_bv)
        return result['heffingskorting_per_periode']

    def _sr_artikel14_aov(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent AOV bijdrage per periode.

        Wordt aangeroepen door de SR_AOV salarisregel.

        :param gross_per_periode: Bruto belastbaar loon per periode
        :param aftrek_bv: Aftrek belastingvrij per periode
        :returns: positief bedrag AOV per periode
        """
        self.ensure_one()
        params = calc.fetch_params_from_payslip(self)
        periodes = self._sr_get_periodes()
        result = calc.calculate_lb(gross_per_periode, periodes, params,
                                   aftrek_bv_per_periode=aftrek_bv)
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

        try:
            contract = self.contract_id
            periodes = self._sr_get_periodes()

            # ── Loonstrookregels ophalen ──────────────────────────────────────────
            def _line_total(code):
                lines = self.line_ids.filtered(lambda l: l.code == code)
                return sum(lines.mapped('total')) if lines else 0.0

            basic = _line_total('BASIC')
            toelagen = _line_total('SR_ALW')
            kb_belastbaar = _line_total('SR_KB_BELAST')
            kb_vrijgesteld = _line_total('SR_KB_VRIJ')
            other_vrijgesteld = _line_total('SR_KINDBIJ')
            aftrek_bv = abs(_line_total('SR_AFTREK_BV'))
            pensioen = abs(_line_total('SR_PENSIOEN'))
            heffingskorting = _line_total('SR_HK')

            # ── Calculator aanroepen ──────────────────────────────────────────────
            gross = basic + toelagen + kb_belastbaar
            aftrek_bv_calc = contract._sr_resolve_regels('aftrek_belastingvrij')
            params = calc.fetch_params_from_payslip(self)

            if not all(params.values()):
                return {}

            r = calc.calculate_lb(gross, periodes, params,
                                  aftrek_bv_per_periode=aftrek_bv_calc)

            totaal_inhoudingen = (
                r['lb_gross_per_periode']
                - r['heffingskorting_per_periode']
                + r['aov_per_periode']
                + pensioen
                + aftrek_bv
            )
            bruto_totaal = gross + kb_vrijgesteld + other_vrijgesteld
            netto = bruto_totaal + heffingskorting - r['lb_gross_per_periode'] - r['aov_per_periode'] - pensioen - aftrek_bv

            return {
                # Basis
                'periodes': periodes,
                'is_fn': periodes == 26,
                'basic': basic,
                'toelagen': toelagen,
                'kb_belastbaar': kb_belastbaar,
                'kb_vrijgesteld': kb_vrijgesteld,
                'other_vrijgesteld': other_vrijgesteld,
                'bruto_per_periode': gross,
                'bruto_totaal': bruto_totaal,
                # Aftrek belastingvrij
                'aftrek_bv': aftrek_bv_calc,
                'adjusted_bruto_jaar': r['adjusted_bruto_jaar'],
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
                'heffingskorting_per_periode': r['heffingskorting_per_periode'],
                'lb_gross_per_periode': r['lb_gross_per_periode'],
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
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.exception(f"Error in _get_sr_artikel14_breakdown for payslip {self.id}: {str(e)}")
            return {}

    def action_print_sr_payslip(self):
        """
        Direct actie om de Surinaamse loonstrook als PDF te openen.

        Wordt aangeroepen via de 'Loonstrook' stat-knop op het payslip-formulier.
        Toont de loonstrook alleen als de SR-loonstructuur is geselecteerd.
        """
        self.ensure_one()
        return self.env.ref('l10n_sr_hr_payroll.action_report_payslip_sr').report_action(self)

    def action_preview_sr_payslip(self):
        """
        Direct actie om de Surinaamse loonstrook als HTML preview te openen.

        Handige preview zonder PDF-download — toont de loonstrook inline
        in de browser. Zichtbaar als stat-knop op het payslip-formulier.
        """
        self.ensure_one()
        return self.env.ref('l10n_sr_hr_payroll.action_report_payslip_sr_preview').report_action(self)
