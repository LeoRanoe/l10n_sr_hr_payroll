# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Override van de Work Entry Regeneration Wizard voor Suriname Payroll.

Staat System Admins toe om work entries opnieuw te genereren ook als er
gevalideerde entries in het geselecteerde tijdvak bestaan.

Standaard Odoo blokkeert regeneratie als:
  1. De 'valid' berekening False is (gevalideerde entries aanwezig) →
     de Regenereer-knop is verborgen in de wizard
  2. In regenerate_work_entries() → ValidationError als not self.valid

Deze override:
  - Overschrijft _compute_valid: admin is altijd 'valid'
  - Overschrijft regenerate_work_entries: verwijder eerst gevalideerde
    entries (toegestaan door hr_work_entry.py override) daarna normale flow
"""

from odoo import api, models, _
from odoo import fields
from datetime import timedelta


class HrWorkEntryRegenerationWizardSr(models.TransientModel):
    _inherit = 'hr.work.entry.regeneration.wizard'

    @api.depends('date_from', 'date_to', 'employee_ids')
    def _compute_validated_work_entry_ids(self):
        """
        Treat overlapping validated entries as in-range blockers as well.

        The base wizard only lists validated entries fully contained inside the
        selected range. That misses night shifts or boundary entries that cross
        into the interval and should still block or be cleaned up on regen.
        """
        for wizard in self:
            validated_work_entry_ids = self.env['hr.work.entry']
            if wizard.search_criteria_completed:
                range_start = fields.Datetime.to_datetime(wizard.date_from)
                range_stop = fields.Datetime.to_datetime(wizard.date_to) + timedelta(days=1)
                search_domain = [
                    ('employee_id', 'in', wizard.employee_ids.ids),
                    ('date_start', '<', range_stop),
                    ('date_stop', '>', range_start),
                    ('state', '=', 'validated'),
                ]
                validated_work_entry_ids = self.env['hr.work.entry'].search(search_domain, order='date_start')
            wizard.validated_work_entry_ids = validated_work_entry_ids

    def _compute_valid(self):
        """
        Override: System Admins zijn altijd geldig en kunnen gevalideerde
        entries overschrijven. Roep super() aan voor niet-admins.
        """
        super()._compute_valid()
        if self.env.user.has_group('base.group_system'):
            for wizard in self:
                if wizard.search_criteria_completed:
                    # Admin mag altijd regenereren
                    wizard.valid = True

    def regenerate_work_entries(self):
        """
        Override: Als admin en er zijn gevalideerde entries aanwezig in
        het tijdvak, verwijder die eerst zodat regeneratie schoon start.

        De hr_work_entry.py override staat verwijdering toe voor admins.
        """
        if (self.env.user.has_group('base.group_system')
                and self.validated_work_entry_ids):
            # Verwijder gevalideerde entries (toegestaan voor admin)
            self.validated_work_entry_ids.sudo().unlink()
        return super().regenerate_work_entries()
