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

from odoo import models, _


class HrWorkEntryRegenerationWizardSr(models.TransientModel):
    _inherit = 'hr.work.entry.regeneration.wizard'

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
