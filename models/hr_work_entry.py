# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    sr_is_admin = fields.Boolean(
        compute='_compute_sr_is_admin',
        string='Is Beheerder',
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
