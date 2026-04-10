# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models
from odoo.exceptions import UserError


class HrWorkEntry(models.Model):
    _inherit = 'hr.work.entry'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_validated_work_entries(self):
        """
        Override: Allow System Admins to delete validated work entries.
        
        Base Odoo prevents deletion of validated work entries. This override
        allows System Admins (group 'base.group_system') to bypass this
        restriction for testing and corrective operations.
        """
        # Check if user is System Admin
        is_admin = self.env.user.has_group('base.group_system')
        
        if not is_admin:
            # Only enforce restriction for non-admin users
            # Call parent logic to check for non-admin validations
            validated_entries = self.filtered(lambda w: w.state == 'validated')
            if validated_entries:
                raise UserError(
                    "This work entry is validated. You can't delete it."
                )
        # Admin users bypass the restriction - proceed with deletion
