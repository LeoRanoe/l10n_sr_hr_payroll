# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date as dt_date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
import psycopg2
import threading

from odoo import api, fields, models
from odoo.exceptions import UserError

from . import sr_artikel14_calculator as calc

# Thread-local cache for Art. 14 calculations per compute cycle.
# Keyed on (payslip_id, gross, aftrek_bv) and isolated per request thread.
_sr_calc_thread_local = threading.local()
_SR_MONEY_QUANT = Decimal('0.01')
_SR_INTERNAL_MONEY_QUANT = Decimal('0.000001')
_SR_HOURLY_RATE_QUANT = Decimal('0.000001')
_SR_PAYSLIP_LAYOUT_DEFAULT = 'employee_simple'
_SR_PAYSLIP_LAYOUT_CONFIG_KEY = 'sr_payroll.sr_default_payslip_layout'
_SR_PAYSLIP_LAYOUT_LEGACY_CONFIG_KEY = 'sr_payroll.default_payslip_layout'
_SR_DISPLAY_MODE_CONFIG_KEY = 'sr_payroll.netto_display_mode'
_SR_DISPLAY_MODE_DEFAULT = 'srd'
_SR_PAYSLIP_LAYOUTS = [
    ('employee_simple', 'Werknemer overzicht'),
    ('compact', 'Compact Netto-overzicht'),
    ('artikel14_detail', 'Artikel 14 Detail'),
    ('odoo_standard', 'Alternatieve Odoo-opmaak'),
]
_SR_PAYROLL_STRUCTURE_XMLIDS = (
    'l10n_sr_hr_payroll.sr_payroll_structure',
    'l10n_sr_hr_payroll.sr_payroll_structure_hourly',
)

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
    {'indicator': '202626', 'label': '2026FN26', 'date_from': dt_date(2026, 12, 17), 'date_to': dt_date(2026, 12, 31)},
)


def _get_sr_calc_cache():
    cache = getattr(_sr_calc_thread_local, 'sr_calc_cache', None)
    if cache is None:
        cache = {}
        _sr_calc_thread_local.sr_calc_cache = cache
    return cache


