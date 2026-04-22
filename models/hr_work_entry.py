# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    SR_MAX_SINGLE_SHIFT_HOURS = 24.0

    sr_is_admin = fields.Boolean(
        compute='_compute_sr_is_admin',
        string='Is Beheerder',
    )
    sr_contract_allows_overtime = fields.Boolean(
        string='Contract: Overwerkrecht',
        related='contract_id.sr_has_overtime_right',
        store=True,
        readonly=True,
        help='Snapshot van het contractvinkje dat bepaalt of extra uren als belastbaar overwerk mogen doorstromen.',
    )
    sr_planned_hours = fields.Float(
        string='Roosteruren',
        digits=(16, 2),
        compute='_compute_sr_schedule_metrics',
        store=True,
        help='Aantal uren dat volgens het contractrooster binnen dit tijdvak gepland was.',
    )
    sr_extra_hours = fields.Float(
        string='Extra Uren',
        digits=(16, 2),
        compute='_compute_sr_schedule_metrics',
        store=True,
        help='Werkelijke uren boven het rooster voor dit tijdvak. Deze waarde stuurt de SR overtime-classificatie.',
    )
    sr_has_schedule_deviation = fields.Boolean(
        string='Afwijking van Rooster',
        compute='_compute_sr_schedule_metrics',
        store=True,
        help='Geeft aan dat de werkboeking afwijkt van het geplande rooster of handmatig is gecorrigeerd.',
    )
    sr_overtime_treatment = fields.Selection(
        selection=[
            ('none', 'Volgens rooster'),
            ('overtime_150', 'Overwerk 150%'),
            ('overtime_200', 'Overwerk 200%'),
            ('unpaid', 'Extra uren niet uitbetalen'),
            ('manual', 'Handmatige override'),
        ],
        string='SR Classificatie',
        compute='_compute_sr_schedule_metrics',
        store=True,
        help='Administratieve behandeling van de uren voor Suriname Payroll.',
    )
    sr_deviation_note = fields.Char(
        string='SR Toelichting',
        compute='_compute_sr_schedule_metrics',
        store=True,
        help='Korte audit-uitleg waarom deze werkboeking afwijkt of als overwerk is geclassificeerd.',
    )

    # ── Overwerk classificatie-buckets ────────────────────────────────────
    sr_overtime_150 = fields.Float(
        string='Overwerk 150% (u)',
        digits=(16, 2),
        default=0.0,
        store=True,
        help='Geregistreerde overwerkuren op een werkdag (Ma–Za), uitbetaald op 150% van het uurloon.',
    )
    sr_overtime_200 = fields.Float(
        string='Overwerk 200% (u)',
        digits=(16, 2),
        default=0.0,
        store=True,
        help='Geregistreerde overwerkuren op zondag of een wettelijke feestdag, uitbetaald op 200% van het uurloon.',
    )

    # ── Bron en audit ──────────────────────────────────────────────────────
    sr_entry_source = fields.Selection(
        selection=[
            ('manual', 'Handmatig'),
            ('import', 'Import / Prikklok'),
            ('system', 'Systeem'),
        ],
        string='Bron',
        default='manual',
        store=True,
        help='Oorsprong van deze boeking. Wordt ingevuld door importwizard of systeem.',
    )
    sr_import_batch = fields.Char(
        string='Import Batch',
        store=True,
        help='Identificatie van de importbatch waartoe deze boeking behoort (toekomstige importwizard).',
    )
    sr_manual_override = fields.Boolean(
        string='Handmatig Aangepast',
        default=False,
        store=True,
        help='Vink aan om automatische herclassificatie van overwerkbuckets te blokkeren.',
    )

    @api.depends(
        'date_start',
        'date_stop',
        'duration',
        'work_entry_type_id',
        'sr_manual_override',
        'contract_id.sr_has_overtime_right',
        'contract_id.resource_calendar_id',
    )
    def _compute_sr_schedule_metrics(self):
        holiday_dates = self._sr_get_holiday_dates()
        for entry in self:
            actual_hours = entry._sr_get_actual_duration_hours()
            planned_hours = entry._sr_get_planned_hours()
            extra_hours = entry._sr_get_extra_hours(planned_hours=planned_hours, actual_hours=actual_hours)
            has_deviation = entry.sr_manual_override or abs(actual_hours - planned_hours) > 0.01 or extra_hours > 0.01

            if entry.sr_manual_override:
                treatment = 'manual'
                note = _('Handmatige SR-correctie: automatische classificatie is geblokkeerd.')
            elif extra_hours <= 0.01:
                treatment = 'none'
                if planned_hours > actual_hours + 0.01:
                    note = _('Minder uren dan gepland rooster.')
                elif has_deviation:
                    note = _('Afwijking gedetecteerd, maar zonder uitbetaalbaar overwerk.')
                else:
                    note = False
            elif not entry.contract_id.sr_has_overtime_right:
                treatment = 'unpaid'
                note = _('%.2f extra uur buiten rooster; contract zonder overwerkrecht.') % extra_hours
            elif entry._sr_is_200_percent_day(holiday_dates):
                treatment = 'overtime_200'
                note = _('%.2f extra uur geclassificeerd als 200%% (zondag/feestdag).') % extra_hours
            else:
                treatment = 'overtime_150'
                note = _('%.2f extra uur geclassificeerd als 150%% (werkdag).') % extra_hours

            entry.sr_planned_hours = float_round(planned_hours, precision_digits=2)
            entry.sr_extra_hours = float_round(extra_hours, precision_digits=2)
            entry.sr_has_schedule_deviation = has_deviation
            entry.sr_overtime_treatment = treatment
            entry.sr_deviation_note = note

    @api.constrains('date_start', 'date_stop', 'duration', 'contract_id')
    def _check_sr_reasonable_duration(self):
        for entry in self:
            contract = entry.contract_id
            if not contract or not hasattr(contract, '_sr_is_payroll_contract') or not contract._sr_is_payroll_contract():
                continue
            if entry.date_start and entry.date_stop and entry.date_stop <= entry.date_start:
                raise ValidationError('Een werkboeking moet een eindtijd hebben die later ligt dan de starttijd.')
            actual_hours = entry._sr_get_actual_duration_hours()
            if actual_hours > self.SR_MAX_SINGLE_SHIFT_HOURS + 0.01:
                raise ValidationError(
                    'Een SR werkboeking mag niet meer dan 24 uur aaneengesloten bevatten. '
                    'Controleer de prikklok-import of splits de registratie op per werkdag.'
                )

    def _compute_sr_is_admin(self):
        """True als de huidige gebruiker een System Admin is."""
        is_admin = self.env.user.has_group('base.group_system')
        for entry in self:
            entry.sr_is_admin = is_admin

    def action_sr_reset_to_draft(self):
        """
        Admin-actie: zet gevalideerde work entry terug naar 'draft'.

        Alleen beschikbaar voor System Admins. Wordt aangeroepen via de
        'Terug naar Concept (Admin)' knop op het work entry formulier.
        """
        self.ensure_one()
        if not self.env.user.has_group('base.group_system'):
            raise UserError(_("Only System Administrators can reset validated work entries to draft."))
        if self.state != 'validated':
            raise UserError(_("Only validated work entries can be reset to draft."))
        # Bypass the validated-state ORM blockers using sudo
        self.sudo().write({'state': 'draft', 'active': True})

    @api.ondelete(at_uninstall=False)
    def _unlink_except_validated_work_entries(self):
        """
        Override: Allow System Admins to delete validated work entries.

        Base Odoo prevents deletion of validated work entries. This override
        allows System Admins (group 'base.group_system') to bypass this
        restriction for testing and corrective operations.
        """
        if not self.env.user.has_group('base.group_system'):
            validated_entries = self.filtered(lambda w: w.state == 'validated')
            if validated_entries:
                raise UserError(
                    "This work entry is validated. You can't delete it."
                )
        # Admin users bypass the restriction — proceed with deletion

    # ── ORM hooks voor classificatie ──────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._sr_prepare_manual_override_vals(vals) for vals in vals_list]
        records = super().create(vals_list)
        records._sr_classify_overtime()
        return records

    def write(self, vals):
        if self.env.context.get('sr_skip_overtime_reclassify'):
            return super().write(vals)

        vals = self._sr_prepare_manual_override_vals(vals)
        result = super().write(vals)
        reclassify_fields = {
            'work_entry_type_id', 'date_start', 'date_stop',
            'duration', 'sr_manual_override', 'contract_id', 'employee_id', 'state',
        }
        if reclassify_fields & vals.keys():
            self._sr_classify_overtime()
        return result

    def _sr_prepare_manual_override_vals(self, vals):
        vals = dict(vals)
        if {'sr_overtime_150', 'sr_overtime_200'} & vals.keys() and 'sr_manual_override' not in vals:
            vals['sr_manual_override'] = True
        return vals

    def _sr_get_holiday_dates(self):
        dates = {entry.date_start.date() for entry in self if entry.date_start}
        if not dates:
            return set()
        holidays = self.env['sr.public.holiday'].search([
            ('date', 'in', list(dates)),
            ('active', '=', True),
        ])
        return {holiday.date for holiday in holidays}

    def _sr_get_actual_duration_hours(self):
        self.ensure_one()
        date_diff_hours = 0.0
        if self.date_start and self.date_stop:
            date_diff_hours = max((self.date_stop - self.date_start).total_seconds() / 3600.0, 0.0)
        return max(self.duration or 0.0, date_diff_hours)

    def _sr_get_schedule_calendar(self):
        self.ensure_one()
        return self.contract_id.resource_calendar_id

    def _sr_get_planned_hours(self):
        self.ensure_one()
        actual_hours = self._sr_get_actual_duration_hours()
        if actual_hours <= 0 or not self.date_start or not self.date_stop:
            return 0.0

        calendar = self._sr_get_schedule_calendar()
        if calendar:
            return max(calendar.get_work_hours_count(self.date_start, self.date_stop, compute_leaves=False), 0.0)

        weekday = self.date_start.weekday()
        default_day_hours = 8.0 if weekday < 6 else 0.0
        return min(actual_hours, default_day_hours)

    def _sr_get_extra_hours(self, planned_hours=None, actual_hours=None):
        self.ensure_one()
        actual_hours = self._sr_get_actual_duration_hours() if actual_hours is None else actual_hours
        planned_hours = self._sr_get_planned_hours() if planned_hours is None else planned_hours
        if self.work_entry_type_id.sr_is_overtime:
            return actual_hours
        return max(actual_hours - planned_hours, 0.0)

    def _sr_is_200_percent_day(self, holiday_dates=None):
        self.ensure_one()
        if not self.date_start:
            return False
        entry_date = self.date_start.date()
        holiday_dates = holiday_dates or set()
        return entry_date.weekday() == 6 or entry_date in holiday_dates

    @api.model
    def sr_prepare_clock_entry_vals(
        self,
        contract,
        check_in,
        check_out,
        work_entry_type=None,
        source='import',
        batch=None,
        manual_override=False,
        **extra_vals,
    ):
        """
        Centrale helper voor toekomstige CSV/prikklok-imports.

        Map check-in/check-out rechtstreeks naar een create()-payload voor
        hr.work.entry, zodat alle SR-classificatie via dezelfde engine loopt.
        """
        contract = contract if hasattr(contract, 'id') else self.env['hr.contract'].browse(contract)
        if not contract or not contract.exists():
            raise UserError(_('Geen geldig contract ontvangen voor de prikklok-import.'))
        if not check_in or not check_out or check_out <= check_in:
            raise UserError(_('Check-out moet later zijn dan check-in voor een geldige werkboeking.'))

        work_entry_type = work_entry_type if hasattr(work_entry_type, 'id') else self.env['hr.work.entry.type'].browse(work_entry_type)
        if not work_entry_type:
            work_entry_type = self.env.ref('hr_work_entry.work_entry_type_attendance', raise_if_not_found=False)
        if not work_entry_type:
            work_entry_type = self.env['hr.work.entry.type'].search([], limit=1)
        if not work_entry_type:
            raise UserError(_('Geen standaard work entry type beschikbaar voor de prikklok-import.'))

        duration = max((check_out - check_in).total_seconds() / 3600.0, 0.0)
        if duration > self.SR_MAX_SINGLE_SHIFT_HOURS + 0.01:
            raise UserError(_('Een prikklok-importregel mag niet meer dan 24 uur aaneengesloten bevatten.'))
        vals = {
            'name': extra_vals.pop('name', _('Prikklok %s %s') % (contract.employee_id.name, check_in.strftime('%Y-%m-%d %H:%M'))),
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'company_id': contract.company_id.id,
            'work_entry_type_id': work_entry_type.id,
            'date_start': check_in,
            'date_stop': check_out,
            'duration': duration,
            'sr_entry_source': source,
            'sr_import_batch': batch,
            'sr_manual_override': manual_override,
        }
        vals.update(extra_vals)
        return vals

    # ── Classificatie-engine ──────────────────────────────────────────────

    def _sr_classify_overtime(self):
        """
        Classificeer overwerkbuckets op basis van dag-type:
          - Zondag of Surinaamse feestdag  → sr_overtime_200 = duration
          - Overige werkdagen (Ma–Za)      → sr_overtime_150 = duration
          - Geen overtijdtype              → beide buckets op 0,0

        Regels met sr_manual_override=True worden overgeslagen.
        De classificatie gebruikt _write() om write()-recursie te vermijden.
        """
        if not self:
            return

        holiday_dates = self._sr_get_holiday_dates()
        entries = self.filtered(lambda entry: not entry.sr_manual_override)

        for entry in entries:
            actual_hours = entry._sr_get_actual_duration_hours()
            extra_hours = entry._sr_get_extra_hours(actual_hours=actual_hours)
            overtime_hours = 0.0

            if actual_hours > 0 and entry.contract_id.sr_has_overtime_right:
                if entry.work_entry_type_id.sr_is_overtime:
                    overtime_hours = actual_hours
                else:
                    overtime_hours = extra_hours

            if overtime_hours <= 0.01:
                entry.with_context(sr_skip_overtime_reclassify=True).write({
                    'sr_overtime_150': 0.0,
                    'sr_overtime_200': 0.0,
                })
                continue

            if entry._sr_is_200_percent_day(holiday_dates):
                entry.with_context(sr_skip_overtime_reclassify=True).write({
                    'sr_overtime_200': overtime_hours,
                    'sr_overtime_150': 0.0,
                })
            else:
                entry.with_context(sr_skip_overtime_reclassify=True).write({
                    'sr_overtime_150': overtime_hours,
                    'sr_overtime_200': 0.0,
                })
