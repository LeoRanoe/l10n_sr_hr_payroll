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

    # ── Flexibele vaste loon regels (debit / credit) ───────────────────────
    # De eindgebruiker beheert hier zijn eigen toeslagen en inhoudingen.
    # Categorieën:
    #   belastbaar  → telt mee in de Art. 14 loonbelastinggrondslag
    #   vrijgesteld → Art. 10 WLB belastingvrij voordeel
    #   inhouding   → netto aftrek (pensioenpremie, ziektekostenpremie, etc.)
    sr_vaste_regels = fields.One2many(
        comodel_name='hr.contract.sr.line',
        inverse_name='contract_id',
        string='Vaste Loon Regels',
        help=(
            'Vaste bedragen die elke loonperiode verwerkt worden.\n\n'
            'Voeg hier toe:\n'
            '• Toeslagen (olie, kleding, representatie, ...) → Belastbaar of Belastingvrij\n'
            '• Inhoudingen (pensioenpremie, ziektekostenpremie, ...) → Inhouding\n\n'
            'Voor eenmalige of variabele bedragen (overwerk, vakantietoelage, bonus): '
            'gebruik de Payslip inputs bij het aanmaken van de loonstrook.'
        ),
    )

    # ── Rekenvoorbeeld — live Artikel 14 preview ──────────────────────────
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

    @api.depends(
        'wage',
        'sr_salary_type',
        'sr_vaste_regels.amount',
        'sr_vaste_regels.sr_categorie',
    )
    def _compute_sr_preview(self):
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
        aov_pct  = _p('SR_AOV_TARIEF', 0.04)
        franchise = _p('SR_AOV_FRANCHISE_MAAND', 400.0)

        for contract in self:
            periodes = 26 if contract.sr_salary_type == 'fn' else 12

            belastbaar_toelagen = sum(
                r.amount for r in contract.sr_vaste_regels if r.sr_categorie == 'belastbaar'
            )
            vrijgesteld_toelagen = sum(
                r.amount for r in contract.sr_vaste_regels if r.sr_categorie == 'vrijgesteld'
            )
            inhoudingen = sum(
                r.amount for r in contract.sr_vaste_regels if r.sr_categorie == 'inhouding'
            )

            bruto_belastbaar = (contract.wage or 0.0) + belastbaar_toelagen
            bruto_jaar = bruto_belastbaar * periodes

            forfaitaire = min(bruto_jaar * forfaitaire_pct, forfaitaire_max)
            belastbaar_jaar = max(0.0, bruto_jaar - belastingvrij_jaar - forfaitaire)

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

            franchise_periode = franchise if periodes == 12 else 0.0
            aov = max(0.0, bruto_belastbaar - franchise_periode) * aov_pct

            bruto_totaal = bruto_belastbaar + vrijgesteld_toelagen

            contract.sr_preview_bruto = bruto_totaal
            contract.sr_preview_belastbaar_jaar = belastbaar_jaar
            contract.sr_preview_lb_periode = lb_periode
            contract.sr_preview_aov_periode = aov
            contract.sr_preview_netto = bruto_totaal - lb_periode - aov - inhoudingen
