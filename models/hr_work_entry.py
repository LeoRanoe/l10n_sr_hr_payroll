# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    sr_is_admin = fields.Boolean(
        compute='_compute_sr_is_admin',
        string='Is Beheerder',
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
        records = super().create(vals_list)
        records._sr_classify_overtime()
        return records

    def write(self, vals):
        result = super().write(vals)
        reclassify_fields = {
            'work_entry_type_id', 'date_start', 'date_stop',
            'duration', 'sr_manual_override',
        }
        if reclassify_fields & vals.keys():
            self._sr_classify_overtime()
        return result

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
        overtime_entries = self.filtered(
            lambda e: e.work_entry_type_id.sr_is_overtime and not e.sr_manual_override
        )
        non_ot = self.filtered(
            lambda e: not e.work_entry_type_id.sr_is_overtime and not e.sr_manual_override
        )

        # Wis buckets voor niet-overwerk entries
        if non_ot:
            non_ot._write({'sr_overtime_150': 0.0, 'sr_overtime_200': 0.0})

        if not overtime_entries:
            return

        # Verzamel unieke datums voor feestdagenopzoeking (één DB-query)
        dates = {e.date_start.date() for e in overtime_entries if e.date_start}
        holiday_set = set()
        if dates:
            holidays = self.env['sr.public.holiday'].search([
                ('date', 'in', list(dates)),
                ('active', '=', True),
            ])
            holiday_set = {h.date for h in holidays}

        for entry in overtime_entries:
            hours = entry.duration or 0.0
            if not hours:
                entry._write({'sr_overtime_150': 0.0, 'sr_overtime_200': 0.0})
                continue
            entry_date = entry.date_start.date() if entry.date_start else None
            if entry_date and (entry_date.weekday() == 6 or entry_date in holiday_set):
                entry._write({'sr_overtime_200': hours, 'sr_overtime_150': 0.0})
            else:
                entry._write({'sr_overtime_150': hours, 'sr_overtime_200': 0.0})
