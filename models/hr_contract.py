# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as Date
from decimal import Decimal, ROUND_HALF_UP

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from . import sr_artikel14_calculator as calc


class HrContract(models.Model):
    _inherit = 'hr.contract'

    SR_AKB_MAX_CHILDREN = 4
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
            'category': 'belastbaar',
            'fallback_names': ('vrije geneeskundige behandeling', 'geneeskundige behandeling'),
        },
    }

    sr_salary_type = fields.Selection(
        selection=[
            ('monthly', '1 lb sal ovw (Maandloon)'),
            ('fn', 'FN (Fortnight)'),
        ],
        string='Surinaams Loontype',
        default='monthly',
        store=True,
        help='Selecteer het betaaltype: maandloon (12 periodes) of fortnight (26 periodes per jaar).',
    )

    sr_aantal_kinderen = fields.Integer(
        string='Aantal Kinderen',
        default=0,
        store=True,
        help=(
            'Aantal kinderen waarvoor kinderbijslag wordt betaald.\n'
            'Gebruikt voor de Art. 10h splitsing: max SRD 250/kind/maand, '
            'max SRD 1.000/maand is belastingvrij. Het meerdere is belastbaar.'
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
        default=lambda self: (
            self.env['res.currency'].search([('name', '=', 'SRD')], limit=1)
            or self.env.company.currency_id
        ),
        store=True,
        copy=True,
        help=(
            'Valuta waarin het basisloon is uitgedrukt. '
            'Kies SRD (standaard), USD of EUR. '
            'Toelagen en inhoudingen blijven altijd in SRD. '
            'Bij loonverwerking wordt het loon omgerekend naar SRD '
            'via de actuele wisselkoers uit SR Payroll Instellingen. '
            'De gehanteerde koers wordt per loonstrook bevroren opgeslagen.'
        ),
    )

    sr_hourly_wage = fields.Float(
        string='Uurloon (SRD)',
        digits=(16, 4),
        compute='_compute_sr_hourly_wage',
        store=True,
        precompute=True,
        help='Bruto uurloon in SRD: basisloon (omgerekend) ÷ 173,33 (maandloon) of ÷ 80 (fortnight).',
    )
    sr_kinderbijslag_bedrag = fields.Monetary(
        string='Kinderbijslag per Periode',
        currency_field='currency_id',
        compute='_compute_sr_named_contract_lines',
        inverse='_inverse_sr_kinderbijslag_bedrag',
        store=True,
        precompute=True,
        help='Snelle contractinvoer voor de vaste kinderbijslagregel. Schrijft door naar de fiscale contractregels.',
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

    @api.depends(
        'sr_kinderbijslag_bedrag',
        'sr_vervoer_toelage',
        'sr_representatie_toelage',
        'sr_vrije_geneeskundige_behandeling',
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
        config_params = self.env['ir.config_parameter'].sudo()

        for contract in self:
            periodes = 26 if contract.sr_salary_type == 'fn' else 12
            heffingskorting = contract._sr_get_heffingskorting_per_periode()

            belastbaar_toelagen = contract._sr_resolve_regels('belastbaar')
            vrijgesteld_toelagen = contract._sr_resolve_other_vrijgestelde_regels()
            inhoudingen = contract._sr_resolve_regels('inhouding')
            aftrek_bv = contract._sr_resolve_regels('aftrek_belastingvrij')

            # Kinderbijslag splitsing (Art. 10h)
            kb_split = contract._sr_kinderbijslag_split()
            kb_belastbaar = kb_split['belastbaar']
            kb_vrijgesteld = kb_split['vrijgesteld']

            # Basisloon omrekenen naar SRD voor fiscale berekening
            rate = contract._sr_get_current_exchange_rate(config_params)
            wage_srd = float(Decimal(str(contract.wage or 0.0)) * Decimal(str(rate)))

            # Bruto belastbaar = salaris (SRD) + belastbare toelagen + KB belastbaar
            bruto_belastbaar = wage_srd + belastbaar_toelagen + kb_belastbaar
            result = calc.calculate_lb(
                bruto_belastbaar, periodes, params,
                aftrek_bv_per_periode=aftrek_bv,
            )

            bruto_totaal = wage_srd + belastbaar_toelagen + kb_belastbaar + kb_vrijgesteld + vrijgesteld_toelagen
            contract.sr_preview_bruto = bruto_totaal
            contract.sr_preview_belastbaar_jaar = result['belastbaar_jaar']
            contract.sr_preview_lb_periode = result['lb_per_periode']
            contract.sr_preview_aov_periode = result['aov_per_periode']
            contract.sr_preview_netto = (
                bruto_totaal
                + heffingskorting
                - result['lb_per_periode']
                - result['aov_per_periode']
                - inhoudingen
                - aftrek_bv
            )
            contract.sr_preview_breakdown_html = calc.generate_breakdown_html(
                result=result,
                wage=wage_srd,
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
            self.sr_aantal_kinderen = 0
            return {
                'warning': {
                    'title': 'Ongeldige AKB invoer',
                    'message': 'Aantal kinderen kan niet negatief zijn. De waarde is teruggezet naar 0.',
                }
            }
        if self.sr_aantal_kinderen > self.SR_AKB_MAX_CHILDREN:
            self.sr_aantal_kinderen = self.SR_AKB_MAX_CHILDREN
            return {
                'warning': {
                    'title': 'AKB limiet bereikt',
                    'message': 'Voor de 2026 release accepteert de module maximaal 4 kinderen voor AKB.',
                }
            }

    @api.onchange('wage')
    def _onchange_wage_non_negative(self):
        if self.wage is not False and self.wage < 0:
            self.wage = 0.0
            return {
                'warning': {
                    'title': 'Ongeldig loonbedrag',
                    'message': 'Negatieve lonen zijn niet toegestaan. Het basisloon is teruggezet naar SRD 0,00.',
                }
            }

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
                    'Aantal kinderen voor AKB mag voor de 2026 release maximaal 4 zijn.'
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
                            f'Controleer dat het loodbedrag in de nieuwe valuta is ingevoerd. '
                            f'De wisselkoers uit SR Payroll Instellingen (Valuta & Wisselkoers) '
                            f'wordt bij elke loonrun gebruikt voor omrekening naar SRD.'
                        ),
                    }
                }

    @api.depends('wage', 'sr_salary_type', 'sr_contract_currency')
    def _compute_sr_hourly_wage(self):
        """Berekent het bruto uurloon in SRD: basisloon (omgerekend) ÷ 173,33 (maandloon) of ÷ 80 (fortnight)."""
        params = self.env['ir.config_parameter'].sudo()
        for contract in self:
            wage = contract.wage or 0.0
            if not wage:
                contract.sr_hourly_wage = 0.0
                continue
            # Wisselkoers ophalen voor vreemde valuta
            rate = contract._sr_get_current_exchange_rate(params)
            wage_srd = Decimal(str(wage)) * Decimal(str(rate))
            divisor = Decimal('80.0') if contract.sr_salary_type == 'fn' else Decimal('173.333333')
            hourly = wage_srd / divisor
            contract.sr_hourly_wage = float(
                hourly.quantize(Decimal('0.0001'), rounding=ROUND_HALF_UP)
            )

    def _sr_get_current_exchange_rate(self, params=None):
        """Leest de actuele wisselkoers voor de contractvaluta (voor preview/display)."""
        self.ensure_one()
        currency = self.sr_contract_currency
        if not currency or currency.name == 'SRD':
            return 1.0
        if params is None:
            params = self.env['ir.config_parameter'].sudo()
        if currency.name == 'USD':
            try:
                return float(params.get_param('sr_payroll.exchange_rate_usd', default='36.5000'))
            except (TypeError, ValueError):
                return 36.5
        if currency.name == 'EUR':
            try:
                return float(params.get_param('sr_payroll.exchange_rate_eur', default='39.0000'))
            except (TypeError, ValueError):
                return 39.0
        return 1.0

    def _sr_is_payroll_contract(self):
        self.ensure_one()
        sr_struct = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False)
        return bool(sr_struct and self.structure_type_id == sr_struct.type_id)

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

    @api.depends(
        'sr_vaste_regels.type_id',
        'sr_vaste_regels.name',
        'sr_vaste_regels.amount',
        'sr_vaste_regels.amount_type',
        'sr_vaste_regels.percentage',
        'sr_vaste_regels.percentage_base',
    )
    def _compute_sr_named_contract_lines(self):
        for contract in self:
            for field_name, definition in self.SR_CONTRACT_LINE_FIELD_MAP.items():
                total = sum(
                    contract._sr_resolve_line_amount(line)
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
        if lines:
            lines.unlink()

        if not amount:
            return

        line_type = self._sr_get_line_type_from_definition(definition)
        line_vals = {
            'contract_id': self.id,
            'name': definition['name'],
            'sr_categorie': definition['category'],
            'amount_type': 'fixed',
            'amount': amount,
        }
        if line_type:
            line_vals['type_id'] = line_type.id
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

    def _sr_get_heffingskorting_per_periode(self, heffingskorting_maand=None):
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
        if periodes == 12:
            return calc.round_money(heffingskorting_maand)
        return calc.round_money(heffingskorting_maand * 12.0 / 26.0)

    def _sr_resolve_line_amount(self, line):
        """
        Berekent het effectieve bedrag van een vaste loon regel.

        Handelt zowel vaste bedragen als percentages af.
        Bij percentage: berekend over basisloon of bruto belastbaar.
        """
        if line.amount_type == 'percentage' and line.percentage:
            if line.percentage_base == 'bruto_belastbaar':
                base = (self.wage or 0.0) + sum(
                    l.amount or 0.0 for l in self.sr_vaste_regels
                    if l._sr_effective_category() == 'belastbaar'
                    and l.amount_type != 'percentage'
                    and l.id != line.id
                )
            else:
                base = self.wage or 0.0
            return base * (line.percentage / 100.0)
        return line.amount or 0.0

    def _sr_resolve_regels(self, categorie):
        """
        Totale bedrag van vaste regels voor een bepaalde categorie.

        Handelt percentages automatisch af via _sr_resolve_line_amount.
        """
        return sum(
            self._sr_resolve_line_amount(r) for r in self.sr_vaste_regels
            if r._sr_effective_category() == categorie
        )

    def _sr_resolve_other_vrijgestelde_regels(self):
        """Totale vrijgestelde contractregels exclusief kinderbijslag (Art. 10h)."""
        return sum(
            self._sr_resolve_line_amount(r) for r in self.sr_vaste_regels
            if r._sr_effective_category() == 'vrijgesteld' and not r._is_sr_kindbijslag_line()
        )

    def _sr_kinderbijslag_split(self, max_kind_maand=None, max_maand=None):
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
        kb_lines = [
            r for r in self.sr_vaste_regels
            if r._is_sr_kindbijslag_line()
        ]
        total_kb = sum(self._sr_resolve_line_amount(r) for r in kb_lines) if kb_lines else 0.0

        if total_kb <= 0:
            return {'belastbaar': 0.0, 'vrijgesteld': 0.0}

        if not self.sr_aantal_kinderen or self.sr_aantal_kinderen <= 0:
            # Geen kinderen geregistreerd: volledige KB is belastbaar
            return {'belastbaar': total_kb, 'vrijgesteld': 0.0}

        periodes = 26 if self.sr_salary_type == 'fn' else 12
        exempt_maand = min(self.sr_aantal_kinderen * max_kind_maand, max_maand)
        exempt_per_periode = exempt_maand if periodes == 12 else exempt_maand * 12.0 / 26.0

        kb_exempt = min(total_kb, exempt_per_periode)
        kb_belastbaar = max(0.0, total_kb - exempt_per_periode)

        return {'belastbaar': kb_belastbaar, 'vrijgesteld': kb_exempt}

    def generate_work_entries(self, date_start, date_stop, force=False):
        """
        Override: Allow admin/dev users to regenerate validated work entries.
        
        Base Odoo restricts regenerating validated work entries. This override
        allows System Admins (in the 'base.group_system' group) to bypass this
        restriction for testing and corrective work.
        
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
