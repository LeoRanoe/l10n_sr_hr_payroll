# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date

from odoo.tests import common, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestSrPayrollSecurity(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test SR Security A',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.other_company = cls.env['res.company'].create({
            'name': 'Test SR Security B',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id, cls.other_company.id],
        ))
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Security Werknemer A',
            'company_id': cls.company.id,
        })
        cls.other_employee = cls.env['hr.employee'].create({
            'name': 'Security Werknemer B',
            'company_id': cls.other_company.id,
        })
        cls.contract = cls._create_contract(cls.employee, cls.company)
        cls.other_contract = cls._create_contract(cls.other_employee, cls.other_company)
        cls.line = cls.env['hr.contract.sr.line'].create({
            'contract_id': cls.contract.id,
            'name': 'Security Toelage A',
            'sr_categorie': 'belastbaar',
            'amount': 100.0,
        })
        cls.other_line = cls.env['hr.contract.sr.line'].create({
            'contract_id': cls.other_contract.id,
            'name': 'Security Toelage B',
            'sr_categorie': 'belastbaar',
            'amount': 200.0,
        })

        cls.payroll_user = cls._new_limited_user(
            'sr_security_payroll_user',
            'base.group_user,hr_payroll.group_hr_payroll_user',
        )
        cls.payroll_manager = cls._new_limited_user(
            'sr_security_payroll_manager',
            'base.group_user,hr_payroll.group_hr_payroll_manager',
        )
        cls.accountant_export = cls._new_limited_user(
            'sr_security_accountant_export',
            'base.group_user,l10n_sr_hr_payroll.group_sr_payroll_accountant_export',
        )
        cls.system_user = cls._new_limited_user(
            'sr_security_system',
            'base.group_user,base.group_system',
        )

    @classmethod
    def _create_contract(cls, employee, company):
        return cls.env['hr.contract'].create({
            'name': f'Security Contract {company.name}',
            'employee_id': employee.id,
            'company_id': company.id,
            'structure_type_id': cls.structure_type.id,
            'wage': 5000.0,
            'sr_salary_type': 'monthly',
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    @classmethod
    def _new_limited_user(cls, login, groups):
        user = common.new_test_user(
            cls.env,
            login=login,
            groups=groups,
            company_id=cls.company.id,
        )
        user.write({'company_ids': [(6, 0, [cls.company.id])]})
        return user

    def test_export_menu_groups_have_matching_wizard_acl(self):
        checks = [
            (self.accountant_export, 'sr.payroll.company.year.wizard'),
            (self.accountant_export, 'sr.payroll.verzamelloonstaat.wizard'),
            (self.accountant_export, 'sr.payroll.bank.export.wizard'),
            (self.payroll_manager, 'sr.payroll.annual.statement.wizard'),
            (self.system_user, 'sr.payroll.annual.statement.wizard'),
            (self.system_user, 'sr.payroll.period.wizard'),
            (self.system_user, 'sr.payroll.company.year.wizard'),
            (self.system_user, 'sr.payroll.verzamelloonstaat.wizard'),
            (self.system_user, 'sr.payroll.bank.export.wizard'),
        ]
        for user, model_name in checks:
            model = self.env[model_name].with_user(user)
            self.assertTrue(model.has_access('read'), model_name)
            self.assertTrue(model.has_access('create'), model_name)
            self.assertTrue(model.has_access('write'), model_name)

    def test_tax_report_export_wizard_acl_covers_export_groups(self):
        for user in (self.payroll_user, self.payroll_manager, self.accountant_export, self.system_user):
            model = self.env['sr.payroll.tax.report.export.wizard'].with_user(user)
            self.assertTrue(model.has_access('read'), user.login)
            self.assertTrue(model.has_access('create'), user.login)
            self.assertTrue(model.has_access('write'), user.login)

    def test_accountant_tax_report_stays_readonly(self):
        report_model = self.env['hr.payroll.tax.report'].with_user(self.accountant_export)

        self.assertTrue(report_model.has_access('read'))
        self.assertFalse(report_model.has_access('create'))
        self.assertFalse(report_model.has_access('write'))
        self.assertFalse(report_model.has_access('unlink'))

    def test_contract_sr_lines_follow_allowed_companies(self):
        visible_lines = self.env['hr.contract.sr.line'].with_user(
            self.payroll_user,
        ).with_context(
            allowed_company_ids=[self.company.id],
        ).search([
            ('id', 'in', [self.line.id, self.other_line.id]),
        ])

        self.assertEqual(visible_lines.ids, [self.line.id])
