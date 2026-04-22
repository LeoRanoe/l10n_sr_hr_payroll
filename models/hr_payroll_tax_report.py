# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""SR Fiscaal Belastingoverzicht als live PostgreSQL view."""

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError


class HrPayrollTaxReport(models.Model):
    _name = 'hr.payroll.tax.report'
    _description = 'SR Fiscaal Belastingoverzicht'
    _auto = False
    _order = 'date_from desc, department_name, employee_name'
    _rec_name = 'employee_name'

    payslip_id = fields.Many2one('hr.payslip', string='Loonstrook', readonly=True)
    employee_id = fields.Many2one('hr.employee', string='Werknemer', readonly=True)
    employee_name = fields.Char(string='Naam Werknemer', readonly=True)
    employee_identification_id = fields.Char(string='ID-nummer', readonly=True)
    department_id = fields.Many2one('hr.department', string='Afdeling', readonly=True)
    department_name = fields.Char(string='Afdeling (naam)', readonly=True)
    payslip_run_id = fields.Many2one('hr.payslip.run', string='Loonrun', readonly=True)
    company_id = fields.Many2one('res.company', string='Bedrijf', readonly=True)
    date_from = fields.Date(string='Periode Van', readonly=True)
    date_to = fields.Date(string='Periode T/m', readonly=True)
    contract_currency_id = fields.Many2one('res.currency', string='Contract Valuta', readonly=True)
    exchange_rate = fields.Float(
        string='Wisselkoers (→ SRD)',
        digits=(16, 6),
        readonly=True,
    )
    amount_bruto_srd = fields.Float(
        string='Bruto Loon (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_overwerk_150_srd = fields.Float(
        string='Overwerk 150% (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_overwerk_200_srd = fields.Float(
        string='Overwerk 200% (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_aov_srd = fields.Float(
        string='AOV Inhouding (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_belastingvrij_periode_srd = fields.Float(
        string='Belastingvrije Voet/Periode (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_lb_srd = fields.Float(
        string='Ingehouden LB (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_akb_srd = fields.Float(
        string='AKB / Kinderbijslag (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_netto_srd = fields.Float(
        string='Netto Loon (SRD)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    amount_netto_bronvaluta = fields.Float(
        string='Netto Loon (Bronvaluta)',
        digits=(16, 2),
        readonly=True,
        aggregator='sum',
    )
    payslip_state = fields.Selection(
        selection=[
            ('draft', 'Concept'),
            ('verify', 'Te Controleren'),
            ('done', 'Bevestigd'),
            ('paid', 'Betaald'),
        ],
        string='Status Loonstrook',
        readonly=True,
    )

    def _raise_readonly_view_error(self):
        raise UserError(_(
            'Het fiscaal overzicht is een auditrapport op basis van een SQL-view en kan niet rechtstreeks worden aangemaakt, gewijzigd of verwijderd. Pas de onderliggende loonstrook aan als correctie nodig is.'
        ))

    @api.model_create_multi
    def create(self, vals_list):
        self._raise_readonly_view_error()

    def write(self, vals):
        self._raise_readonly_view_error()

    def unlink(self):
        self._raise_readonly_view_error()

    def _query(self):
        return """
            WITH line_totals AS (
                SELECT
                    hpl.slip_id AS payslip_id,
                    SUM(CASE WHEN hpl.code IN (
                        'BASIC',
                        'SR_ALW',
                        'SR_KB_BELAST',
                        'SR_KB_VRIJ',
                        'SR_KINDBIJ',
                        'SR_INPUT_BELASTB',
                        'SR_INPUT_VRIJ',
                        'SR_OVERWERK',
                        'SR_VAKANTIE',
                        'SR_GRAT',
                        'SR_BIJZ',
                        'SR_UITK_INEENS'
                    ) THEN hpl.total ELSE 0 END) AS amount_bruto_srd,
                    SUM(CASE WHEN hpl.code IN ('SR_AOV', 'SR_AOV_BIJZ', 'SR_AOV_17A', 'SR_AOV_OVERWERK')
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_aov_srd,
                    SUM(CASE WHEN hpl.code IN ('SR_LB', 'SR_LB_BIJZ', 'SR_LB_17A', 'SR_LB_OVERWERK')
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_lb_srd,
                    SUM(CASE WHEN hpl.code IN ('SR_KB_BELAST', 'SR_KB_VRIJ')
                        THEN hpl.total ELSE 0 END) AS amount_akb_srd,
                    SUM(CASE WHEN hpl.code = 'NET'
                        THEN hpl.total ELSE 0 END) AS amount_netto_srd
                FROM hr_payslip_line hpl
                GROUP BY hpl.slip_id
            ),
            input_totals AS (
                SELECT
                    hpi.payslip_id AS payslip_id,
                    SUM(CASE WHEN hpit.code = 'SR_IN_OVERWERK_150'
                        THEN hpi.amount ELSE 0 END) AS amount_overwerk_150_srd,
                    SUM(CASE WHEN hpit.code = 'SR_IN_OVERWERK_200'
                        THEN hpi.amount ELSE 0 END) AS amount_overwerk_200_srd
                FROM hr_payslip_input hpi
                JOIN hr_payslip_input_type hpit ON hpit.id = hpi.input_type_id
                GROUP BY hpi.payslip_id
            )
            SELECT
                hp.id AS id,
                hp.id AS payslip_id,
                hp.employee_id AS employee_id,
                he.name AS employee_name,
                COALESCE(he.identification_id, '') AS employee_identification_id,
                he.department_id AS department_id,
                COALESCE(hd.name->>'en_US', hd.name->>'nl_NL', '') AS department_name,
                hp.payslip_run_id AS payslip_run_id,
                hp.company_id AS company_id,
                hp.date_from AS date_from,
                hp.date_to AS date_to,
                hp.sr_frozen_contract_currency_id AS contract_currency_id,
                COALESCE(hp.sr_exchange_rate, hp.sr_frozen_exchange_rate, 1.0) AS exchange_rate,
                COALESCE(lt.amount_bruto_srd, 0.0) AS amount_bruto_srd,
                COALESCE(it.amount_overwerk_150_srd, 0.0) AS amount_overwerk_150_srd,
                COALESCE(it.amount_overwerk_200_srd, 0.0) AS amount_overwerk_200_srd,
                COALESCE(lt.amount_aov_srd, 0.0) AS amount_aov_srd,
                COALESCE(hp.sr_belastingvrij_periode_srd, 0.0) AS amount_belastingvrij_periode_srd,
                COALESCE(lt.amount_lb_srd, 0.0) AS amount_lb_srd,
                COALESCE(lt.amount_akb_srd, 0.0) AS amount_akb_srd,
                COALESCE(lt.amount_netto_srd, 0.0) AS amount_netto_srd,
                COALESCE(hp.sr_netto_bronvaluta, lt.amount_netto_srd, 0.0) AS amount_netto_bronvaluta,
                hp.state AS payslip_state
            FROM hr_payslip hp
            JOIN hr_employee he ON he.id = hp.employee_id
            LEFT JOIN hr_department hd ON hd.id = he.department_id
            LEFT JOIN line_totals lt ON lt.payslip_id = hp.id
            LEFT JOIN input_totals it ON it.payslip_id = hp.id
            WHERE hp.sr_is_sr_struct IS TRUE
              AND hp.state IN ('done', 'paid')
        """

    def init(self):
        self.env.cr.execute(
            """
            SELECT c.relkind
              FROM pg_class c
             WHERE c.relname = %s
               AND c.relkind IN ('r', 'v', 'm', 'p')
            """,
            [self._table],
        )
        relation = self.env.cr.fetchone()
        if relation:
            relation_kind = relation[0]
            if relation_kind in ('r', 'p'):
                self.env.cr.execute(f'DROP TABLE IF EXISTS {self._table} CASCADE')
            elif relation_kind in ('v', 'm'):
                self.env.cr.execute(f'DROP VIEW IF EXISTS {self._table} CASCADE')
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""CREATE OR REPLACE VIEW %s AS (%s)""" % (self._table, self._query()))
