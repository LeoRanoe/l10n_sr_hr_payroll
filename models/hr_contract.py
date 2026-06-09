# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as Date
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_compare

from . import sr_artikel14_calculator as calc


SR_STANDARD_SHORTCUT_CODES = frozenset({'KINDBIJ', 'TRANSPORT', 'REPRES', 'GENEESK'})
SR_INTERNAL_MONEY_QUANT = Decimal('0.000001')
SR_STRUCTURE_TYPE_XMLIDS = (
    'l10n_sr_hr_payroll.sr_payroll_structure_type',
    'l10n_sr_hr_payroll.sr_payroll_structure_type_hourly',
)


class HrContract(models.Model):
    _inherit = 'hr.contract'

    SR_AKB_MAX_CHILDREN = 4
    SR_FOREIGN_WAGE_WARNING_THRESHOLD = 1000.0
    SR_CONTRACT_LINE_FIELD_MAP = {
        'sr_kinderbijslag_bedrag': {
            'code': 'KINDBIJ',
            'xmlid': 'l10n_sr_hr_payroll.sr_line_type_kinderbijslag',
            'name': 'Kinderbijslag',
            'category': 'vrijgesteld',
            'fallback_names': ('kinderbijslag',),
        },
        'sr_vervoer_toelage': {
            'code': 'TRANSPORT',
            'xmlid': 'l10n_sr_hr_payroll.sr_line_type_transport',
            'name': 'Transportvergoeding',
            'category': 'vrijgesteld',
            'fallback_names': ('transportvergoeding', 'transport', 'vervoer'),
        },
        'sr_representatie_toelage': {
            'code': 'REPRES',
            'xmlid': 'l10n_sr_hr_payroll.sr_line_type_representatie',
            'name': 'Representatie Toelage',
            'category': 'belastbaar',
            'fallback_names': ('representatie toelage', 'representatie'),
        },
        'sr_vrije_geneeskundige_behandeling': {
            'code': 'GENEESK',
            'xmlid': 'l10n_sr_hr_payroll.sr_line_type_geneeskunde',
            'name': 'Vrije Geneeskundige Behandeling',
            'category': 'fiscaal_grondslag',
            'fallback_names': ('vrije geneeskundige behandeling', 'geneeskundige behandeling'),
        },
    }

    sr_salary_type = fields.Selection(
        selection=[
            ('monthly', 'Maandloon (12 periodes)'),
            ('fn', 'FN-loon (26 periodes)'),
        ],
        string='Surinaams loontype',
        default='monthly',
        store=True,
        help='Selecteer het betaaltype: maandloon (12 periodes per jaar) of FN-loon (26 periodes per jaar).',
    )

    sr_aantal_kinderen = fields.Integer(
        string='Aantal Kinderen',
        default=0,
        store=True,
        help=(
            'Aantal kinderen waarvoor kinderbijslag wordt betaald.\n'
            'Gebruikt voor de Art. 10h splitsing: max SRD 250/kind/maand, '
            'max SRD 1.000/maand is belastingvrij. Het meerdere is belastbaar.\n'
            'Maximaal 4 kinderen zijn toegestaan voor de AKB-vrijstelling.'
        ),
    )

    sr_has_overtime_right = fields.Boolean(
        string='Heeft Overwerkrecht',
        default=True,
        store=True,
        help=(
            'Overwerk kan worden uitbetaald als variabel bedrag op basis van geregistreerde uren.\n'
            'Als uitgevinkt worden extra uren wel geregistreerd maar NIET als variabel overwerk uitbetaald.\n'
            'Gebruik de Vaste Loon Regels voor een vaste periodieke overwerktoeslag.'
        ),
    )

    sr_contract_currency = fields.Many2one(
        'res.currency',
        string='Contractvaluta',
        domain=[('name', 'in', ['SRD', 'USD', 'EUR'])],
        default=lambda self: (
            self.env.company.sr_default_contract_currency_id
            or self.env['res.currency'].search([('name', '=', 'SRD')], limit=1)
            or self.env.company.currency_id
        ),
        store=True,
        copy=True,
        help=(
            'Valuta waarin het basisloon is uitgedrukt. '
            'Kies SRD (standaard), USD of EUR. '
            'Elke vaste loon regel (toelage / inhouding) heeft een eigen valuta die standaard '
            'gelijk is aan de contractvaluta maar individueel instelbaar is. '
            'Bij loonverwerking worden alle bedragen omgerekend naar SRD '
            'via de actuele wisselkoers uit SR Payroll Instellingen. '
            'De gehanteerde koers wordt per loonstrook bevroren opgeslagen.'
        ),
    )
    sr_show_contract_shortcuts = fields.Boolean(
        string='Toon standaard contract-shortcuts',
        related='company_id.sr_show_contract_shortcuts',
        store=False,
        readonly=True,
    )
    sr_contract_shortcut_type_ids = fields.Many2many(
        related='company_id.sr_contract_shortcut_type_ids',
        string='Contract shortcut types',
        store=False,
        readonly=True,
    )
    sr_has_contract_shortcut_types = fields.Boolean(
        string='Heeft gekozen shortcut types',
        compute='_compute_sr_has_contract_shortcut_types',
        store=False,
    )
    sr_has_kinderbijslag_shortcut = fields.Boolean(
        string='Toon Kinderbijslag shortcut',
        compute='_compute_sr_shortcut_ui_flags',
        store=False,
    )
    sr_has_transport_shortcut = fields.Boolean(
        string='Toon Transport shortcut',
        compute='_compute_sr_shortcut_ui_flags',
        store=False,
    )
    sr_has_representatie_shortcut = fields.Boolean(
        string='Toon Representatie shortcut',
        compute='_compute_sr_shortcut_ui_flags',
        store=False,
    )
    sr_has_geneeskundige_shortcut = fields.Boolean(
        string='Toon Geneeskundige shortcut',
        compute='_compute_sr_shortcut_ui_flags',
        store=False,
    )
    sr_has_custom_contract_shortcut_types = fields.Boolean(
        string='Heeft eigen shortcut types',
        compute='_compute_sr_shortcut_ui_flags',
        store=False,
    )

    @api.model
    def _sr_get_structure_types(self):
        structure_types = self.env['hr.payroll.structure.type']
        for xmlid in SR_STRUCTURE_TYPE_XMLIDS:
            structure_type = self.env.ref(xmlid, raise_if_not_found=False)
            if structure_type:
                structure_types |= structure_type
        return structure_types

    @api.depends('company_id')
    def _compute_structure_type_id(self):
        super()._compute_structure_type_id()
        sr_default_structure_type = self.env.ref(
            'l10n_sr_hr_payroll.sr_payroll_structure_type',
            raise_if_not_found=False,
        )
        sr_structure_types = self._sr_get_structure_types()

        for contract in self:
            if contract.company_id.country_id.code != 'SR' or not sr_default_structure_type:
                continue
            if not contract.structure_type_id or contract.structure_type_id not in sr_structure_types:
                contract.structure_type_id = sr_default_structure_type

    sr_hourly_wage = fields.Float(
        string='Uurloon (SRD)',
        digits=(16, 4),
        compute='_compute_sr_hourly_wage',
        help='Bruto uurloon in SRD: maandloon ÷ 173,33 (geldt voor zowel maandloon als FN).',
    )
    sr_current_exchange_rate_display = fields.Float(
        string='Actuele Wisselkoers',
        digits=(16, 6),
        compute='_compute_sr_currency_pair_display',
        store=False,
        help='Huidige wisselkoers voor de contractvaluta vanuit de bedrijfsinstellingen (niet bevroren).',
    )
    sr_wage_srd = fields.Monetary(
        string='Basisloon in SRD',
        currency_field='currency_id',
        compute='_compute_sr_currency_pair_display',
        store=False,
        help='Maandloon omgerekend naar SRD op basis van de actuele wisselkoers.',
    )
    sr_wage_per_period_srd = fields.Monetary(
        string='Loon per FN-periode (SRD)',
        currency_field='currency_id',
        compute='_compute_sr_wage_per_period',
        store=False,
        help='Automatisch berekend: maandloon × 12 ÷ 26. Dit bedrag wordt bij FN als BASIC op de loonstrook gebruikt.',
    )
    sr_kinderbijslag_bedrag = fields.Monetary(
        string='Kinderbijslag per Kind per Maand',
        currency_field='currency_id',
        compute='_compute_sr_named_contract_lines',
        inverse='_inverse_sr_kinderbijslag_bedrag',
        store=True,
        precompute=True,
        help='Snelle contractinvoer voor de kinderbijslagregel. Bedrag is per kind per maand; FN rekent dit naar per periode om.',
    )
    sr_vervoer_toelage = fields.Monetary(
        string='Vervoer / Transport',
        currency_field='currency_id',
        compute='_compute_sr_named_contract_lines',
        inverse='_inverse_sr_vervoer_toelage',
        store=True,
        precompute=True,
        help='Vaste transportvergoeding per periode. Wordt als SR contractregel opgeslagen.',
    )
    sr_representatie_toelage = fields.Monetary(
        string='Representatie',
        currency_field='currency_id',
        compute='_compute_sr_named_contract_lines',
        inverse='_inverse_sr_representatie_toelage',
        store=True,
        precompute=True,
        help='Vaste representatietoelage per periode. Wordt als SR contractregel opgeslagen.',
    )
    sr_vrije_geneeskundige_behandeling = fields.Monetary(
        string='Vrije Geneeskundige Behandeling',
        currency_field='currency_id',
        compute='_compute_sr_named_contract_lines',
        inverse='_inverse_sr_vrije_geneeskundige_behandeling',
        store=True,
        precompute=True,
        help='Vaste geneeskundige behandeling per periode. Wordt als belastbare SR contractregel opgeslagen.',
    )

    # ── Flexibele vaste loon regels (debit / credit) ───────────────────────
    sr_vaste_regels = fields.One2many(
        comodel_name='hr.contract.sr.line',
        inverse_name='contract_id',
        string='Vaste Loon Regels',
        help=(
            'Vaste bedragen die elke loonperiode verwerkt worden.\n\n'
            'Voeg hier toe:\n'
            '• Toeslagen (olie, kleding, representatie, ...) → Belastbaar of Belastingvrij\n'
            '• Pensioenpremie en Art. 10f inhoudingen → Aftrek Belastingvrij\n'
            '• Overige netto-inhoudingen (ziektekosten, lening, vakbond) → Inhouding\n\n'
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
    sr_preview_belastinggrondslag = fields.Monetary(
        string='Grondslag voor Belasting',
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
    sr_preview_netto_jaar = fields.Monetary(
        string='Verwacht Netto per Jaar',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
        help='Voor maandloon: geschat netto per maand × 12. Voor FN: verwacht jaartotaal inclusief de eventuele FN26-jaarafronding.',
    )
    sr_preview_fn26_correctie = fields.Monetary(
        string='Verwachte FN26 Jaarafronding',
        currency_field='currency_id',
        compute='_compute_sr_preview',
        store=False,
        help='Kleine positieve of negatieve slotcorrectie die alleen op FN26 nodig kan zijn om 26 FN-betalingen exact te laten aansluiten op het maandjaartotaal.',
    )
    sr_preview_breakdown_html = fields.Html(
        string='Berekeningsdetail',
        compute='_compute_sr_preview',
        store=False,
        sanitize=False,
    )

    # ── Dynamische tarieftabel (uit parameters) ────────────────────────────
    sr_tax_bracket_html = fields.Html(
        string='Tariefschijven',
        compute='_compute_sr_tax_bracket_html',
        store=False,
        sanitize=False,
    )

    @api.depends('company_id.sr_contract_shortcut_type_ids')
    def _compute_sr_has_contract_shortcut_types(self):
        for contract in self:
            contract.sr_has_contract_shortcut_types = bool(contract.company_id.sr_contract_shortcut_type_ids)

    @api.depends('company_id.sr_contract_shortcut_type_ids', 'company_id.sr_contract_shortcut_type_ids.code')
    def _compute_sr_shortcut_ui_flags(self):
        for contract in self:
            selected_codes = set(contract.company_id.sr_contract_shortcut_type_ids.mapped('code'))
            contract.sr_has_kinderbijslag_shortcut = 'KINDBIJ' in selected_codes
            contract.sr_has_transport_shortcut = 'TRANSPORT' in selected_codes
            contract.sr_has_representatie_shortcut = 'REPRES' in selected_codes
            contract.sr_has_geneeskundige_shortcut = 'GENEESK' in selected_codes
            contract.sr_has_custom_contract_shortcut_types = any(
                code not in SR_STANDARD_SHORTCUT_CODES
                for code in selected_codes
            )

    @api.depends(
        'wage',
        'sr_salary_type',
        'sr_aantal_kinderen',
        'sr_contract_currency',
        'sr_vaste_regels.type_id',
        'sr_vaste_regels.name',
        'sr_vaste_regels.amount',
        'sr_vaste_regels.sr_categorie',
        'sr_vaste_regels.amount_type',
        'sr_vaste_regels.percentage',
        'sr_vaste_regels.percentage_base',
        'sr_vaste_regels.line_currency_id',
        'company_id.sr_exchange_rate_usd',
        'company_id.sr_exchange_rate_eur',
    )
    def _compute_sr_preview(self):
        """
        Berekent Art. 14 loonbelasting preview op basis van contractwaarden.

        Gebruikt de centrale sr_artikel14_calculator zodat preview altijd
        overeenkomt met de werkelijke payslip berekening.
        Loon wordt eerst omgerekend naar SRD op basis van de actuele wisselkoers.
        """
        today = Date.today()
        params = calc.fetch_params_from_rule_parameter(self.env, today)

        for contract in self:
            periodes = 26 if contract.sr_salary_type == 'fn' else 12
            # The 2026 WLB calculation uses the Art. 13 belastingvrije som.
            # A separate heffingskorting is kept as a legacy setting only.
            heffingskorting = 0.0

            rate = contract._sr_get_current_exchange_rate()
            belastbaar_toelagen = contract._sr_resolve_regels('belastbaar', exchange_rate=rate, round_result=False)
            vrijgesteld_toelagen = contract._sr_resolve_other_vrijgestelde_regels(exchange_rate=rate, round_result=False)
            inhoudingen = contract._sr_resolve_regels('inhouding', exchange_rate=rate, round_result=False)
            aftrek_bv = contract._sr_resolve_regels('aftrek_belastingvrij', exchange_rate=rate, round_result=False)

            # Kinderbijslag splitsing (Art. 10h)
            kb_split = contract._sr_kinderbijslag_split(exchange_rate=rate, round_result=False)
            kb_belastbaar = kb_split['belastbaar']
            kb_vrijgesteld = kb_split['vrijgesteld']

            # VGB fiscaal belastbaar deel (Art. 9 WLB — voordeel in natura, max SR_VGB_MAX_JAAR)
            vgb_belastbaar = contract._sr_vgb_fiscaal_belastbaar(exchange_rate=rate, round_result=False)

            # Basisloon per periode in SRD (FN: maandloon × 12/26)
            wage_per_period = contract._sr_get_wage_per_period_srd(exchange_rate=rate, round_result=False)

            # Bruto belastbaar = basisloon per periode + belastbare toelagen + KB belastbaar + VGB fiscaal
            bruto_belastbaar = wage_per_period + belastbaar_toelagen + kb_belastbaar + vgb_belastbaar
            result = calc.calculate_lb(
                bruto_belastbaar, periodes, params,
                aftrek_bv_per_periode=aftrek_bv,
                heffingskorting_per_periode=heffingskorting,
            )

            bruto_totaal = wage_per_period + belastbaar_toelagen + kb_belastbaar + kb_vrijgesteld + vrijgesteld_toelagen
            contract.sr_preview_bruto = calc.round_money(bruto_totaal)
            contract.sr_preview_belastinggrondslag = result['grondslag_belasting_per_periode']
            contract.sr_preview_belastbaar_jaar = result['belastbaar_jaar']
            contract.sr_preview_lb_periode = result['lb_per_periode']
            contract.sr_preview_aov_periode = result['aov_per_periode']
            contract.sr_preview_netto = calc.round_money(
                bruto_totaal
                - result['lb_per_periode']
                - result['aov_per_periode']
                - inhoudingen
                - aftrek_bv
            )
            preview_netto_dec = Decimal(str(contract.sr_preview_netto or 0.0))
            contract.sr_preview_netto_jaar = calc.round_money(preview_netto_dec * Decimal(str(periodes)))
            contract.sr_preview_fn26_correctie = 0.0

            if contract.sr_salary_type == 'fn':
                scale = Decimal('26') / Decimal('12')
                monthly_wage = Decimal(str(wage_per_period)) * scale
                monthly_belastbaar_toelagen = Decimal(str(belastbaar_toelagen)) * scale
                monthly_vrijgesteld_toelagen = Decimal(str(vrijgesteld_toelagen)) * scale
                monthly_inhoudingen = Decimal(str(inhoudingen)) * scale
                monthly_aftrek_bv = Decimal(str(aftrek_bv)) * scale
                monthly_kb_belastbaar = Decimal(str(kb_belastbaar)) * scale
                monthly_kb_vrijgesteld = Decimal(str(kb_vrijgesteld)) * scale
                monthly_vgb_belastbaar = Decimal(str(vgb_belastbaar)) * scale
                monthly_heffingskorting = Decimal('0')

                monthly_bruto_belastbaar = (
                    monthly_wage
                    + monthly_belastbaar_toelagen
                    + monthly_kb_belastbaar
                    + monthly_vgb_belastbaar
                )
                monthly_bruto_totaal = (
                    monthly_wage
                    + monthly_belastbaar_toelagen
                    + monthly_kb_belastbaar
                    + monthly_kb_vrijgesteld
                    + monthly_vrijgesteld_toelagen
                )
                monthly_result = calc.calculate_lb(
                    float(monthly_bruto_belastbaar),
                    12,
                    params,
                    aftrek_bv_per_periode=float(monthly_aftrek_bv),
                    heffingskorting_per_periode=float(monthly_heffingskorting),
                )
                monthly_net = calc.round_money(
                    monthly_bruto_totaal
                    - Decimal(str(monthly_result['lb_per_periode']))
                    - Decimal(str(monthly_result['aov_per_periode']))
                    - monthly_inhoudingen
                    - monthly_aftrek_bv
                )
                annual_target = calc.round_money(Decimal(str(monthly_net)) * Decimal('12'))
                annual_projection = calc.round_money(preview_netto_dec * Decimal('26'))

                contract.sr_preview_netto_jaar = annual_target
                contract.sr_preview_fn26_correctie = calc.round_money(
                    Decimal(str(annual_target)) - Decimal(str(annual_projection))
                )

            contract.sr_preview_breakdown_html = calc.generate_breakdown_html(
                result=result,
                wage=wage_per_period,
                periodes=periodes,
                salary_type=contract.sr_salary_type,
                kb_split=kb_split,
                vrijgesteld=vrijgesteld_toelagen,
                inhoudingen=inhoudingen,
                belastbaar_toelagen=belastbaar_toelagen,
                bruto_totaal=bruto_totaal,
                netto_totaal=contract.sr_preview_netto,
                heffingskorting=heffingskorting,
            )

    @api.onchange('sr_aantal_kinderen')
    def _onchange_sr_aantal_kinderen(self):
        if self.sr_aantal_kinderen is False:
            return
        if self.sr_aantal_kinderen < 0:
            return {
                'warning': {
                    'title': 'Ongeldige AKB invoer',
                    'message': 'Aantal kinderen kan niet negatief zijn.',
                }
            }
        if self.sr_aantal_kinderen > self.SR_AKB_MAX_CHILDREN:
            self.sr_aantal_kinderen = self.SR_AKB_MAX_CHILDREN
            return {
                'warning': {
                    'title': 'AKB fiscaal gemaximeerd',
                    'message': (
                        f'Het aantal kinderen is teruggebracht naar maximaal {self.SR_AKB_MAX_CHILDREN}. '
                        'De Surinaamse wetgeving begrenst de AKB-vrijstelling op '
                        f'maximaal {self.SR_AKB_MAX_CHILDREN} kinderen per maand.'
                    ),
                }
            }

    @api.onchange('wage', 'sr_contract_currency')
    def _onchange_wage(self):
        self.ensure_one()
        if self.wage is not False and self.wage < 0:
            self.wage = 0.0
            return {
                'warning': {
                    'title': 'Ongeldig loonbedrag',
                    'message': 'Negatieve lonen zijn niet toegestaan. Het basisloon is teruggezet naar SRD 0,00.',
                }
            }

        currency = self.sr_contract_currency
        if not currency or currency.name in ('SRD', False, '') or not self.wage:
            return False

        rate = self._sr_get_current_exchange_rate()
        wage_srd = self._sr_get_wage_in_srd(exchange_rate=rate)
        warning_title = 'Controleer basisloon in vreemde valuta'
        if self.wage >= self.SR_FOREIGN_WAGE_WARNING_THRESHOLD:
            warning_message = (
                f'Dit contract gebruikt {currency.name}. Tegen de actuele 2026 payrollkoers van {rate:,.4f} '
                f'wordt {self.wage:,.2f} {currency.name} omgerekend naar {calc.format_srd(wage_srd)}. '
                'Controleer of het ingevoerde bedrag niet al in SRD is opgegeven. '
                'De definitieve loonstrook bevriest deze koers later in sr_exchange_rate.'
            )
        else:
            warning_message = (
                f'Dit contract gebruikt {currency.name}. Tegen de actuele 2026 payrollkoers van {rate:,.4f} '
                f'wordt het basisloon voorlopig omgerekend naar {calc.format_srd(wage_srd)}. '
                'De definitieve loonstrook bevriest deze koers later in sr_exchange_rate.'
            )
        return {
            'warning': {
                'title': warning_title,
                'message': warning_message,
            }
        }

    def _onchange_wage_non_negative(self):
        return self._onchange_wage()

    @api.constrains('wage')
    def _check_non_negative_wage(self):
        for contract in self:
            if contract.wage < 0:
                raise ValidationError('Negatieve lonen zijn niet toegestaan op Surinaamse contracten.')

    @api.constrains('sr_aantal_kinderen')
    def _check_sr_aantal_kinderen_range(self):
        for contract in self:
            if contract.sr_aantal_kinderen < 0:
                raise ValidationError('Aantal kinderen kan niet negatief zijn.')
            if contract.sr_aantal_kinderen > self.SR_AKB_MAX_CHILDREN:
                raise ValidationError(
                    f'Maximaal {self.SR_AKB_MAX_CHILDREN} kinderen zijn toegestaan voor AKB.'
                )

    @api.depends()
    def _compute_sr_tax_bracket_html(self):
        """Genereert de Art. 14 tarieftabel HTML uit actuele parameters."""
        today = Date.today()
        params = calc.fetch_params_from_rule_parameter(self.env, today)
        html = calc.generate_tax_bracket_html(params)
        for contract in self:
            contract.sr_tax_bracket_html = html

    @api.onchange('sr_contract_currency')
    def _onchange_sr_contract_currency(self):
        for contract in self:
            currency = contract.sr_contract_currency
            if currency and currency.name not in ('SRD', False, ''):
                return {
                    'warning': {
                        'title': 'Vreemde Valuta Geselecteerd',
                        'message': (
                            f'Het basisloon wordt nu ingevoerd in {currency.name} ({currency.symbol or currency.name}). '
                            f'Controleer dat het loonbedrag in de nieuwe valuta is ingevoerd. '
                            f'De contractpreview gebruikt de actuele koers uit SR Payroll Instellingen, '
                            f'maar de loonstrook bevriest later een aparte sr_exchange_rate snapshot.'
                        ),
                    }
                }

    @api.depends('wage', 'sr_salary_type', 'sr_contract_currency',
                 'company_id.sr_exchange_rate_usd', 'company_id.sr_exchange_rate_eur')
    def _compute_sr_wage_per_period(self):
        for contract in self:
            contract.sr_wage_per_period_srd = contract._sr_get_wage_per_period_srd()

    @api.depends('wage', 'sr_salary_type', 'sr_contract_currency')
    def _compute_sr_hourly_wage(self):
        """Bruto uurloon in SRD: maandloon ÷ 173,33 (geldt voor zowel maandloon als FN)."""
        for contract in self:
            if not contract.wage:
                contract.sr_hourly_wage = 0.0
                continue
            rate = contract._sr_get_current_exchange_rate()
            wage_srd = Decimal(str(contract._sr_get_wage_in_srd(exchange_rate=rate)))
            hourly = wage_srd / Decimal('173.333333')
            contract.sr_hourly_wage = float(
                hourly.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            )

    @api.depends(
        'wage', 'sr_contract_currency',
        'company_id.sr_exchange_rate_usd', 'company_id.sr_exchange_rate_eur',
    )
    def _compute_sr_currency_pair_display(self):
        for contract in self:
            rate = contract._sr_get_current_exchange_rate()
            contract.sr_current_exchange_rate_display = rate
            wage_srd = contract._sr_get_wage_in_srd(exchange_rate=rate)
            contract.sr_wage_srd = wage_srd

    def _sr_get_wage_in_srd(self, exchange_rate=None, round_result=True):
        """Zet het contractloon (maandloon) om naar SRD."""
        self.ensure_one()
        wage = Decimal(str(self.wage or 0.0))
        if not wage:
            return 0.0
        rate = Decimal(str(exchange_rate if exchange_rate is not None else self._sr_get_current_exchange_rate()))
        wage_srd = wage * rate
        quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT
        return float(wage_srd.quantize(quant, rounding=ROUND_HALF_UP))

    def _sr_get_wage_per_period_srd(self, exchange_rate=None, round_result=True):
        """Geeft het loon per uitbetalingsperiode terug in SRD.

        Het basisloon wordt altijd als maandloon ingevoerd.
        Voor FN-contracten wordt automatisch omgerekend: maandloon × 12 ÷ 26.
        Voor maandloon: ongewijzigd.
        """
        self.ensure_one()
        wage_srd = Decimal(str(
            self._sr_get_wage_in_srd(exchange_rate=exchange_rate, round_result=False)
        ))
        if self.sr_salary_type == 'fn':
            wage_srd = wage_srd * Decimal('12') / Decimal('26')
        quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT
        return float(wage_srd.quantize(quant, rounding=ROUND_HALF_UP))

    def _sr_get_current_exchange_rate(self):
        """Leest de actuele wisselkoers voor de contractvaluta (voor preview/display)."""
        self.ensure_one()
        currency = self.sr_contract_currency
        if not currency or currency.name == 'SRD':
            return 1.0
        company = self.company_id or self.env.company
        if currency.name == 'USD':
            return company.sr_exchange_rate_usd or 36.5
        if currency.name == 'EUR':
            return company.sr_exchange_rate_eur or 39.0
        return 1.0

    def _sr_is_payroll_contract(self):
        self.ensure_one()
        return bool(self.structure_type_id and self.structure_type_id in self._sr_get_structure_types())

    def _sr_guard_salary_type_change_with_existing_slips(self, new_salary_type):
        if self.env.context.get('sr_allow_salary_type_change_with_slips'):
            return
        changing_contracts = self.filtered(
            lambda contract: contract._sr_is_payroll_contract()
            and contract.sr_salary_type
            and contract.sr_salary_type != new_salary_type
        )
        if not changing_contracts:
            return

        blocking_slip = self.env['hr.payslip'].search([
            ('contract_id', 'in', changing_contracts.ids),
            ('state', 'not in', ('draft', 'cancel')),
        ], limit=1)
        if blocking_slip:
            raise ValidationError(
                'Je kunt het SR betaaltype niet wijzigen zolang er al berekende of bevestigde '
                'loonstroken op dit contract bestaan. Annuleer of corrigeer eerst de bestaande '
                'loonstroken en probeer daarna opnieuw.'
            )

    def write(self, vals):
        if 'sr_salary_type' in vals:
            self._sr_guard_salary_type_change_with_existing_slips(vals['sr_salary_type'])
        result = super().write(vals)
        if 'sr_has_overtime_right' in vals:
            work_entries = self.env['hr.work.entry'].search([
                ('contract_id', 'in', self.ids),
                ('sr_manual_override', '=', False),
            ])
            if work_entries:
                work_entries._sr_classify_overtime()
        return result

    @api.constrains('wage', 'state', 'structure_type_id')
    def _check_sr_positive_wage(self):
        for contract in self:
            if not contract._sr_is_payroll_contract():
                continue
            if contract.state not in ('open', 'pending'):
                continue
            if (contract.wage or 0.0) <= 0.0:
                raise ValidationError(
                    'SR payroll-contracten met een actieve status vereisen een positief basisloon. '
                    'Zonder loon kunnen uurloon, overwerk en fiscale inhoudingen niet veilig worden berekend.'
                )

    _SR_SUPPORTED_CURRENCIES = frozenset({'SRD', 'USD', 'EUR'})

    @api.constrains('sr_contract_currency')
    def _check_sr_contract_currency(self):
        for contract in self:
            currency = contract.sr_contract_currency
            if currency and currency.name not in self._SR_SUPPORTED_CURRENCIES:
                raise ValidationError(
                    f'Contractvaluta "{currency.name}" wordt niet ondersteund door de SR payroll-engine. '
                    'Kies SRD, USD of EUR.'
                )

    @api.depends(
        'sr_vaste_regels.type_id',
        'sr_vaste_regels.name',
        'sr_vaste_regels.amount',
        'sr_vaste_regels.amount_type',
        'sr_vaste_regels.percentage',
        'sr_vaste_regels.percentage_base',
        'sr_vaste_regels.line_currency_id',
        'sr_contract_currency',
        'company_id.sr_exchange_rate_usd',
        'company_id.sr_exchange_rate_eur',
    )
    def _compute_sr_named_contract_lines(self):
        for contract in self:
            rate = contract._sr_get_current_exchange_rate()
            for field_name, definition in self.SR_CONTRACT_LINE_FIELD_MAP.items():
                total = sum(
                    contract._sr_resolve_line_amount(line, exchange_rate=rate)
                    for line in contract._sr_get_named_rule_lines(definition)
                )
                contract[field_name] = calc.round_money(total)

    # ── Helper methoden voor berekeningen ──────────────────────────────

    def _sr_get_line_type_from_definition(self, definition):
        line_type = self.env.ref(definition['xmlid'], raise_if_not_found=False)
        if line_type:
            return line_type
        return self.env['hr.contract.sr.line.type'].search([
            ('code', '=', definition['code']),
        ], limit=1)

    def _sr_get_named_rule_lines(self, definition):
        self.ensure_one()
        fallback_names = {name.casefold() for name in definition.get('fallback_names', ())}
        return self.sr_vaste_regels.filtered(
            lambda line: (line.type_id and line.type_id.code == definition['code'])
            or (
                not line.type_id
                and (line.name or '').strip().casefold() in fallback_names
            )
        )

    def _sr_set_named_rule_amount(self, field_name, amount):
        self.ensure_one()
        definition = self.SR_CONTRACT_LINE_FIELD_MAP[field_name]
        lines = self._sr_get_named_rule_lines(definition)
        normalized_amount = calc.round_money(amount or 0.0)
        current_total = calc.round_money(sum(self._sr_resolve_line_amount(line) for line in lines)) if lines else 0.0
        keeper = lines[:1]
        line_type = self._sr_get_line_type_from_definition(definition)
        keeper_matches_definition = bool(keeper) and (
            keeper.name == definition['name']
            and keeper.amount_type == 'fixed'
            and keeper.sr_categorie == definition['category']
            and (
                (line_type and keeper.type_id == line_type)
                or (not line_type and not keeper.type_id)
            )
        )
        if (
            float_compare(current_total, normalized_amount, precision_digits=2) == 0
            and len(lines) == 1
            and keeper_matches_definition
        ):
            return

        if not normalized_amount:
            if lines:
                lines.unlink()
            return

        extra_lines = lines - keeper
        if extra_lines:
            extra_lines.unlink()

        line_vals = {
            'name': definition['name'],
            'sr_categorie': definition['category'],
            'amount_type': 'fixed',
            'amount': normalized_amount,
        }
        if line_type:
            line_vals['type_id'] = line_type.id

        if keeper:
            keeper.write(line_vals)
            return

        line_vals['contract_id'] = self.id
        self.env['hr.contract.sr.line'].create(line_vals)

    def _inverse_sr_kinderbijslag_bedrag(self):
        for contract in self:
            contract._sr_set_named_rule_amount('sr_kinderbijslag_bedrag', contract.sr_kinderbijslag_bedrag)

    def _inverse_sr_vervoer_toelage(self):
        for contract in self:
            contract._sr_set_named_rule_amount('sr_vervoer_toelage', contract.sr_vervoer_toelage)

    def _inverse_sr_representatie_toelage(self):
        for contract in self:
            contract._sr_set_named_rule_amount('sr_representatie_toelage', contract.sr_representatie_toelage)

    def _inverse_sr_vrije_geneeskundige_behandeling(self):
        for contract in self:
            contract._sr_set_named_rule_amount(
                'sr_vrije_geneeskundige_behandeling',
                contract.sr_vrije_geneeskundige_behandeling,
            )

    def _sr_get_heffingskorting_per_periode(self, heffingskorting_maand=None, round_result=True):
        """Geeft de netto heffingskorting terug voor maandloon of FN."""
        self.ensure_one()
        if heffingskorting_maand is None:
            heffingskorting_maand = calc.get_sr_parameter_value(
                self.env, 'SR_HEFFINGSKORTING', Date.today(),
                default=calc.get_config_parameter_default('SR_HEFFINGSKORTING'),
                raise_if_not_found=False,
            )
        if not heffingskorting_maand:
            return 0.0

        periodes = 26 if self.sr_salary_type == 'fn' else 12
        heffingskorting_per_periode = Decimal(str(heffingskorting_maand))
        if periodes != 12:
            heffingskorting_per_periode = heffingskorting_per_periode * Decimal('12') / Decimal('26')
        quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT
        return float(heffingskorting_per_periode.quantize(quant, rounding=ROUND_HALF_UP))

    def _sr_resolve_line_amount(self, line, exchange_rate=None, round_result=True):
        """
        Berekent het effectieve bedrag van een vaste loon regel in SRD.

        Handelt zowel vaste bedragen als percentages af.
        Bij percentage: berekend over het loon per periode (FN: maandloon × 12/26) in SRD.
        Bij vast bedrag in vreemde valuta (USD/EUR): converteert naar SRD via exchange_rate.
        Vaste bedragen zijn loonperiode-bedragen zoals ingevoerd. Alleen het basisloon
        en maandnormen zoals kinderbijslag-vrijstelling worden voor FN omgerekend.
        """
        quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT

        if line.amount_type == 'percentage' and line.percentage:
            wage_srd = self._sr_get_wage_per_period_srd(exchange_rate=exchange_rate, round_result=False)
            if line.percentage_base == 'bruto_belastbaar':
                base = wage_srd + sum(
                    self._sr_resolve_line_amount(l, exchange_rate=exchange_rate, round_result=False)
                    for l in self.sr_vaste_regels
                    if l._sr_effective_category() == 'belastbaar'
                    and l.amount_type != 'percentage'
                    and l.id != line.id
                )
            else:
                base = wage_srd
            percentage_amount = Decimal(str(base)) * Decimal(str(line.percentage or 0.0)) / Decimal('100')
            return float(percentage_amount.quantize(quant, rounding=ROUND_HALF_UP))

        # Vast bedrag — converteer naar SRD als de lijn-valuta vreemd is
        amount = self._sr_resolve_fixed_line_amount_srd(line, exchange_rate=exchange_rate)
        return float(amount.quantize(quant, rounding=ROUND_HALF_UP))

    def _sr_resolve_fixed_line_amount_srd(self, line, exchange_rate=None):
        """Converteert een vast contractregelbedrag naar SRD zonder periode-prorata."""
        amount = Decimal(str(line.amount or 0.0))
        line_currency = line.line_currency_id
        if line_currency and line_currency.name not in ('SRD', False, ''):
            rate = Decimal(str(exchange_rate if exchange_rate is not None else self._sr_get_current_exchange_rate()))
            amount = amount * rate
        return amount

    def _sr_resolve_regels(self, categorie, exchange_rate=None, round_result=True):
        """
        Totale bedrag van vaste regels voor een bepaalde categorie.

        Handelt percentages automatisch af via _sr_resolve_line_amount.
        """
        total = sum((
            Decimal(str(self._sr_resolve_line_amount(r, exchange_rate=exchange_rate, round_result=False)))
            for r in self.sr_vaste_regels
            if r._sr_effective_category() == categorie
        ), Decimal('0'))
        quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT
        return float(total.quantize(quant, rounding=ROUND_HALF_UP))

    def _sr_resolve_other_vrijgestelde_regels(self, exchange_rate=None, round_result=True):
        """Totale vrijgestelde contractregels exclusief kinderbijslag (Art. 10h)."""
        total = sum((
            Decimal(str(self._sr_resolve_line_amount(r, exchange_rate=exchange_rate, round_result=False)))
            for r in self.sr_vaste_regels
            if r._sr_effective_category() == 'vrijgesteld' and not r._is_sr_kindbijslag_line()
        ), Decimal('0'))
        quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT
        return float(total.quantize(quant, rounding=ROUND_HALF_UP))

    def _sr_kinderbijslag_split(self, max_kind_maand=None, max_maand=None, exchange_rate=None, round_result=True):
        """
        Splitst kinderbijslag in belastbaar en vrijgesteld deel (Art. 10h).

        Wanneer max_kind_maand of max_maand None is, wordt de waarde
        automatisch opgehaald uit System Parameters met fallback naar
        hr.rule.parameter.

        :param max_kind_maand: Maximum vrijstelling per kind per maand (SRD)
        :param max_maand: Maximum vrijstelling per maand (SRD)
        :returns: dict met 'belastbaar' en 'vrijgesteld'
        """
        if max_kind_maand is None:
            max_kind_maand = calc.get_sr_parameter_value(
                self.env, 'SR_KINDBIJ_MAX_KIND_MAAND', Date.today(),
                default=calc.get_config_parameter_default('SR_KINDBIJ_MAX_KIND_MAAND'),
                raise_if_not_found=False,
            )
        if max_maand is None:
            max_maand = calc.get_sr_parameter_value(
                self.env, 'SR_KINDBIJ_MAX_MAAND', Date.today(),
                default=calc.get_config_parameter_default('SR_KINDBIJ_MAX_MAAND'),
                raise_if_not_found=False,
            )
        # Kinderbijslag regels via type KINDBIJ of genormaliseerde naam.
        # Invoer is het maandbedrag per kind. Voor FN wordt dit eerst naar
        # een FN-periode omgerekend en daarna vermenigvuldigd met het aantal kinderen.
        kb_lines = [
            r for r in self.sr_vaste_regels
            if r._is_sr_kindbijslag_line()
        ]
        eligible_children = min(self.sr_aantal_kinderen or 0, self.SR_AKB_MAX_CHILDREN)
        total_kb = Decimal('0')
        for line in kb_lines:
            if line.amount_type == 'percentage':
                line_amount = Decimal(str(
                    self._sr_resolve_line_amount(line, exchange_rate=exchange_rate, round_result=False)
                ))
            else:
                line_amount = self._sr_resolve_fixed_line_amount_srd(line, exchange_rate=exchange_rate)
                if self.sr_salary_type == 'fn':
                    line_amount = line_amount * Decimal('12') / Decimal('26')
            total_kb += line_amount * Decimal(str(eligible_children))

        if total_kb <= 0:
            return {'belastbaar': 0.0, 'vrijgesteld': 0.0}

        periodes = 26 if self.sr_salary_type == 'fn' else 12
        exempt_maand = min(eligible_children * max_kind_maand, max_maand)
        exempt_per_periode = Decimal(str(exempt_maand or 0.0))
        if periodes != 12:
            exempt_per_periode = exempt_per_periode * Decimal('12') / Decimal('26')

        kb_exempt = min(total_kb, exempt_per_periode)
        kb_belastbaar = max(Decimal('0'), total_kb - exempt_per_periode)

        quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT

        return {
            'belastbaar': float(kb_belastbaar.quantize(quant, rounding=ROUND_HALF_UP)),
            'vrijgesteld': float(kb_exempt.quantize(quant, rounding=ROUND_HALF_UP)),
        }

    def _sr_vgb_fiscaal_belastbaar(self, exchange_rate=None, round_result=True):
        """
        Berekent het fiscaal belastbaar deel van Vrije Geneeskundige Behandeling (Art. 9 WLB).

        VGB is een voordeel in natura (bijv. werkgeversbijdrage medische verzekering).
        Het verhoogt de Art. 14 grondslag voor LB en AOV maar wordt NIET als cash
        uitbetaald. Het belastbaar deel is gemaximeerd op SR_VGB_MAX_JAAR/jaar.

        Prioriteit:
        1. Expliciete GENEESK-contractregel (categorie='fiscaal_grondslag') — gebruikt die waarde, gecapped.
        2. Geen contractregel — geen VGB-grondslag.

        :returns: Belastbaar VGB per periode (gecapped op SR_VGB_MAX_JAAR/periodes)
        """
        self.ensure_one()
        vgb_max_jaar = calc.get_sr_parameter_value(
            self.env, 'SR_VGB_MAX_JAAR', Date.today(),
            default=200.0, raise_if_not_found=False,
        ) or 200.0
        periodes = 26 if self.sr_salary_type == 'fn' else 12
        vgb_max_periode = Decimal(str(vgb_max_jaar or 0.0)) / Decimal(str(periodes or 1))

        vgb_contract = self._sr_resolve_regels('fiscaal_grondslag', exchange_rate=exchange_rate, round_result=False)
        if vgb_contract:
            quant = calc.MONEY_QUANT if round_result else SR_INTERNAL_MONEY_QUANT
            capped_amount = min(Decimal(str(vgb_contract)), vgb_max_periode)
            return float(capped_amount.quantize(quant, rounding=ROUND_HALF_UP))

        return 0.0

    def generate_work_entries(self, date_start, date_stop, force=False):
        """
        Override: Allow admin/dev users to regenerate validated work entries.
        
        :param date_start: Work entry period start
        :param date_stop: Work entry period stop
        :param force: Force deletion of existing entries (for admins)
        :return: Created work entry recordset
        """
        # Check if user is System Admin
        is_admin = self.env.user.has_group('base.group_system')
        
        if is_admin and force:
            # Allow admin to delete validated entries and regenerate
            existing = self.env['hr.work.entry'].search([
                ('contract_id', 'in', self.ids),
                ('date_start', '<=', date_stop),
                ('date_stop', '>=', date_start),
            ])
            if existing:
                # Delete with admin context to bypass validation restrictions
                existing.sudo().unlink()
        
        # Call parent implementation
        return super().generate_work_entries(date_start, date_stop, force=force)
