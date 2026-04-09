# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _get_sr_artikel14_breakdown(self):
        """
        Berekent de tussenliggende Artikel 14 stappen voor weergave op de loonstrook.

        Leest dezelfde datumgebonden parameters als de SR_LB salarisregel,
        zodat de loonstrookweergave altijd overeenkomt met de werkelijke berekening.

        Geeft een dict terug met alle tussenliggende bedragen en labels.
        Geeft een leeg dict terug als de loonstrook nog geen regels heeft.
        """
        self.ensure_one()

        if not self.date_from or not self.line_ids:
            return {}

        contract = self.contract_id
        periodes_per_jaar = 26 if getattr(contract, 'sr_salary_type', 'monthly') == 'fn' else 12

        # ── Loonstrookregels ophalen ──────────────────────────────────────────
        def _line_total(code):
            line = self.line_ids.filtered(lambda l: l.code == code)
            return line.total if line else 0.0

        basic = _line_total('BASIC')
        toelagen = _line_total('SR_ALW')
        kinderbijslag = _line_total('SR_KINDBIJ')
        # GROSS = BASIC + SR_ALW (excl. kinderbijslag — niet belastbaar)
        gross = _line_total('GROSS')
        pensioen = abs(_line_total('SR_PENSIOEN'))

        bruto_per_periode = gross
        bruto_jaarloon = bruto_per_periode * periodes_per_jaar

        # ── Artikel 12 — Forfaitaire beroepskosten ────────────────────────────
        forfaitaire_pct = self._rule_parameter('SR_FORFAITAIRE_PCT')
        forfaitaire_max = self._rule_parameter('SR_FORFAITAIRE_MAX_JAAR')
        forfaitaire_jaar = min(bruto_jaarloon * forfaitaire_pct, forfaitaire_max)

        # ── Artikel 13 — Belastingvrije som ───────────────────────────────────
        belastingvrij_jaar = self._rule_parameter('SR_BELASTINGVRIJ_JAAR')

        # ── Belastbaar jaarloon ───────────────────────────────────────────────
        belastbaar_jaarloon = max(0.0, bruto_jaarloon - belastingvrij_jaar - forfaitaire_jaar)

        # ── Artikel 14 — Tariefschijven ───────────────────────────────────────
        s1 = self._rule_parameter('SR_SCHIJF_1_GRENS')
        s2 = self._rule_parameter('SR_SCHIJF_2_GRENS')
        s3 = self._rule_parameter('SR_SCHIJF_3_GRENS')
        r1 = self._rule_parameter('SR_TARIEF_1')
        r2 = self._rule_parameter('SR_TARIEF_2')
        r3 = self._rule_parameter('SR_TARIEF_3')
        r4 = self._rule_parameter('SR_TARIEF_4')

        s1_basis = min(belastbaar_jaarloon, s1)
        s2_basis = max(0.0, min(belastbaar_jaarloon - s1, s2 - s1))
        s3_basis = max(0.0, min(belastbaar_jaarloon - s2, s3 - s2))
        s4_basis = max(0.0, belastbaar_jaarloon - s3)

        lb_s1 = s1_basis * r1
        lb_s2 = s2_basis * r2
        lb_s3 = s3_basis * r3
        lb_s4 = s4_basis * r4
        lb_voor_heffingskorting = lb_s1 + lb_s2 + lb_s3 + lb_s4

        # ── Heffingskorting ───────────────────────────────────────────────────
        heffingskorting_maand = self._rule_parameter('SR_HEFFINGSKORTING_MAAND')
        heffingskorting_jaar = heffingskorting_maand * 12
        lb_jaar_netto = max(0.0, lb_voor_heffingskorting - heffingskorting_jaar)
        lb_per_periode = lb_jaar_netto / periodes_per_jaar

        # ── AOV ───────────────────────────────────────────────────────────────
        aov_tarief = self._rule_parameter('SR_AOV_TARIEF')
        aov_franchise_maand = self._rule_parameter('SR_AOV_FRANCHISE_MAAND')
        franchise_periode = aov_franchise_maand if periodes_per_jaar == 12 else 0.0
        aov_grondslag = max(0.0, bruto_per_periode - franchise_periode)
        aov_per_periode = aov_grondslag * aov_tarief

        totaal_inhoudingen = lb_per_periode + aov_per_periode + pensioen
        netto = basic + toelagen + kinderbijslag - totaal_inhoudingen

        return {
            # Basis
            'periodes': periodes_per_jaar,
            'is_fn': periodes_per_jaar == 26,
            'basic': basic,
            'toelagen': toelagen,
            'kinderbijslag': kinderbijslag,
            'bruto_per_periode': bruto_per_periode,
            'bruto_totaal': basic + toelagen + kinderbijslag,
            # Artikel 14 stappen
            'bruto_jaarloon': bruto_jaarloon,
            'belastingvrij_jaar': belastingvrij_jaar,
            'forfaitaire_pct': forfaitaire_pct * 100,
            'forfaitaire_jaar': forfaitaire_jaar,
            'belastbaar_jaarloon': belastbaar_jaarloon,
            # Schijfgrenzen (voor labels)
            's1_grens': s1,
            's2_grens': s2,
            's3_grens': s3,
            # Schijfbedragen (belastbaar deel per schijf)
            's1_basis': s1_basis,
            's2_basis': s2_basis,
            's3_basis': s3_basis,
            's4_basis': s4_basis,
            # Belasting per schijf
            'r1_pct': r1 * 100,
            'r2_pct': r2 * 100,
            'r3_pct': r3 * 100,
            'r4_pct': r4 * 100,
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
            'aov_tarief_pct': aov_tarief * 100,
            'aov_per_periode': aov_per_periode,
            # Samenvatting
            'pensioen': pensioen,
            'totaal_inhoudingen': totaal_inhoudingen,
            'netto': netto,
        }
