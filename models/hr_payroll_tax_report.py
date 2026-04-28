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

    # ── Artikel-niveau LB uitsplitsing ────────────────────────────────────────
    amount_lb_art14_srd = fields.Float(
        string='LB Art. 14 (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Loonbelasting regulier periodiek loon — Artikel 14 WLB',
    )
    amount_lb_bijz_srd = fields.Float(
        string='LB Art. 17 (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Loonbelasting bijzondere beloningen — Artikel 17 WLB',
    )
    amount_lb_17a_srd = fields.Float(
        string='LB Art. 17a (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Loonbelasting uitkering ineens — Artikel 17a WLB',
    )
    amount_lb_overwerk_srd = fields.Float(
        string='LB Art. 17c (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Loonbelasting overwerk — Artikel 17c WLB',
    )
    # ── Artikel-niveau AOV uitsplitsing ───────────────────────────────────────
    amount_aov_art14_srd = fields.Float(
        string='AOV Art. 14 (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='AOV premie regulier periodiek loon',
    )
    amount_aov_bijz_srd = fields.Float(
        string='AOV Art. 17 (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='AOV premie bijzondere beloningen',
    )
    amount_aov_17a_srd = fields.Float(
        string='AOV Art. 17a (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='AOV premie uitkering ineens',
    )
    amount_aov_overwerk_srd = fields.Float(
        string='AOV Art. 17c (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='AOV premie overwerk',
    )
    # ── Extra bruto uitsplitsing ──────────────────────────────────────────────
    amount_bijz_bruto_srd = fields.Float(
        string='Bijz. Beloningen Bruto (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Bruto bijzondere beloningen (vakantiegeld, gratificatie, overige bijz.)',
    )
    amount_uitk_ineens_srd = fields.Float(
        string='Uitkering Ineens (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Bruto uitkering ineens (Art. 17a WLB)',
    )
    # ── Kortingen en inhoudingen ──────────────────────────────────────────────
    amount_heffingskorting_srd = fields.Float(
        string='Heffingskorting (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Toegepaste heffingskorting (belastingvermindering toegepast op werknemer)',
    )
    amount_pensioen_srd = fields.Float(
        string='Andere inhoudingen (SRD)', digits=(16, 2), readonly=True, aggregator='sum',
        help='Geaggregeerde netto inhoudingen uit contract en payslip per periode',
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
            WITH valid_payslips AS (
                SELECT hp.id
                FROM hr_payslip hp
                WHERE hp.sr_is_sr_struct IS TRUE
                  AND hp.state IN ('done', 'paid')
            ),
            line_totals AS (
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
                        THEN hpl.total ELSE 0 END) AS amount_netto_srd,
                    SUM(CASE WHEN hpl.code = 'SR_LB'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_lb_art14_srd,
                    SUM(CASE WHEN hpl.code = 'SR_LB_BIJZ'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_lb_bijz_srd,
                    SUM(CASE WHEN hpl.code = 'SR_LB_17A'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_lb_17a_srd,
                    SUM(CASE WHEN hpl.code = 'SR_LB_OVERWERK'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_lb_overwerk_srd,
                    SUM(CASE WHEN hpl.code = 'SR_AOV'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_aov_art14_srd,
                    SUM(CASE WHEN hpl.code = 'SR_AOV_BIJZ'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_aov_bijz_srd,
                    SUM(CASE WHEN hpl.code = 'SR_AOV_17A'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_aov_17a_srd,
                    SUM(CASE WHEN hpl.code = 'SR_AOV_OVERWERK'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_aov_overwerk_srd,
                    SUM(CASE WHEN hpl.code IN ('SR_VAKANTIE', 'SR_GRAT', 'SR_BIJZ')
                        THEN hpl.total ELSE 0 END) AS amount_bijz_bruto_srd,
                    SUM(CASE WHEN hpl.code = 'SR_UITK_INEENS'
                        THEN hpl.total ELSE 0 END) AS amount_uitk_ineens_srd,
                    SUM(CASE WHEN hpl.code = 'SR_HK'
                        THEN hpl.total ELSE 0 END) AS amount_heffingskorting_srd,
                    SUM(CASE WHEN hpl.code = 'SR_PENSIOEN'
                        THEN ABS(hpl.total) ELSE 0 END) AS amount_pensioen_srd
                FROM hr_payslip_line hpl
                JOIN valid_payslips vp ON vp.id = hpl.slip_id
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
                JOIN valid_payslips vp ON vp.id = hpi.payslip_id
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
                COALESCE(lt.amount_lb_art14_srd, 0.0) AS amount_lb_art14_srd,
                COALESCE(lt.amount_lb_bijz_srd, 0.0) AS amount_lb_bijz_srd,
                COALESCE(lt.amount_lb_17a_srd, 0.0) AS amount_lb_17a_srd,
                COALESCE(lt.amount_lb_overwerk_srd, 0.0) AS amount_lb_overwerk_srd,
                COALESCE(lt.amount_aov_art14_srd, 0.0) AS amount_aov_art14_srd,
                COALESCE(lt.amount_aov_bijz_srd, 0.0) AS amount_aov_bijz_srd,
                COALESCE(lt.amount_aov_17a_srd, 0.0) AS amount_aov_17a_srd,
                COALESCE(lt.amount_aov_overwerk_srd, 0.0) AS amount_aov_overwerk_srd,
                COALESCE(lt.amount_bijz_bruto_srd, 0.0) AS amount_bijz_bruto_srd,
                COALESCE(lt.amount_uitk_ineens_srd, 0.0) AS amount_uitk_ineens_srd,
                COALESCE(lt.amount_heffingskorting_srd, 0.0) AS amount_heffingskorting_srd,
                COALESCE(lt.amount_pensioen_srd, 0.0) AS amount_pensioen_srd,
                hp.state AS payslip_state
                        FROM valid_payslips vp
                        JOIN hr_payslip hp ON hp.id = vp.id
            JOIN hr_employee he ON he.id = hp.employee_id
            LEFT JOIN hr_department hd ON hd.id = he.department_id
            LEFT JOIN line_totals lt ON lt.payslip_id = hp.id
            LEFT JOIN input_totals it ON it.payslip_id = hp.id
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

    # ── Fiscaal Overzicht lijst-PDF ───────────────────────────────────────────

    def get_pdf_overview_data(self):
        """Return grouped data dict for the Fiscaal Overzicht list PDF.

        Called from the QWeb template with ``docs.get_pdf_overview_data()``.
        ``docs`` is the full recordset selected in the list view.
        """
        _AMOUNT_FIELDS = [
            'amount_bruto_srd', 'amount_bijz_bruto_srd',
            'amount_lb_art14_srd', 'amount_lb_bijz_srd',
            'amount_lb_17a_srd', 'amount_lb_overwerk_srd', 'amount_lb_srd',
            'amount_aov_srd',
            'amount_heffingskorting_srd', 'amount_pensioen_srd',
            'amount_netto_srd',
        ]

        dept_map = {}
        for rec in self:
            dept_id = rec.department_id.id or 0
            dept_name = rec.department_name or _('Geen Afdeling')
            if dept_id not in dept_map:
                dept_map[dept_id] = {
                    'dept_name': dept_name,
                    'employees': [],
                    'totals': {f: 0.0 for f in _AMOUNT_FIELDS},
                }
            emp_row = {'employee_name': rec.employee_name or '-'}
            for f in _AMOUNT_FIELDS:
                v = getattr(rec, f, 0.0) or 0.0
                emp_row[f] = v
                dept_map[dept_id]['totals'][f] += v
            dept_map[dept_id]['employees'].append(emp_row)

        dept_groups = sorted(dept_map.values(), key=lambda d: d['dept_name'])
        grand_totals = {f: sum(d['totals'][f] for d in dept_groups) for f in _AMOUNT_FIELDS}

        # Date range from the selection
        dates = self.mapped('date_from')
        dates_to = self.mapped('date_to')
        date_from = min(dates) if dates else False
        date_to = max(dates_to) if dates_to else False

        return {
            'dept_groups': dept_groups,
            'grand_totals': grand_totals,
            'employee_count': len(set(self.mapped('employee_id').ids)),
            'date_from': date_from,
            'date_to': date_to,
            'generated_on': fields.Date.context_today(self),
        }

    def action_print_pdf_overview(self):
        return self.env.ref(
            'l10n_sr_hr_payroll.action_report_sr_fiscal_overview_pdf'
        ).report_action(self, config=False)
