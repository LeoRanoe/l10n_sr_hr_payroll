# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as Date

from odoo import api, fields, models


class HrContract(models.Model):
    _inherit = 'hr.contract'

    sr_salary_type = fields.Selection(
        selection=[
            ('monthly', 'Maandloon (12× per jaar)'),
            ('fn', 'Fortnight Loon (26× per jaar)'),
        ],
        string='Surinaams Loontype',
        default='monthly',
        help='Selecteer het betaaltype: maandloon (12 periodes) of fortnight (26 periodes per jaar).',
    )
    sr_toelagen = fields.Monetary(
        string='Toelagen (Belastbaar)',
        currency_field='currency_id',
        default=0.0,
        help='Belastbare toelagen per loonperiode (bijv. vervoerskostenvergoeding die als loon belast wordt).',
    )
    sr_kinderbijslag = fields.Monetary(
        string='Kinderbijslag',
        currency_field='currency_id',
        default=0.0,
        help='Kinderbijslag per loonperiode — belastingvrij voordeel, wordt niet meegenomen in de loonbelastingberekening.',
    )
    sr_pensioenpremie = fields.Monetary(
        string='Pensioenpremie (werknemer)',
        currency_field='currency_id',
        default=0.0,
        help='Werknemerspremie pensioenfonds per loonperiode.',
    )

    # ── Rekenvoorbeeld — live Artikel 14 preview ──────────────────────────
    # Berekent een schatting op basis van de huidig ingevulde contractwaarden.
    # Gebruikt dezelfde formules als de SR_LB / SR_AOV salarisregels.

    sr_preview_bruto = fields.Monetary(
        string='Bruto Loon',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_belastbaar_jaar = fields.Monetary(
        string='Belastbaar Jaarloon',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_lb_periode = fields.Monetary(
        string='Loonbelasting per Periode',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_aov_periode = fields.Monetary(
        string='AOV per Periode',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )
    sr_preview_netto = fields.Monetary(
        string='Geschat Nettoloon',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
    )

    @api.depends('wage', 'sr_toelagen', 'sr_kinderbijslag',
                 'sr_pensioenpremie', 'sr_salary_type')
    def _compute_sr_preview(self):
        """
        Live preview van de Artikel 14 WLB loonbelasting berekening.
        Leest datumgebonden parameters uit hr.rule.parameter.
        Valt terug op ingebakken 2026-waarden als parameters niet gevonden worden.
        """
        today = Date.today()
        RuleParam = self.env['hr.rule.parameter']

        def _p(code, fallback):
            val = RuleParam._get_parameter_from_code(code, today, raise_if_not_found=False)
            return val if val is not None else fallback

        belastingvrij_jaar = _p('SR_BELASTINGVRIJ_JAAR', 108000.0)
        forfaitaire_pct    = _p('SR_FORFAITAIRE_PCT', 0.04)
        forfaitaire_max    = _p('SR_FORFAITAIRE_MAX_JAAR', 4800.0)
        s1 = _p('SR_SCHIJF_1_GRENS', 42000.0)
        s2 = _p('SR_SCHIJF_2_GRENS', 84000.0)
        s3 = _p('SR_SCHIJF_3_GRENS', 126000.0)
        r1 = _p('SR_TARIEF_1', 0.08)
        r2 = _p('SR_TARIEF_2', 0.18)
        r3 = _p('SR_TARIEF_3', 0.28)
        r4 = _p('SR_TARIEF_4', 0.38)
        hk_maand = _p('SR_HEFFINGSKORTING_MAAND', 750.0)
        aov_pct   = _p('SR_AOV_TARIEF', 0.04)
        franchise = _p('SR_AOV_FRANCHISE_MAAND', 400.0)

        for contract in self:
            periodes = 26 if contract.sr_salary_type == 'fn' else 12
            bruto_belastbaar = (contract.wage or 0.0) + (contract.sr_toelagen or 0.0)
            bruto_jaar = bruto_belastbaar * periodes

            # Artikel 12 + 13
            forfaitaire = min(bruto_jaar * forfaitaire_pct, forfaitaire_max)
            belastbaar_jaar = max(0.0, bruto_jaar - belastingvrij_jaar - forfaitaire)

            # Artikel 14 — rtiefschijven
            if belastbaar_jaar <= s1:
                lb_jaar = belastbaar_jaar * r1
            elif belastbaar_jaar <= s2:
                lb_jaar = (s1 * r1) + ((belastbaar_jaar - s1) * r2)
            elif belastbaar_jaar <= s3:
                lb_jaar = (s1 * r1) + ((s2 - s1) * r2) + ((belastbaar_jaar - s2) * r3)
            else:
                lb_jaar = (
                    (s1 * r1) + ((s2 - s1) * r2)
                    + ((s3 - s2) * r3) + ((belastbaar_jaar - s3) * r4)
                )

            lb_jaar_netto = max(0.0, lb_jaar - (hk_maand * 12))
            lb_periode = lb_jaar_netto / periodes

            # AOV — geen franchise voor fortnight
            franchise_periode = franchise if periodes == 12 else 0.0
            aov = max(0.0, bruto_belastbaar - franchise_periode) * aov_pct

            kinderbijslag = contract.sr_kinderbijslag or 0.0
            pensioen = contract.sr_pensioenpremie or 0.0
            bruto_totaal = bruto_belastbaar + kinderbijslag

            contract.sr_preview_bruto = bruto_totaal
            contract.sr_preview_belastbaar_jaar = belastbaar_jaar
            contract.sr_preview_lb_periode = lb_periode
            contract.sr_preview_aov_periode = aov
            contract.sr_preview_netto = bruto_totaal - lb_periode - aov - pensioen