def _clear_sr_calc_cache():
    _get_sr_calc_cache().clear()


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    sr_is_sr_struct = fields.Boolean(
        compute='_compute_sr_is_sr_struct',
        string='SR Structuur',
        store=True,
        compute_sudo=True,
    )
    sr_payslip_layout = fields.Selection(
        selection=_SR_PAYSLIP_LAYOUTS,
        string='Loonstrook Layout',
        default=lambda self: self._default_sr_payslip_layout(),
        copy=False,
        help='Kies welke loonstrooklayout gebruikt wordt voor deze SR-loonstrook.',
    )
    sr_regular_hours = fields.Float(
        string='Normale Uren',
        digits=(16, 2),
        copy=False,
        readonly=True,
    )
    sr_overtime_hours_150 = fields.Float(
        string='Overwerk 150% Uren',
        digits=(16, 2),
        copy=False,
        readonly=True,
    )
    sr_overtime_hours_200 = fields.Float(
        string='Overwerk 200% Uren',
        digits=(16, 2),
        copy=False,
        readonly=True,
    )
    sr_unpaid_extra_hours = fields.Float(
        string='Extra Uren Niet Uitbetaald',
        digits=(16, 2),
        copy=False,
        readonly=True,
    )
    sr_total_worked_hours = fields.Float(
        string='Totaal Gewerkte Uren',
        digits=(16, 2),
        copy=False,
        readonly=True,
    )
    sr_total_worked_days = fields.Float(
        string='Totaal Gewerkte Dagen',
        digits=(16, 2),
        copy=False,
        readonly=True,
    )
    sr_bruto_totaal_display = fields.Monetary(
        string='Bruto Totaal',
        currency_field='currency_id',
        compute='_compute_sr_summary_display',
        compute_sudo=True,
        store=True,
    )
    sr_heffingskorting_display = fields.Monetary(
        string='Heffingskorting',
        currency_field='currency_id',
        compute='_compute_sr_summary_display',
        compute_sudo=True,
        store=True,
    )
    sr_lb_totaal_display = fields.Monetary(
        string='Totale LB',
        currency_field='currency_id',
        compute='_compute_sr_summary_display',
        compute_sudo=True,
        store=True,
    )
    sr_aov_totaal_display = fields.Monetary(
        string='Totale AOV',
        currency_field='currency_id',
        compute='_compute_sr_summary_display',
        compute_sudo=True,
        store=True,
    )
    sr_inhoudingen_totaal_display = fields.Monetary(
        string='Totale Inhoudingen',
        currency_field='currency_id',
        compute='_compute_sr_summary_display',
        compute_sudo=True,
        store=True,
    )
    sr_netto_totaal_display = fields.Monetary(
        string='Netto Totaal',
        currency_field='currency_id',
        compute='_compute_sr_summary_display',
        compute_sudo=True,
        store=True,
    )

    # ── Multi-Currency: bevroren snapshot (kopie bij compute_sheet) ───────
    sr_frozen_contract_currency_id = fields.Many2one(
        'res.currency',
        string='Contract Valuta (Bevroren)',
        readonly=True,
        copy=False,
        help='Contractvaluta bevroren op het moment van loonberekening.',
    )
    sr_frozen_exchange_rate = fields.Float(
        string='Technische Wisselkoerssnapshot',
        digits=(16, 6),
        store=True,
        readonly=True,
        copy=False,
        help='Technisch compatibiliteitsveld voor oudere data. Gebruik sr_exchange_rate voor alle actuele payroll-logica.',
    )
    sr_exchange_rate = fields.Float(
        related='sr_frozen_exchange_rate',
        string='Wisselkoers bij Berekening',
        digits=(16, 6),
        store=True,
        readonly=True,
        copy=False,
        help='Persistente alias voor de bevroren wisselkoers op deze loonstrook.',
    )
    sr_frozen_netto_display_mode = fields.Selection(
        selection=[
            ('srd', 'Altijd in SRD'),
            ('contract_currency', 'Toon ook in Contractvaluta'),
        ],
        string='Netto Weergavemodus (Bevroren)',
        readonly=True,
        copy=False,
        help='Netto weergavemodus bevroren op het moment van loonberekening.',
    )
    sr_netto_bronvaluta = fields.Float(
        string='Netto Loon (Bronvaluta)',
        digits=(16, 2),
        store=True,
        readonly=True,
        copy=False,
        help='Nettoloon omgerekend naar de contractvaluta. Gelijk aan Netto SRD als contractvaluta = SRD.',
    )
    sr_bruto_bronvaluta = fields.Float(
        string='Bruto Loon (Bronvaluta)',
        digits=(16, 2),
        store=True,
        readonly=True,
        copy=False,
        help='Bruto loon omgerekend naar de contractvaluta (bruto SRD ÷ wisselkoers). Gelijk aan Bruto SRD als contractvaluta = SRD.',
    )
    sr_belastingvrij_periode_srd = fields.Float(
        string='Belastingvrije Voet / Periode (SRD)',
        digits=(16, 2),
        store=True,
        readonly=True,
        copy=False,
        help='Bevroren belastingvrije voet per periode op basis van de actieve parameters tijdens berekening.',
    )

    @api.model
    def _default_sr_payslip_layout(self):
        valid_values = {key for key, _label in _SR_PAYSLIP_LAYOUTS}
        company = self.env.company
        if hasattr(company, 'sr_payslip_template') and company.sr_payslip_template in valid_values:
            return company.sr_payslip_template
        params = self.env['ir.config_parameter'].sudo()
        value = params.get_param(_SR_PAYSLIP_LAYOUT_CONFIG_KEY)
        if value in (None, False, ''):
            value = params.get_param(
                _SR_PAYSLIP_LAYOUT_LEGACY_CONFIG_KEY,
                default=_SR_PAYSLIP_LAYOUT_DEFAULT,
            )
        return value if value in valid_values else _SR_PAYSLIP_LAYOUT_DEFAULT

    def _sr_get_effective_payslip_layout(self):
        self.ensure_one()
        valid_values = {key for key, _label in _SR_PAYSLIP_LAYOUTS}
        layout = self.sr_payslip_layout
        if layout and layout in valid_values:
            return layout
        company = self.company_id or self.env.company
        if hasattr(company, 'sr_payslip_template') and company.sr_payslip_template in valid_values:
            return company.sr_payslip_template
        return _SR_PAYSLIP_LAYOUT_DEFAULT

    @api.model
    def _sr_get_payroll_structures(self):
        structures = self.env['hr.payroll.structure']
        for xmlid in _SR_PAYROLL_STRUCTURE_XMLIDS:
            structure = self.env.ref(xmlid, raise_if_not_found=False)
            if structure:
                structures |= structure
        return structures

    def _sr_is_supported_sr_payslip(self):
        self.ensure_one()
        return bool(self.struct_id and self.struct_id in self._sr_get_payroll_structures())

    @api.depends('struct_id')
    def _compute_sr_is_sr_struct(self):
        sr_structures = self._sr_get_payroll_structures()
        for slip in self:
            slip.sr_is_sr_struct = bool(slip.struct_id and slip.struct_id in sr_structures)

    @api.depends('line_ids.code', 'line_ids.total')
    def _compute_sr_summary_display(self):
        for slip in self:
            def _line_total(*codes):
                total = sum((
                    Decimal(str(line.total or 0.0))
                    for line in slip.line_ids
                    if line.code in codes
                ), Decimal('0'))
                return float(total.quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP))

            basic = _line_total('BASIC')
            toelagen = _line_total('SR_ALW')
            kinderbijslag = _line_total('SR_KB_BELAST', 'SR_KB_VRIJ')
            vrijgesteld_contract = _line_total('SR_KINDBIJ')
            input_belastbaar = _line_total('SR_INPUT_BELASTB')
            input_vrijgesteld = _line_total('SR_INPUT_VRIJ')
            overwerk = _line_total('SR_OVERWERK')
            vakantie = _line_total('SR_VAKANTIE')
            gratificatie = _line_total('SR_GRAT')
            bijz_beloning = _line_total('SR_BIJZ')
            uitkering_ineens = _line_total('SR_UITK_INEENS')
            heffingskorting = _line_total('SR_HK')

            bruto_totaal = float(Decimal(str(
                basic + toelagen + kinderbijslag + vrijgesteld_contract
                + input_belastbaar + input_vrijgesteld + overwerk
                + vakantie + gratificatie + bijz_beloning + uitkering_ineens
            )).quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP))
            totaal_lb = float(Decimal(str(abs(_line_total('SR_LB', 'SR_LB_BIJZ', 'SR_LB_17A', 'SR_LB_OVERWERK')))).quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP))
            totaal_aov = float(Decimal(str(abs(_line_total('SR_AOV', 'SR_AOV_BIJZ', 'SR_AOV_17A', 'SR_AOV_OVERWERK')))).quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP))
            overige_inhoudingen = float(Decimal(str(abs(_line_total('SR_PENSIOEN', 'SR_INPUT_AFTREK', 'SR_AFTREK_BV')))).quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP))

            slip.sr_bruto_totaal_display = bruto_totaal
            slip.sr_heffingskorting_display = heffingskorting
            slip.sr_lb_totaal_display = totaal_lb
            slip.sr_aov_totaal_display = totaal_aov
            slip.sr_inhoudingen_totaal_display = totaal_lb + totaal_aov + overige_inhoudingen
            slip.sr_netto_totaal_display = _line_total('NET')

    def compute_sheet(self):
        """Clear the thread-local Art. 14 cache before computing salary rules."""
        _clear_sr_calc_cache()
        try:
            self._sr_lock_for_update()
            sr_structures = self._sr_get_payroll_structures()
            locked_slips = self.filtered(
                lambda slip: slip.struct_id in sr_structures and slip.state in ('done', 'paid')
            )
            if locked_slips and not self.env.context.get('sr_allow_confirmed_recompute'):
                raise UserError(
                    'Bevestigde SR-loonstroken zijn bevroren. Zet de loonstrook eerst terug naar concept '
                    'of gebruik expliciet technische override-context voor herberekening.'
                )
            for slip in self:
                slip._sr_validate_contract_period_integrity()
                slip._sr_validate_fn_period_2026()
                slip._sr_require_positive_contract_wage()
                slip._sr_freeze_currency_snapshot()

            work_entries_by_slip = self._sr_get_period_work_entries_batch()
            self._sr_sync_overtime_inputs_batch(work_entries_by_slip=work_entries_by_slip)
            self._sr_store_work_entry_snapshots_batch(work_entries_by_slip=work_entries_by_slip)

            res = super().compute_sheet()
            for slip in self:
                slip._sr_store_currency_totals()
            return res
        finally:
            _clear_sr_calc_cache()

    def action_payslip_done(self):
        self._sr_lock_for_update()
        for slip in self:
            slip._sr_validate_contract_period_integrity()
            slip._sr_require_positive_contract_wage()
            slip._sr_freeze_currency_snapshot()
        self._sr_store_work_entry_snapshots_batch()
        result = super().action_payslip_done()
        for slip in self:
            slip._sr_store_currency_totals()
        return result

    def write(self, vals):
        locked_snapshot_fields = {
            'sr_frozen_contract_currency_id',
            'sr_frozen_exchange_rate',
            'sr_frozen_netto_display_mode',
        }
        if locked_snapshot_fields.intersection(vals) and not self.env.context.get('sr_allow_locked_currency_update'):
            locked_slips = self.filtered(lambda slip: slip.state in ('done', 'paid'))
            if locked_slips:
                raise UserError(
                    'De bevroren valuta-snapshot van een bevestigde SR-loonstrook mag niet meer worden gewijzigd.'
                )
        return super().write(vals)

    def _sr_line_total(self, *codes):
        self.ensure_one()
        total = sum((
            Decimal(str(line.total or 0.0))
            for line in self.line_ids
            if line.code in codes
        ), Decimal('0'))
        return float(total.quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP))

    def _sr_collect_legacy_fn_aov_recompute_candidates(self):
        sr_structures = self._sr_get_payroll_structures()
        candidates = self.env['hr.payslip']
        before_by_id = {}

        if not sr_structures:
            return candidates, before_by_id

        slips = self.filtered(
            lambda slip: slip.struct_id in sr_structures
            and slip.contract_id
            and slip.contract_id.sr_salary_type == 'fn'
            and slip.state != 'cancel'
        )

        for slip in slips:
            if slip._sr_get_periodes() != 26:
                continue

            stored_aov = abs(slip._sr_line_total('SR_AOV'))
            gross = (
                slip._sr_line_total('BASIC')
                + slip._sr_line_total('SR_ALW')
                + slip._sr_line_total('SR_KB_BELAST')
                + slip._sr_line_total('SR_INPUT_BELASTB')
                + abs(slip._sr_line_total('SR_VGB_BELAST'))
            )
            aftrek_bv = abs(slip._sr_line_total('SR_AFTREK_BV'))
            heffingskorting = slip._sr_line_total('SR_HK')
            if abs(heffingskorting) < 0.005 and slip.contract_id:
                heffingskorting = slip.contract_id._sr_get_heffingskorting_per_periode(
                    slip._rule_parameter('SR_HEFFINGSKORTING'),
                    round_result=False,
                )
            params = calc.fetch_params_from_payslip(slip)
            expected_aov = calc.calculate_lb(
                gross,
                26,
                params,
                aftrek_bv_per_periode=aftrek_bv,
                heffingskorting_per_periode=heffingskorting,
            )['aov_per_periode']
            if abs(Decimal(str(stored_aov)) - Decimal(str(expected_aov))) <= Decimal('0.01'):
                continue

            before_by_id[slip.id] = {
                'aov': stored_aov,
                'net': slip._sr_line_total('NET'),
            }
            candidates |= slip

        return candidates, before_by_id

    def _sr_recompute_legacy_fn_aov_slips(self, limit=None):
        sr_structures = self._sr_get_payroll_structures()
        slips = self

        if not slips:
            if not sr_structures:
                return {
                    'count': 0,
                    'recomputed_ids': [],
                    'detail_lines': [],
                }
            slips = self.search([
                ('struct_id', 'in', sr_structures.ids),
                ('contract_id', '!=', False),
                ('contract_id.sr_salary_type', '=', 'fn'),
                ('state', 'in', ('draft', 'verify', 'done', 'paid')),
            ], order='date_from, number, id', limit=limit)
        elif limit:
            slips = slips[:limit]

        candidates, before_by_id = slips._sr_collect_legacy_fn_aov_recompute_candidates()
        if not candidates:
            return {
                'count': 0,
                'recomputed_ids': [],
                'detail_lines': [],
            }

        recompute_ctx = dict(
            self.env.context,
            sr_allow_confirmed_recompute=True,
            tracking_disable=True,
            mail_notrack=True,
            mail_create_nolog=True,
            mail_create_nosubscribe=True,
        )
        candidates.with_context(**recompute_ctx).compute_sheet()
        recomputed_slips = self.browse(candidates.ids)
        detail_lines = []
        for slip in recomputed_slips:
            before = before_by_id.get(slip.id, {})
            after_aov = abs(slip._sr_line_total('SR_AOV'))
            after_net = slip._sr_line_total('NET')
            slip_label = slip.number or slip.name or f'ID {slip.id}'
            detail_lines.append(
                f'{slip_label} ({slip.employee_id.name}): '
                f'AOV {before.get("aov", 0.0):.2f}->{after_aov:.2f}, '
                f'NET {before.get("net", 0.0):.2f}->{after_net:.2f}'
            )

        return {
            'count': len(recomputed_slips),
            'recomputed_ids': recomputed_slips.ids,
            'detail_lines': detail_lines,
        }

    def action_sr_recompute_legacy_fn_aov_slips(self):
        result = self._sr_recompute_legacy_fn_aov_slips()
        count = result['count']
        detail_preview = '; '.join(result['detail_lines'][:3])

        if count:
            message = f'{count} FN-loonstro(o)k(en) herrekend zonder AOV-franchise.'
            if detail_preview:
                message = f'{message} {detail_preview}'
            if len(result['detail_lines']) > 3:
                message = f'{message} ...'
            notif_type = 'success'
        else:
            message = 'Geen FN-loonstroken gevonden die nog met de oude AOV-franchise berekend zijn.'
            notif_type = 'warning'

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'FN AOV herrekening',
                'message': message,
                'type': notif_type,
                'sticky': False,
            },
        }

    def _sr_require_positive_contract_wage(self):
        self.ensure_one()
        if not self._sr_is_supported_sr_payslip() or not self.contract_id:
            return
        if (self.contract_id.wage or 0.0) > 0.0:
            return
        raise UserError(
            'Deze SR-loonstrook kan niet worden berekend omdat het gekoppelde contract geen positief basisloon heeft. '
            'Corrigeer eerst het contractloon zodat uurloon, overwerk en LB/AOV veilig berekend worden.'
        )

    def _sr_get_period_bounds(self):
        self.ensure_one()
        if not self.date_from or not self.date_to:
            return False, False
        return (
            datetime.combine(self.date_from, time.min),
            datetime.combine(self.date_to + timedelta(days=1), time.min),
        )

    def _sr_get_period_work_entries(self):
        self.ensure_one()
        if not self._sr_is_supported_sr_payslip() or not self.contract_id or not self.date_from or not self.date_to:
            return self.env['hr.work.entry']

        period_start, period_stop = self._sr_get_period_bounds()
        return self.env['hr.work.entry'].search([
            ('contract_id', '=', self.contract_id.id),
            ('date_start', '<', period_stop),
            ('date_stop', '>', period_start),
            # Odoo can flip already-consumed entries to conflict after the first compute;
            # keep them in scope so repeated compute_sheet stays idempotent.
            ('state', 'in', ('validated', 'conflict')),
        ], order='date_start, id')

    def _sr_get_period_work_entries_batch(self):
        work_entry_model = self.env['hr.work.entry']
        grouped_entries = {slip.id: work_entry_model for slip in self}
        sr_structures = self._sr_get_payroll_structures()
        valid_slips = self.filtered(
            lambda slip: slip.struct_id in sr_structures and slip.contract_id and slip.date_from and slip.date_to
        )
        if not valid_slips:
            return grouped_entries

        search_start = datetime.combine(min(valid_slips.mapped('date_from')), time.min)
        search_stop = datetime.combine(max(valid_slips.mapped('date_to')) + timedelta(days=1), time.min)
        contract_entries = {
            contract.id: work_entry_model
            for contract in valid_slips.mapped('contract_id')
        }

        work_entries = work_entry_model.search([
            ('contract_id', 'in', list(contract_entries)),
            ('date_start', '<', search_stop),
            ('date_stop', '>', search_start),
            ('state', 'in', ('validated', 'conflict')),
        ], order='date_start, id')
        for entry in work_entries:
            contract_entries[entry.contract_id.id] |= entry

        for slip in valid_slips:
            period_start, period_stop = slip._sr_get_period_bounds()
            grouped_entries[slip.id] = contract_entries.get(slip.contract_id.id, work_entry_model).filtered(
                lambda entry: entry.date_start < period_stop and entry.date_stop > period_start
            )
        return grouped_entries

    def _sr_build_work_entry_snapshot(self, work_entries=None):
        self.ensure_one()
        work_entries = work_entries if work_entries is not None else self._sr_get_period_work_entries()
        period_start, period_stop = self._sr_get_period_bounds()
        summary = {
            'regular_hours': 0.0,
            'overtime_hours_150': 0.0,
            'overtime_hours_200': 0.0,
            'unpaid_extra_hours': 0.0,
            'total_worked_hours': 0.0,
            'total_worked_days': 0.0,
        }
        worked_days = set()

        for entry in work_entries:
            if hasattr(entry, '_sr_get_actual_duration_hours'):
                actual_hours = entry._sr_get_actual_duration_hours()
            elif entry.date_start and entry.date_stop:
                actual_hours = max((entry.date_stop - entry.date_start).total_seconds() / 3600.0, 0.0)
            else:
                actual_hours = entry.duration or 0.0

            overtime_150 = max(entry.sr_overtime_150 or 0.0, 0.0)
            overtime_200 = max(entry.sr_overtime_200 or 0.0, 0.0)
            unpaid_extra = max(entry.sr_extra_hours or 0.0, 0.0) if getattr(entry, 'sr_overtime_treatment', False) == 'unpaid' else 0.0
            regular_hours = max(actual_hours - overtime_150 - overtime_200 - unpaid_extra, 0.0)

            summary['regular_hours'] += regular_hours
            summary['overtime_hours_150'] += overtime_150
            summary['overtime_hours_200'] += overtime_200
            summary['unpaid_extra_hours'] += unpaid_extra
            summary['total_worked_hours'] += actual_hours

            if actual_hours > 0.005 and entry.date_start:
                worked_days |= self._sr_get_worked_dates_for_entry(
                    entry,
                    period_start=period_start,
                    period_stop=period_stop,
                )

        summary['total_worked_days'] = float(len(worked_days))
        return summary

    def _sr_get_worked_dates_for_entry(self, entry, period_start=None, period_stop=None):
        effective_start = entry.date_start
        effective_stop = entry.date_stop
        if period_start and effective_start:
            effective_start = max(effective_start, period_start)
        if period_stop and effective_stop:
            effective_stop = min(effective_stop, period_stop)
        if not effective_start or not effective_stop or effective_stop <= effective_start:
            return set()

        worked_dates = set()
        current_start = effective_start
        while current_start < effective_stop:
            worked_dates.add(current_start.date())
            next_day_start = datetime.combine(current_start.date() + timedelta(days=1), time.min)
            current_start = min(next_day_start, effective_stop)
        return worked_dates

    def _sr_store_work_entry_snapshot(self, work_entries=None):
        self.ensure_one()
        summary = self._sr_build_work_entry_snapshot(work_entries=work_entries)
        self.update({
            'sr_regular_hours': summary['regular_hours'],
            'sr_overtime_hours_150': summary['overtime_hours_150'],
            'sr_overtime_hours_200': summary['overtime_hours_200'],
            'sr_unpaid_extra_hours': summary['unpaid_extra_hours'],
            'sr_total_worked_hours': summary['total_worked_hours'],
            'sr_total_worked_days': summary['total_worked_days'],
        })

    def _sr_store_work_entry_snapshots_batch(self, work_entries_by_slip=None):
        work_entries_by_slip = work_entries_by_slip or self._sr_get_period_work_entries_batch()
        for slip in self:
            slip._sr_store_work_entry_snapshot(work_entries=work_entries_by_slip.get(slip.id))

    def _sr_get_config_exchange_rate(self, currency=None):
        self.ensure_one()
        contract = self.contract_id
        currency = currency or (contract.sr_contract_currency if contract else False)
        if not currency or currency.name == 'SRD':
            return 1.0
        company = self.company_id or self.env.company
        if currency.name == 'USD':
            return company.sr_exchange_rate_usd or 36.5
        if currency.name == 'EUR':
            return company.sr_exchange_rate_eur or 39.0
        return 1.0

    def _sr_freeze_currency_snapshot(self, force=False):
        """
        Bevriест de contractvaluta, wisselkoers en display-modus op de loonstrook.

        Wordt aangeroepen aan het begin van compute_sheet(), vóór de salarisregels,
        zodat _sr_wage_in_srd() en _sr_get_hourly_rate() de bevroren waarden kunnen lezen.
        """
        self.ensure_one()
        if not force and self.sr_frozen_contract_currency_id and self.sr_exchange_rate:
            return

        contract = self.contract_id
        if not contract:
            return

        # Contractvaluta van het contract lezen
        currency = contract.sr_contract_currency
        if not currency:
            currency = self.env['res.currency'].search([('name', '=', 'SRD')], limit=1)

        # Wisselkoers ophalen uit res.company (per-bedrijf)
        params = self.env['ir.config_parameter'].sudo()
        rate = self._sr_get_config_exchange_rate(currency=currency)

        # Display modus ophalen
        display_mode = params.get_param(_SR_DISPLAY_MODE_CONFIG_KEY, default=_SR_DISPLAY_MODE_DEFAULT)
        if display_mode not in ('srd', 'contract_currency'):
            display_mode = _SR_DISPLAY_MODE_DEFAULT

        self.update({
            'sr_frozen_contract_currency_id': currency.id if currency else False,
            'sr_frozen_exchange_rate': rate,
            'sr_frozen_netto_display_mode': display_mode,
        })

    def _sr_store_currency_totals(self):
        self.ensure_one()
        if not self.line_ids:
            return

        def _line_total(*codes):
            return sum(
                line.total or 0.0
                for line in self.line_ids
                if line.code in codes
            )

        netto_srd = _line_total('NET')
        bruto_srd = _line_total(
            'BASIC', 'SR_ALW', 'SR_KB_BELAST', 'SR_KB_VRIJ', 'SR_KINDBIJ',
            'SR_INPUT_BELASTB', 'SR_INPUT_VRIJ', 'SR_OVERWERK',
            'SR_VAKANTIE', 'SR_GRAT', 'SR_BIJZ', 'SR_UITK_INEENS',
        )
        rate = self.sr_exchange_rate or 1.0
        currency = self.sr_frozen_contract_currency_id
        if currency and currency.name not in ('SRD', False, '') and rate > 0:
            netto_bronvaluta = Decimal(str(netto_srd)) / Decimal(str(rate))
            bruto_bronvaluta = Decimal(str(bruto_srd)) / Decimal(str(rate))
        else:
            netto_bronvaluta = Decimal(str(netto_srd))
            bruto_bronvaluta = Decimal(str(bruto_srd))

        belastingvrij_jaar = Decimal(str(self._rule_parameter('SR_BELASTINGVRIJ_JAAR') or 0.0))
        periodes = Decimal(str(self._sr_get_periodes() or 0))
        belastingvrij_periode = Decimal('0.0')
        if periodes > 0:
            belastingvrij_periode = belastingvrij_jaar / periodes

        self.update({
            'sr_netto_bronvaluta': float(netto_bronvaluta.quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP)),
            'sr_bruto_bronvaluta': float(bruto_bronvaluta.quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP)),
            'sr_belastingvrij_periode_srd': float(
                belastingvrij_periode.quantize(_SR_MONEY_QUANT, rounding=ROUND_HALF_UP)
            ),
        })

    def _sr_wage_in_srd(self, round_result=True):
        """
        Geeft het contractloon per periode terug in SRD.

        Het basisloon wordt altijd als maandloon ingevoerd.
        Voor FN-contracten wordt automatisch omgerekend: maandloon × 12 ÷ 26.
        De bevroren wisselkoers wordt gebruikt zodat herberekening consistent blijft.
        """
        self.ensure_one()
        wage = self.contract_id.wage or 0.0
        if not wage:
            return 0.0
        rate = self.sr_exchange_rate or 1.0
        currency = self.sr_frozen_contract_currency_id
        if currency and currency.name not in ('SRD', False, ''):
            wage_srd = Decimal(str(wage)) * Decimal(str(rate))
        else:
            wage_srd = Decimal(str(wage))

        if self.contract_id.sr_salary_type == 'fn':
            wage_srd = wage_srd * Decimal('12') / Decimal('26')

        quant = _SR_MONEY_QUANT if round_result else _SR_INTERNAL_MONEY_QUANT
        return float(wage_srd.quantize(quant, rounding=ROUND_HALF_UP))

    def _rule_parameter(self, code):
        self.ensure_one()
        ref_date = self.date_to or self.date_from or dt_date.today()
        # ir.config_parameter overrides take priority (Settings page) over hr.rule.parameter.
        config_key = calc.get_config_parameter_key(code)
        if config_key:
            raw = self.env['ir.config_parameter'].sudo().get_param(config_key)
            if not calc.is_missing_parameter_value(raw):
                normalized = calc.normalize_config_parameter_value(code, raw)
                try:
                    return float(normalized)
                except (TypeError, ValueError):
                    pass
        try:
            value = super()._rule_parameter(code)
        except (UserError, KeyError, TypeError, ValueError):
            value = None
        if not calc.is_missing_parameter_value(value):
            return value
        hardcoded = calc.get_config_parameter_default(code)
        if not calc.is_missing_parameter_value(hardcoded):
            return hardcoded
        return calc.get_sr_parameter_value(
            self.env, code, ref_date,
            default=None,
            raise_if_not_found=True,
        )

    def _sr_get_layout_label(self):
        self.ensure_one()
        layout_labels = dict(_SR_PAYSLIP_LAYOUTS)
        return layout_labels.get(
            self._sr_get_effective_payslip_layout(),
            layout_labels[_SR_PAYSLIP_LAYOUT_DEFAULT],
        )

    def _sr_money_quantize(self, value, quant=_SR_MONEY_QUANT):
        self.ensure_one()
        if value in (None, False, ''):
            return Decimal('0').quantize(quant, rounding=ROUND_HALF_UP)
        return Decimal(str(value)).quantize(quant, rounding=ROUND_HALF_UP)

    def _sr_validate_contract_period_integrity(self):
        self.ensure_one()
        if not self._sr_is_supported_sr_payslip() or not self.contract_id or not self.employee_id or not self.date_from or not self.date_to:
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
                'maandloon/FN en vaste regels niet door elkaar lopen.'
            )

    def _sr_get_hourly_rate(self):
        self.ensure_one()
        wage_srd = self._sr_wage_in_srd()
        if not wage_srd:
            return 0.0
        divisor = Decimal('80') if self._sr_get_periodes() == 26 else Decimal('173.333333')
        hourly_rate = Decimal(str(wage_srd)) / divisor
        return float(hourly_rate.quantize(_SR_HOURLY_RATE_QUANT, rounding=ROUND_HALF_UP))

    def _sr_prepare_overtime_inputs_from_work_entries(self, work_entries=None):
        """Bouw nog niet opgeslagen overwerk-inputs voor deze loonstrook."""
        self.ensure_one()

        if not self._sr_is_supported_sr_payslip() or not self.contract_id or not self.date_from or not self.date_to:
            return []

        # Medewerkers zonder overwerkrecht krijgen geen variabele overwerkinput
        if not self.contract_id.sr_has_overtime_right:
            return []

        hourly_rate = self._sr_get_hourly_rate()
        if hourly_rate <= 0:
            return []

        # Zoek alle gevalideerde work entries in de loonperiode
        work_entries = work_entries if work_entries is not None else self._sr_get_period_work_entries()

        # Lees multiplier-factors uit configuratie
        config = self.env['ir.config_parameter'].sudo()
        factor_150 = float(config.get_param('sr_payroll.overwerk_factor_150', '1.5'))
        factor_200 = float(config.get_param('sr_payroll.overwerk_factor_200', '2.0'))

        # Sommeer bucket-uren over alle entries; legacy entries apart bijhouden
        total_ot_150 = Decimal('0')
        total_ot_200 = Decimal('0')
        legacy_entries = []
        inputs_to_create = []

        for entry in work_entries:
            has_buckets = (entry.sr_overtime_150 or 0.0) > 0 or (entry.sr_overtime_200 or 0.0) > 0
            if has_buckets:
                total_ot_150 += Decimal(str(entry.sr_overtime_150 or 0.0))
                total_ot_200 += Decimal(str(entry.sr_overtime_200 or 0.0))
            elif entry.work_entry_type_id.sr_is_overtime:
                # Backward-compat: entry met overtijdtype maar zonder gevulde buckets
                legacy_entries.append(entry)

        # ── Nieuwe bucket-aanpak ──────────────────────────────────────────
        if total_ot_150 > 0:
            ot_type_150 = self.env.ref(
                'l10n_sr_hr_payroll.sr_input_overwerk_150', raise_if_not_found=False
            )
            if ot_type_150:
                amount = float(self._sr_money_quantize(
                    total_ot_150 * Decimal(str(hourly_rate)) * Decimal(str(factor_150))
                ))
                if amount > 0:
                    hrs = float(total_ot_150)
                    inputs_to_create.append({
                        'payslip_id': self.id,
                        'name': f'Overwerk 150% ({hrs:.2f}u \u00d7 SRD {hourly_rate:.4f}/u \u00d7 {factor_150})',
                        'input_type_id': ot_type_150.id,
                        'amount': amount,
                        'sr_generated_from_work_entry': True,
                    })

        if total_ot_200 > 0:
            ot_type_200 = self.env.ref(
                'l10n_sr_hr_payroll.sr_input_overwerk_200', raise_if_not_found=False
            )
            if ot_type_200:
                amount = float(self._sr_money_quantize(
                    total_ot_200 * Decimal(str(hourly_rate)) * Decimal(str(factor_200))
                ))
                if amount > 0:
                    hrs = float(total_ot_200)
                    inputs_to_create.append({
                        'payslip_id': self.id,
                        'name': f'Overwerk 200% ({hrs:.2f}u \u00d7 SRD {hourly_rate:.4f}/u \u00d7 {factor_200})',
                        'input_type_id': ot_type_200.id,
                        'amount': amount,
                        'sr_generated_from_work_entry': True,
                    })

        # ── Backward-compat: legacy overtime entries (geen buckets) ────────
        if legacy_entries:
            period_start, period_stop = self._sr_get_period_bounds()
            overtime_type = self.env.ref(
                'l10n_sr_hr_payroll.sr_input_overwerk', raise_if_not_found=False
            )
            if overtime_type:
                for entry in legacy_entries:
                    effective_start = max(entry.date_start, period_start)
                    effective_stop = min(entry.date_stop, period_stop)
                    hours = max(0.0, (effective_stop - effective_start).total_seconds() / 3600.0)
                    if hours <= 0:
                        continue
                    multiplier = entry.work_entry_type_id.sr_overtime_multiplier or 1.0
                    amount = float(self._sr_money_quantize(
                        Decimal(str(hours)) * Decimal(str(hourly_rate)) * Decimal(str(multiplier))
                    ))
                    if amount <= 0:
                        continue
                    inputs_to_create.append({
                        'payslip_id': self.id,
                        'name': f'{entry.work_entry_type_id.name} ({hours:.2f}u)',
                        'input_type_id': overtime_type.id,
                        'amount': amount,
                        'sr_generated_from_work_entry': True,
                        'sr_work_entry_id': entry.id,
                    })

        return inputs_to_create

    def _sr_sync_overtime_inputs_from_work_entries(self, work_entries=None):
        """Synchroniseer overwerk payslip-inputs voor één loonstrook."""
        self.ensure_one()
        generated_inputs = self._sr_get_generated_overtime_inputs()
        if generated_inputs:
            generated_inputs.unlink()

        inputs_to_create = self._sr_prepare_overtime_inputs_from_work_entries(work_entries=work_entries)
        if inputs_to_create:
            self.env['hr.payslip.input'].create(inputs_to_create)

    def _sr_sync_overtime_inputs_batch(self, work_entries_by_slip=None):
        generated_inputs = self._sr_get_generated_overtime_inputs()
        if generated_inputs:
            generated_inputs.unlink()

        work_entries_by_slip = work_entries_by_slip or self._sr_get_period_work_entries_batch()
        inputs_to_create = []
        for slip in self:
            inputs_to_create.extend(
                slip._sr_prepare_overtime_inputs_from_work_entries(work_entries=work_entries_by_slip.get(slip.id))
            )

        if inputs_to_create:
            self.env['hr.payslip.input'].create(inputs_to_create)

    def _sr_get_generated_overtime_inputs(self):
        if not self.ids:
            return self.env['hr.payslip.input']
        return self.env['hr.payslip.input'].search([
            ('payslip_id', 'in', self.ids),
            ('sr_generated_from_work_entry', '=', True),
        ])

    def _sr_lock_for_update(self):
        if not self.ids:
            return
        try:
            with self.env.cr.savepoint(flush=False):
                self.env.cr.execute(
                    f'SELECT id FROM {self._table} WHERE id IN %s FOR UPDATE NOWAIT',
                    [tuple(self.ids)],
                )
        except psycopg2.errors.LockNotAvailable:
            raise UserError(
                'Een van de geselecteerde loonstroken wordt al door een andere berekening verwerkt. '
                'Wacht tot die berekening klaar is en probeer daarna opnieuw.'
            ) from None

    def _sr_get_periodes(self):
        """Bepaalt het aantal periodes per jaar: 12 (maandloon) of 26 (FN)."""
        self.ensure_one()
        contract = self.contract_id
        if not contract:
            return 12
        return 26 if contract.sr_salary_type == 'fn' else 12

    def _sr_get_fn_period_2026(self):
        """Geeft FN-periode-info terug op basis van de loonstrookdatums.

        Probeert eerst een exacte match met de standaard SR-kalender; anders
        wordt de periodelabel dynamisch berekend vanuit de dag-positie in het jaar.
        Zo kunnen bedrijven hun eigen betaalschema gebruiken (bijv. 1-14 en 16-31).
        """
        self.ensure_one()
        if not self.date_from or not self.date_to:
            return False
        for period in SR_FN_2026_PERIODS:
            if self.date_from == period['date_from'] and self.date_to == period['date_to']:
                return period
        year = self.date_from.year
        day_of_year = (self.date_from - dt_date(year, 1, 1)).days
        period_num = max(1, min(26, day_of_year // 14 + 1))
        return {
            'indicator': f'{year}{period_num:02d}',
            'label': f'{year}FN{period_num}',
            'date_from': self.date_from,
            'date_to': self.date_to,
        }

    def _sr_validate_fn_period_2026(self):
        """Valideert dat een FN-loonstrook ca. 14 dagen beslaat (13–16 dagen).

        Bedrijven mogen hun eigen betaalschema bepalen — de periode hoeft niet
        exact overeen te komen met de standaard SR-kalender.
        """
        self.ensure_one()
        contract = self.contract_id
        if not contract or contract.sr_salary_type != 'fn':
            return
        if not self.date_from or not self.date_to:
            return
        duration = (self.date_to - self.date_from).days + 1
        if duration < 13 or duration > 16:
            raise UserError(
                f'FN-loonstroken moeten ca. 14 dagen beslaan (13–16 dagen). '
                f'De ingestelde periode beslaat {duration} dag(en). '
                f'Pas de datums aan of gebruik Maandloon voor een andere periodelengte.'
            )

    def _sr_get_cached_result(self, gross_per_periode, aftrek_bv=0.0, heffingskorting=0.0):
        """
        Berekent Artikel 14 één keer per (payslip, gross, aftrek_bv) combinatie
        en cached het resultaat in thread-local opslag om redundante
        berekeningen te voorkomen wanneer SR_LB en SR_AOV regels
        achtereenvolgens dezelfde waarden opvragen.
        """
        self.ensure_one()
        cache = _get_sr_calc_cache()
        cache_key = (
            self.id,
            str(self._sr_money_quantize(gross_per_periode, quant=_SR_INTERNAL_MONEY_QUANT)),
            str(self._sr_money_quantize(aftrek_bv, quant=_SR_INTERNAL_MONEY_QUANT)),
            str(self._sr_money_quantize(heffingskorting, quant=_SR_INTERNAL_MONEY_QUANT)),
        )
        if cache_key in cache:
            return cache[cache_key]
        params = calc.fetch_params_from_payslip(self)
        periodes = self._sr_get_periodes()
        result = calc.calculate_lb(
            gross_per_periode, periodes, params,
            aftrek_bv_per_periode=aftrek_bv,
            heffingskorting_per_periode=heffingskorting,
        )
        cache[cache_key] = result
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
        heffingskorting = self.contract_id._sr_get_heffingskorting_per_periode(
            self._rule_parameter('SR_HEFFINGSKORTING'),
            round_result=False,
        ) if self.contract_id else 0.0
        return self._sr_get_cached_result(
            gross_per_periode,
            aftrek_bv,
            heffingskorting=heffingskorting,
        )['lb_per_periode']

    def _sr_artikel14_aov(self, gross_per_periode, aftrek_bv=0.0):
        """
        Berekent AOV bijdrage per periode.

        Wordt aangeroepen door de SR_AOV salarisregel.

        :param gross_per_periode: Bruto belastbaar loon per periode
        :param aftrek_bv: Aftrek belastingvrij per periode (Art. 10f)
        :returns: positief bedrag AOV per periode
        """
        heffingskorting = self.contract_id._sr_get_heffingskorting_per_periode(
            self._rule_parameter('SR_HEFFINGSKORTING'),
            round_result=False,
        ) if self.contract_id else 0.0
        return self._sr_get_cached_result(
            gross_per_periode,
            aftrek_bv,
            heffingskorting=heffingskorting,
        )['aov_per_periode']

    def _sr_get_fn_annual_alignment_target(self):
        """Geeft het maandloon-jaartotaal terug dat een full-year FN-contract moet benaderen."""
        self.ensure_one()
        contract = self.contract_id
        if not contract or contract.sr_salary_type != 'fn':
            return None
        if not self.date_from or not self.date_to:
            return None
        if any(abs(line.amount or 0.0) > 0.000001 for line in self.input_line_ids):
            return None

        scale = Decimal('26') / Decimal('12')
        exchange_rate = self.sr_exchange_rate or 1.0

        wage = Decimal(str(
            contract._sr_get_wage_per_period_srd(exchange_rate=exchange_rate, round_result=False)
        )) * scale
        belastbaar_toelagen = Decimal(str(
            contract._sr_resolve_regels('belastbaar', exchange_rate=exchange_rate, round_result=False)
        )) * scale
        vrijgesteld_toelagen = Decimal(str(
            contract._sr_resolve_other_vrijgestelde_regels(exchange_rate=exchange_rate, round_result=False)
        )) * scale
        inhoudingen = Decimal(str(
            contract._sr_resolve_regels('inhouding', exchange_rate=exchange_rate, round_result=False)
        )) * scale
        aftrek_bv = Decimal(str(
            contract._sr_resolve_regels('aftrek_belastingvrij', exchange_rate=exchange_rate, round_result=False)
        )) * scale
        kb_split = contract._sr_kinderbijslag_split(exchange_rate=exchange_rate, round_result=False)
        kb_belastbaar = Decimal(str(kb_split['belastbaar'])) * scale
        kb_vrijgesteld = Decimal(str(kb_split['vrijgesteld'])) * scale
        vgb_belastbaar = Decimal(str(
            contract._sr_vgb_fiscaal_belastbaar(exchange_rate=exchange_rate, round_result=False)
        )) * scale
        heffingskorting = Decimal(str(
            contract._sr_get_heffingskorting_per_periode(
                self._rule_parameter('SR_HEFFINGSKORTING'),
                round_result=False,
            )
        )) * scale

        bruto_belastbaar = wage + belastbaar_toelagen + kb_belastbaar + vgb_belastbaar
        bruto_totaal = wage + belastbaar_toelagen + kb_belastbaar + kb_vrijgesteld + vrijgesteld_toelagen
        monthly_result = calc.calculate_lb(
            float(bruto_belastbaar),
            12,
            calc.fetch_params_from_payslip(self),
            aftrek_bv_per_periode=float(aftrek_bv),
            heffingskorting_per_periode=float(heffingskorting),
        )
        monthly_net = calc.round_money(
            bruto_totaal
            - Decimal(str(monthly_result['lb_per_periode']))
            - Decimal(str(monthly_result['aov_per_periode']))
            - inhoudingen
            - aftrek_bv
        )
        return self._sr_money_quantize(Decimal(str(monthly_net)) * Decimal('12'))

    def _sr_fn_annual_alignment_adjustment(self, current_net):
        """Corrigeert de laatste FN-loonstrook zodat 26 FN-betalingen exact het maandjaartotaal volgen."""
        self.ensure_one()
        contract = self.contract_id
        if not contract or contract.sr_salary_type != 'fn' or self._sr_get_periodes() != 26:
            return 0.0

        fn_period = self._sr_get_fn_period_2026()
        if not fn_period or not str(fn_period.get('indicator', '')).endswith('26'):
            return 0.0

        target_annual = self._sr_get_fn_annual_alignment_target()
        if target_annual is None:
            return 0.0

        year_start = dt_date(self.date_from.year, 1, 1)
        previous_slips = self.search([
            ('id', '!=', self.id),
            ('contract_id', '=', contract.id),
            ('state', '!=', 'cancel'),
            ('date_from', '>=', year_start),
            ('date_to', '<', self.date_from),
        ], order='date_from, id')
        if len(previous_slips) != 25:
            return 0.0
        if any(not slip.line_ids.filtered(lambda line: line.code == 'NET') for slip in previous_slips):
            return 0.0

        previous_total = sum((
            Decimal(str(slip._sr_line_total('NET')))
            for slip in previous_slips
        ), Decimal('0'))
        current_net_dec = self._sr_money_quantize(current_net)
        adjustment = (target_annual - previous_total - current_net_dec).quantize(
            _SR_MONEY_QUANT,
            rounding=ROUND_HALF_UP,
        )
        if abs(adjustment) < Decimal('0.005'):
            return 0.0
        return float(adjustment)

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
        vgb_belastbaar_bedrag = abs(_line_total('SR_VGB_BELAST'))

        # ── Calculator voor Art. 14 stap-detail ──────────────────────────────
        # Herleid de wettelijke Art. 14 grondslag uit de expliciete belastbare
        # looncomponenten. Historische SR_HK-regels kunnen het GROSS/NET totaal
        # op bestaande slips verhogen, maar horen niet in de LB/AOV-grondslag.
        gross = basic + toelagen + kb_belastbaar + input_belastbaar + vgb_belastbaar_bedrag
        params = calc.fetch_params_from_payslip(self)
        heffingskorting_calc = heffingskorting
        if abs(heffingskorting_calc) < 0.005 and contract:
            heffingskorting_calc = contract._sr_get_heffingskorting_per_periode(
                self._rule_parameter('SR_HEFFINGSKORTING'),
                round_result=False,
            )
        r = calc.calculate_lb(
            gross,
            periodes,
            params,
            aftrek_bv_per_periode=aftrek_bv,
            heffingskorting_per_periode=heffingskorting_calc,
        )

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
        toelagen_totaal = bruto_totaal - basic
        netto = bruto_totaal - totaal_inhoudingen - aftrek_bv

        rule_exchange_rate = self.sr_exchange_rate or 1.0
        contract_line_groups = {
            'belastbaar': [],
            'vrijgesteld': [],
            'aftrek_belastingvrij': [],
            'inhouding': [],
        }
        for line in contract.sr_vaste_regels.sorted(lambda record: (record.sequence, record.id)):
            category = line._sr_effective_category()
            if category not in contract_line_groups:
                continue
            if category == 'vrijgesteld' and line._is_sr_kindbijslag_line():
                continue
            amount = contract._sr_resolve_line_amount(line, exchange_rate=rule_exchange_rate)
            if amount <= 0:
                continue
            contract_line_groups[category].append({
                'name': line.type_id.name or line.name or 'Contractregel',
                'amount': amount,
            })

        contract_belastbare_lines = contract_line_groups['belastbaar']
        contract_vrijgestelde_lines = contract_line_groups['vrijgesteld']
        contract_aftrek_bv_lines = contract_line_groups['aftrek_belastingvrij']
        contract_inhoudingen = contract_line_groups['inhouding']

        input_line_groups = {
            'belastbaar': [],
            'vrijgesteld': [],
            'inhouding': [],
        }
        for input_line in self.input_line_ids.filtered(lambda record: record.amount > 0):
            category = input_line.input_type_id.sr_categorie
            if category not in input_line_groups:
                continue
            input_line_groups[category].append({
                'name': input_line.input_type_id.name or input_line.name or 'Payslip input',
                'amount': input_line.amount,
            })

        input_belastbaar_lines = input_line_groups['belastbaar']
        input_vrijgesteld_lines = input_line_groups['vrijgesteld']
        input_inhoudingen = input_line_groups['inhouding']

        earnings_lines = []

        def _append_amount_line(target, label, amount, style='normal'):
            if abs(amount or 0.0) < 0.005:
                return
            target.append({
                'name': label,
                'amount': abs(amount),
                'style': style,
            })

        _append_amount_line(earnings_lines, 'Salaris', basic, 'primary')
        if contract_belastbare_lines:
            for earning in contract_belastbare_lines:
                _append_amount_line(earnings_lines, earning['name'], earning['amount'])
        else:
            _append_amount_line(earnings_lines, 'Toelagen', toelagen)
        _append_amount_line(earnings_lines, 'Kinderbijslag', kinderbijslag, 'muted')
        if contract_vrijgestelde_lines:
            for earning in contract_vrijgestelde_lines:
                _append_amount_line(earnings_lines, earning['name'], earning['amount'], 'muted')
        else:
            _append_amount_line(earnings_lines, 'Vrijgestelde vergoedingen', vrijgesteld_contract, 'muted')
        if input_belastbaar_lines:
            for earning in input_belastbaar_lines:
                _append_amount_line(earnings_lines, earning['name'], earning['amount'])
        else:
            _append_amount_line(earnings_lines, 'Belastbare payslip inputs', input_belastbaar)
        if input_vrijgesteld_lines:
            for earning in input_vrijgesteld_lines:
                _append_amount_line(earnings_lines, earning['name'], earning['amount'], 'muted')
        else:
            _append_amount_line(earnings_lines, 'Vrijgestelde payslip inputs', input_vrijgesteld, 'muted')
        _append_amount_line(earnings_lines, 'Overwerk', overwerk)
        _append_amount_line(earnings_lines, 'Vakantiegeld', vakantie)
        _append_amount_line(earnings_lines, 'Gratificatie', gratificatie)
        _append_amount_line(earnings_lines, 'Bijzondere beloning', bijz_beloning)
        _append_amount_line(earnings_lines, 'Uitkering ineens', uitkering_ineens)

        deductions_lines = []
        _append_amount_line(deductions_lines, 'Loonbelasting', lb_per_periode, 'tax')
        _append_amount_line(deductions_lines, 'LB bijzondere beloningen', lb_bijz, 'tax')
        _append_amount_line(deductions_lines, 'LB uitkering ineens', lb_17a, 'tax')
        _append_amount_line(deductions_lines, 'LB overwerk', lb_overwerk, 'tax')
        _append_amount_line(deductions_lines, 'AOV', aov_per_periode, 'tax')
        _append_amount_line(deductions_lines, 'AOV bijzondere beloningen', aov_bijz, 'tax')
        _append_amount_line(deductions_lines, 'AOV uitkering ineens', aov_17a, 'tax')
        _append_amount_line(deductions_lines, 'AOV overwerk', aov_overwerk, 'tax')
        if contract_aftrek_bv_lines:
            for inhouding in contract_aftrek_bv_lines:
                _append_amount_line(deductions_lines, inhouding['name'], inhouding['amount'])
        else:
            _append_amount_line(deductions_lines, 'Aftrek belastingvrij (Art. 10f)', aftrek_bv)
        if contract_inhoudingen:
            for inhouding in contract_inhoudingen:
                _append_amount_line(deductions_lines, inhouding['name'], inhouding['amount'])
        else:
            _append_amount_line(deductions_lines, 'Andere inhoudingen', pensioen)
        for inhouding in input_inhoudingen:
            _append_amount_line(deductions_lines, inhouding['name'], inhouding['amount'])

        summary_cards = [
            {'label': 'Basisloon', 'amount': basic, 'tone': 'neutral'},
            {'label': 'Toelagen', 'amount': toelagen_totaal, 'tone': 'neutral'},
            {'label': 'Inhoudingen', 'amount': totaal_inhoudingen + aftrek_bv, 'tone': 'danger'},
        ]
        employee = self.employee_id
        bank_account = employee.bank_account_id
        employment_start_date = getattr(employee, 'first_contract_date', False) or contract.date_start
        employee_reference = employee.identification_id or str(employee.id)
        bank_account_number = bank_account.acc_number or bank_account.sanitized_acc_number or False
        bank_name = bank_account.bank_id.name if bank_account and bank_account.bank_id else False
        period_title = self.date_to.strftime('%b %Y').upper() if self.date_to else ''
        if fn_period:
            period_title = f'{period_title} {fn_period["label"]}'

        hours_summary_lines = []
        for label, hours, tone in [
            ('Normale uren', self.sr_regular_hours, 'neutral'),
            ('Overwerk 150%', self.sr_overtime_hours_150, 'warning'),
            ('Overwerk 200%', self.sr_overtime_hours_200, 'danger'),
            ('Extra uren niet uitbetaald', self.sr_unpaid_extra_hours, 'muted'),
        ]:
            if abs(hours or 0.0) < 0.005:
                continue
            hours_summary_lines.append({
                'label': label,
                'hours': abs(hours),
                'tone': tone,
            })

        worked_days_rows = []
        for worked_day in self.worked_days_line_ids.sorted(lambda record: (record.sequence, record.id)):
            hours = worked_day.number_of_hours or 0.0
            days = worked_day.number_of_days or 0.0
            amount = worked_day.amount or 0.0
            if abs(hours) < 0.005 and abs(days) < 0.005 and abs(amount) < 0.005:
                continue
            worked_days_rows.append({
                'name': worked_day.name or worked_day.work_entry_type_id.name or 'Werktijd',
                'days': days,
                'hours': hours,
                'amount': amount,
            })

        line_label_map = {
            'BASIC': 'SALARIS',
            'SR_ALW': 'TOELAGEN',
            'SR_KB_VRIJ': 'KINDERBIJSLAG',
            'SR_KB_BELAST': 'KINDERBIJSLAG BELAST',
            'SR_KINDBIJ': 'VRIJGESTELDE VERGOEDINGEN',
            'SR_INPUT_BELASTB': 'BELASTBARE INPUT',
            'SR_INPUT_VRIJ': 'VRIJGESTELDE INPUT',
            'SR_OVERWERK': 'OVERWERK',
            'SR_VAKANTIE': 'VAKANTIETOELAGE',
            'SR_GRAT': 'GRATIFICATIE',
            'SR_BIJZ': 'BIJZONDERE BELONING',
            'SR_UITK_INEENS': 'UITKERING INEENS',
            'SR_LB': 'LOONBELASTING',
            'SR_LB_BIJZ': 'LOONBELASTING BIJZ.',
            'SR_LB_17A': 'LOONBELASTING 17A',
            'SR_LB_OVERWERK': 'LOONBELASTING OVERWERK',
            'SR_AOV': 'PREMIE AOV',
            'SR_AOV_BIJZ': 'PREMIE AOV BIJZ.',
            'SR_AOV_17A': 'PREMIE AOV 17A',
            'SR_AOV_OVERWERK': 'PREMIE AOV OVERWERK',
            'SR_PENSIOEN': 'ANDERE INHOUDINGEN',
            'SR_INPUT_AFTREK': 'ANDERE INHOUDINGEN (PAYSLIP)',
            'SR_AFTREK_BV': 'AFTREK BELASTINGVRIJ',
            'SR_HK': 'HEFFINGSKORTING',
        }

        payslip_line_rows = []
        belasting_line_rows = []
        display_line_codes_to_skip = {'GROSS', 'NET', 'SR_HK'}
        # Categorie-labels voor bekende loonregels (getoond op de loonstrook naast de omschrijving)
        _code_categorie_label = {
            'SR_KB_BELAST': 'Belastbaar',
            'SR_KB_VRIJ': 'Belastingvrij',
            'SR_KINDBIJ': 'Belastingvrij',
            'SR_INPUT_BELASTB': 'Belastbaar',
            'SR_INPUT_VRIJ': 'Belastingvrij',
            'SR_AFTREK_BV': 'Aftrek belastingvrij',
            'SR_PENSIOEN': 'Inhouding',
            'SR_INPUT_AFTREK': 'Inhouding',
        }

        def _append_breakdown_rows(code, rows, categorie_label, is_credit=False):
            for item in rows:
                amount = item['amount']
                row_name = (item['name'] or 'Post').upper()
                debit = 0.0 if is_credit else amount
                credit = amount if is_credit else 0.0
                payslip_line_rows.append({
                    'code': code,
                    'name': row_name,
                    'categorie_label': categorie_label,
                    'quantity': 1.0,
                    'quantity_display': '',
                    'debit': debit,
                    'credit': credit,
                    'net': debit - credit,
                })
                belasting_line_rows.append({
                    'code': code,
                    'name': row_name,
                    'categorie_label': categorie_label,
                    'quantity_display': '',
                    'verloond_bedrag': -amount if is_credit else amount,
                    'loonbelasting': 0.0,
                    'premie_aov': 0.0,
                })

        for line in self.line_ids.sorted(lambda record: (record.sequence, record.code or '', record.id)):
            total = line.total or 0.0
            if line.code in display_line_codes_to_skip or not line.appears_on_payslip or abs(total) < 0.005:
                continue

            quantity = line.quantity or 0.0
            quantity_display = ''
            if abs(quantity - 1.0) > 0.0001 and abs(quantity) > 0.0001:
                quantity_display = '{:,.2f}'.format(quantity).rstrip('0').rstrip('.')

            # Uitklappen naar individuele contract- of inputregels waar mogelijk.
            if line.code == 'SR_ALW' and contract_belastbare_lines:
                _append_breakdown_rows('SR_ALW', contract_belastbare_lines, 'Belastbaar')
                continue
            if line.code == 'SR_KINDBIJ' and contract_vrijgestelde_lines:
                _append_breakdown_rows('SR_KINDBIJ', contract_vrijgestelde_lines, 'Belastingvrij')
                continue
            if line.code == 'SR_INPUT_BELASTB' and input_belastbaar_lines:
                _append_breakdown_rows('SR_INPUT_BELASTB', input_belastbaar_lines, 'Belastbaar')
                continue
            if line.code == 'SR_INPUT_VRIJ' and input_vrijgesteld_lines:
                _append_breakdown_rows('SR_INPUT_VRIJ', input_vrijgesteld_lines, 'Belastingvrij')
                continue
            if line.code == 'SR_AFTREK_BV' and contract_aftrek_bv_lines:
                _append_breakdown_rows('SR_AFTREK_BV', contract_aftrek_bv_lines, 'Aftrek belastingvrij', is_credit=True)
                continue
            if line.code == 'SR_PENSIOEN' and contract_inhoudingen:
                _append_breakdown_rows('SR_PENSIOEN', contract_inhoudingen, 'Inhouding', is_credit=True)
                continue
            if line.code == 'SR_INPUT_AFTREK' and input_inhoudingen:
                _append_breakdown_rows('SR_INPUT_AFTREK', input_inhoudingen, 'Inhouding', is_credit=True)
                continue

            line_name = (line_label_map.get(line.code) or line.name or line.salary_rule_id.name or line.code or '').upper()
            debit = total if total > 0 else 0.0
            credit = abs(total) if total < 0 else 0.0
            net_line = debit - credit
            payslip_line_rows.append({
                'code': line.code,
                'name': line_name,
                'categorie_label': _code_categorie_label.get(line.code, ''),
                'quantity': quantity,
                'quantity_display': quantity_display,
                'debit': debit,
                'credit': credit,
                'net': net_line,
            })

            if line.code != 'SR_HK':
                belasting_line_rows.append({
                    'code': line.code,
                    'name': line_name,
                    'quantity_display': quantity_display,
                    'verloond_bedrag': total if not line.code.startswith('SR_LB') and not line.code.startswith('SR_AOV') else 0.0,
                    'loonbelasting': abs(total) if line.code.startswith('SR_LB') else 0.0,
                    'premie_aov': abs(total) if line.code.startswith('SR_AOV') else 0.0,
                })

        display_debit_total = sum(row['debit'] for row in payslip_line_rows)
        display_credit_total = sum(row['credit'] for row in payslip_line_rows)
        display_net_total = display_debit_total - display_credit_total
        belasting_paid_total = sum(row['verloond_bedrag'] for row in belasting_line_rows)
        belasting_tax_total = sum(row['loonbelasting'] for row in belasting_line_rows)
        belasting_aov_total = sum(row['premie_aov'] for row in belasting_line_rows)

        return {
            # Basis
            'periodes': periodes,
            'is_fn': periodes == 26,
            'payslip_layout': self._sr_get_effective_payslip_layout(),
            'payslip_layout_label': self._sr_get_layout_label(),
            'period_title': period_title,
            'fn_period_indicator': fn_period['indicator'] if fn_period else False,
            'fn_period_label': fn_period['label'] if fn_period else False,
            'employee_reference': employee_reference,
            'employment_start_date': employment_start_date,
            'bank_account_number': bank_account_number,
            'bank_name': bank_name,
            'hourly_wage': contract.sr_hourly_wage if contract else 0.0,
            'basic': basic,
            'toelagen': toelagen,
            'kinderbijslag': kinderbijslag,
            'kb_belastbaar': kb_belastbaar,
            'kb_vrijgesteld': kb_vrijgesteld,
            'vrijgesteld_contract': vrijgesteld_contract,
            'heffingskorting': heffingskorting_calc,
            'overwerk': overwerk,
            'vakantie': vakantie,
            'gratificatie': gratificatie,
            'bijz_beloning': bijz_beloning,
            'uitkering_ineens': uitkering_ineens,
            'bruto_per_periode': gross,
            'bruto_totaal': bruto_totaal,
            # Artikel 14 stappen
            'grondslag_belasting_per_periode': r['grondslag_belasting_per_periode'],
            'grondslag_belasting_jaar': r['grondslag_belasting_jaar'],
            'bruto_jaarloon': r['bruto_jaar'],
            'belastingvrij_jaar': r['belastingvrij_jaar'],
            'forfaitaire_pct': r['forfaitaire_pct'] * 100,
            'forfaitaire_per_periode': r['forfaitaire_per_periode'],
            'forfaitaire_jaar': r['forfaitaire_jaar'],
            'forfaitaire_max_per_periode': r['forfaitaire_max_per_periode'],
            'forfaitaire_max_jaar': params.get('forfaitaire_max', 4800),
            'belastbaar_jaarloon': r['belastbaar_jaar'],
            'lb_voor_heffingskorting_jaar': r['lb_voor_heffingskorting_jaar'],
            'lb_voor_heffingskorting_per_periode': r['lb_voor_heffingskorting_per_periode'],
            'heffingskorting_per_periode': r['heffingskorting_per_periode'],
            'heffingskorting_jaar': r['heffingskorting_jaar'],
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
            'adjusted_bruto_per_periode': r['adjusted_bruto_per_periode'],
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
            'earnings_lines': earnings_lines,
            'deductions_lines': deductions_lines,
            'summary_cards': summary_cards,
            'hours_summary_lines': hours_summary_lines,
            'worked_days_rows': worked_days_rows,
            'regular_hours': self.sr_regular_hours,
            'overtime_hours_150': self.sr_overtime_hours_150,
            'overtime_hours_200': self.sr_overtime_hours_200,
            'unpaid_extra_hours': self.sr_unpaid_extra_hours,
            'total_worked_hours': self.sr_total_worked_hours,
            'total_worked_days': self.sr_total_worked_days,
            'payslip_line_rows': payslip_line_rows,
            'belasting_line_rows': belasting_line_rows,
            'display_debit_total': display_debit_total,
            'display_credit_total': display_credit_total,
            'display_net_total': display_net_total,
            'belasting_paid_total': belasting_paid_total,
            'belasting_tax_total': belasting_tax_total,
            'belasting_aov_total': belasting_aov_total,
            'totaal_lb': totaal_lb,
            'totaal_aov': totaal_aov,
            'totaal_inhoudingen': totaal_inhoudingen,
            'netto': netto,
        }

    def action_print_sr_payslip(self):
        """Print de gekozen SR-loonstrooklayout als PDF."""
        self.ensure_one()
        return self.env.ref('l10n_sr_hr_payroll.action_report_payslip_sr').report_action(self, config=False)

    def action_preview_sr_payslip(self):
        """Bekijk de gekozen SR-loonstrooklayout als HTML preview."""
        self.ensure_one()
        return self.env.ref('l10n_sr_hr_payroll.action_report_payslip_sr_preview').report_action(self, config=False)
