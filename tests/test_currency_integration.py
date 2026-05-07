# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Integratietests voor volledige valuta-ondersteuning in hr.contract.sr.line.

Verifieert dat:
  - SRD-lijnen geen conversie ondergaan (backward compatible)
  - USD/EUR-lijnen correct naar SRD worden omgerekend via exchange_rate
  - Gemengde valuta (SRD + USD op één contract) correct optellen
  - Standaard contractvaluta vanuit bedrijfsinstellingen correct doorstroomt naar nieuw contract
  - Preview-velden (sr_preview_bruto/netto) kloppen bij USD/EUR-lijnen
  - Payslip-berekening klopt bij USD-lijnen met bevroren wisselkoers
  - Percentage-regels onaangetast blijven (percentage over basisloon, altijd SRD)
  - Constraint blokkeert incompatibele lijn-valuta (bv. EUR op USD-contract)
  - init()-migratie stelt SRD in voor bestaande NULL-records (simulatie)
"""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from odoo.exceptions import ValidationError
from odoo.tests import common, tagged


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestCurrencyIntegration(common.TransactionCase):
    """Valuta-integratie tests voor sr_vaste_regels."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['res.company'].create({
            'name': 'Test Bedrijf Valuta Integratie',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))

        cls.srd = cls.env.ref('base.SRD')
        cls.usd = cls.env.ref('base.USD')
        cls.eur = cls.env.ref('base.EUR')

        # Stel vaste wisselkoersen in op het testbedrijf
        cls.company.write({
            'sr_exchange_rate_usd': 36.5,
            'sr_exchange_rate_eur': 39.0,
            'sr_default_contract_currency_id': cls.srd.id,
        })

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Werknemer Valuta',
            'company_id': cls.company.id,
        })

        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

    def _create_contract(self, wage, contract_currency=None, salary_type='monthly',
                         vaste_regels=None, employee=None):
        """Maak een test contract aan met optionele vaste regels."""
        emp = employee or self.employee
        existing = self.env['hr.contract'].search([
            ('employee_id', '=', emp.id),
            ('state', 'in', ('open', 'pending')),
        ])
        if existing:
            existing.write({'state': 'cancel'})

        currency_id = (contract_currency or self.srd).id
        return self.env['hr.contract'].create({
            'name': 'Test Contract Valuta',
            'employee_id': emp.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_contract_currency': currency_id,
            'sr_vaste_regels': vaste_regels or [],
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    def _compute_payslip(self, contract):
        """Bereken een loonstrook voor mei 2026."""
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Loonstrook Valuta Mei 2026',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        return payslip

    def _line_total(self, payslip, code):
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return line.total if line else 0.0

    def _assertclose(self, val, expected, msg='', tol=0.05):
        self.assertAlmostEqual(
            val, expected,
            delta=tol,
            msg=f'{msg} — verwacht {expected:.2f}, kreeg {val:.2f}',
        )

    # ──────────────────────────────────────────────────────────────────────
    # 1. SRD contract — geen conversie (backward compatible)
    # ──────────────────────────────────────────────────────────────────────

    def test_srd_contract_line_no_conversion(self):
        """SRD-contract met SRD-lijnen: bedrag ongewijzigd in berekening."""
        contract = self._create_contract(
            wage=10000.0,
            contract_currency=self.srd,
            vaste_regels=[(0, 0, {
                'name': 'Olie Toelage',
                'sr_categorie': 'belastbaar',
                'amount_type': 'fixed',
                'amount': 500.0,
                'line_currency_id': self.srd.id,
            })],
        )
        # _sr_resolve_regels moet exact 500 SRD teruggeven
        belastbaar = contract._sr_resolve_regels('belastbaar', exchange_rate=1.0)
        self.assertAlmostEqual(belastbaar, 500.0, delta=0.01,
                               msg='SRD-lijn moet zonder conversie 500.00 SRD zijn')

    # ──────────────────────────────────────────────────────────────────────
    # 2. USD-contract met USD-lijn — converteert correct naar SRD
    # ──────────────────────────────────────────────────────────────────────

    def test_usd_contract_line_in_usd_converts_to_srd(self):
        """USD-lijn van 100 USD × 36.5 = 3650 SRD."""
        rate = 36.5
        contract = self._create_contract(
            wage=500.0,
            contract_currency=self.usd,
            vaste_regels=[(0, 0, {
                'name': 'Olie Toelage USD',
                'sr_categorie': 'belastbaar',
                'amount_type': 'fixed',
                'amount': 100.0,
                'line_currency_id': self.usd.id,
            })],
        )
        belastbaar = contract._sr_resolve_regels('belastbaar', exchange_rate=rate)
        expected = float(
            (Decimal('100.00') * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )
        self._assertclose(belastbaar, expected,
                          msg='USD-lijn moet naar SRD geconverteerd worden')

    # ──────────────────────────────────────────────────────────────────────
    # 3. EUR-contract met EUR-lijn — converteert correct naar SRD
    # ──────────────────────────────────────────────────────────────────────

    def test_eur_contract_line_in_eur_converts_to_srd(self):
        """EUR-lijn van 200 EUR × 39.0 = 7800 SRD."""
        rate = 39.0
        contract = self._create_contract(
            wage=600.0,
            contract_currency=self.eur,
            vaste_regels=[(0, 0, {
                'name': 'Representatie EUR',
                'sr_categorie': 'belastbaar',
                'amount_type': 'fixed',
                'amount': 200.0,
                'line_currency_id': self.eur.id,
            })],
        )
        belastbaar = contract._sr_resolve_regels('belastbaar', exchange_rate=rate)
        expected = float(
            (Decimal('200.00') * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )
        self._assertclose(belastbaar, expected,
                          msg='EUR-lijn moet naar SRD geconverteerd worden')

    # ──────────────────────────────────────────────────────────────────────
    # 4. USD-contract met SRD-lijn — geen conversie (migratie-scenario)
    # ──────────────────────────────────────────────────────────────────────

    def test_usd_contract_srd_line_no_conversion(self):
        """USD-contract maar lijn expliciet in SRD: geen conversie (backward compat)."""
        rate = 36.5
        contract = self._create_contract(
            wage=500.0,
            contract_currency=self.usd,
            vaste_regels=[(0, 0, {
                'name': 'Transport SRD',
                'sr_categorie': 'vrijgesteld',
                'amount_type': 'fixed',
                'amount': 300.0,
                'line_currency_id': self.srd.id,
            })],
        )
        vrijgesteld = contract._sr_resolve_regels('vrijgesteld', exchange_rate=rate)
        self._assertclose(vrijgesteld, 300.0,
                          msg='SRD-lijn op USD-contract mag niet geconverteerd worden')

    # ──────────────────────────────────────────────────────────────────────
    # 5. Gemengde valuta op één USD-contract
    # ──────────────────────────────────────────────────────────────────────

    def test_mixed_currencies_on_usd_contract(self):
        """USD-lijn (100 USD) + SRD-lijn (500 SRD) → totaal 3650 + 500 = 4150 SRD."""
        rate = 36.5
        contract = self._create_contract(
            wage=500.0,
            contract_currency=self.usd,
            vaste_regels=[
                (0, 0, {
                    'name': 'Olie Toelage USD',
                    'sr_categorie': 'belastbaar',
                    'amount_type': 'fixed',
                    'amount': 100.0,
                    'line_currency_id': self.usd.id,
                }),
                (0, 0, {
                    'name': 'Kleding Toelage SRD',
                    'sr_categorie': 'belastbaar',
                    'amount_type': 'fixed',
                    'amount': 500.0,
                    'line_currency_id': self.srd.id,
                }),
            ],
        )
        belastbaar = contract._sr_resolve_regels('belastbaar', exchange_rate=rate)
        usd_in_srd = float(
            (Decimal('100.00') * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )
        expected = usd_in_srd + 500.0
        self._assertclose(belastbaar, expected,
                          msg='Gemengde USD+SRD lijnen moeten correct optellen')

    # ──────────────────────────────────────────────────────────────────────
    # 6. Standaard contractvaluta vanuit bedrijfsinstellingen
    # ──────────────────────────────────────────────────────────────────────

    def test_default_currency_from_company_settings(self):
        """Nieuw contract neemt standaard contractvaluta uit bedrijfsinstellingen."""
        # Stel bedrijfsstandaard in op USD
        self.company.write({'sr_default_contract_currency_id': self.usd.id})
        try:
            emp_b = self.env['hr.employee'].create({
                'name': 'Test Werknemer Default Valuta',
                'company_id': self.company.id,
            })
            contract = self.env['hr.contract'].create({
                'name': 'Test Default Valuta Contract',
                'employee_id': emp_b.id,
                'company_id': self.company.id,
                'structure_type_id': self.structure_type.id,
                'wage': 1000.0,
                'date_start': date(2026, 1, 1),
                'state': 'open',
            })
            self.assertEqual(
                contract.sr_contract_currency, self.usd,
                'Nieuw contract moet standaard contractvaluta USD overnemen',
            )
        finally:
            self.company.write({'sr_default_contract_currency_id': self.srd.id})

    # ──────────────────────────────────────────────────────────────────────
    # 7. Preview-velden kloppen bij USD-lijnen
    # ──────────────────────────────────────────────────────────────────────

    def test_preview_with_usd_lines(self):
        """sr_preview_bruto bevat wage_srd + USD-lijn omgerekend naar SRD."""
        rate = 36.5
        wage_usd = 500.0
        toelage_usd = 100.0
        wage_srd = round(wage_usd * rate, 2)
        toelage_srd = float(
            (Decimal(str(toelage_usd)) * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )
        contract = self._create_contract(
            wage=wage_usd,
            contract_currency=self.usd,
            vaste_regels=[(0, 0, {
                'name': 'Olie Toelage USD',
                'sr_categorie': 'belastbaar',
                'amount_type': 'fixed',
                'amount': toelage_usd,
                'line_currency_id': self.usd.id,
            })],
        )
        # sr_preview_bruto = wage_srd + alle toelagen (SRD-equivalent)
        expected_bruto = wage_srd + toelage_srd
        self._assertclose(
            contract.sr_preview_bruto, expected_bruto, tol=1.0,
            msg='Preview bruto loon moet USD-lijn omrekenen naar SRD',
        )

    # ──────────────────────────────────────────────────────────────────────
    # 8. Payslip berekening klopt bij USD-lijnen met bevroren wisselkoers
    # ──────────────────────────────────────────────────────────────────────

    def test_payslip_compute_usd_lines(self):
        """
        Loonstrook SR_ALW-regel moet USD-toelage × bevroren koers bevatten.
        USD-contract: wage=500, toelage=100 USD, rate=36.5
        SR_ALW = 100 * 36.5 = 3650 SRD
        """
        rate = 36.5
        self.company.write({'sr_exchange_rate_usd': rate})

        contract = self._create_contract(
            wage=500.0,
            contract_currency=self.usd,
            vaste_regels=[(0, 0, {
                'name': 'Olie Toelage USD',
                'sr_categorie': 'belastbaar',
                'amount_type': 'fixed',
                'amount': 100.0,
                'line_currency_id': self.usd.id,
            })],
        )
        payslip = self._compute_payslip(contract)
        sr_alw = self._line_total(payslip, 'SR_ALW')
        expected = float(
            (Decimal('100.00') * Decimal(str(rate))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        )
        self._assertclose(sr_alw, expected, tol=0.05,
                          msg='SR_ALW op loonstrook moet USD-toelage × frozen rate zijn')

    # ──────────────────────────────────────────────────────────────────────
    # 9. Percentage-regels onaangetast bij vreemde contractvaluta
    # ──────────────────────────────────────────────────────────────────────

    def test_percentage_line_correct_with_foreign_currency(self):
        """
        Percentage-regels berekenen over basisloon in SRD, ongeacht lijn-valuta.
        USD-contract: wage=500, rate=36.5 → wage_srd=18250
        Percentage-lijn 10% over basisloon = 1825.0 SRD
        """
        rate = 36.5
        wage_usd = 500.0
        wage_srd = round(wage_usd * rate, 2)
        contract = self._create_contract(
            wage=wage_usd,
            contract_currency=self.usd,
            vaste_regels=[(0, 0, {
                'name': 'Pensioen 10%',
                'sr_categorie': 'aftrek_belastingvrij',
                'amount_type': 'percentage',
                'percentage': 10.0,
                'percentage_base': 'basisloon',
                'line_currency_id': self.usd.id,
            })],
        )
        aftrek = contract._sr_resolve_regels('aftrek_belastingvrij', exchange_rate=rate)
        expected = round(wage_srd * 0.10, 2)
        self._assertclose(aftrek, expected, tol=0.05,
                          msg='Percentage-lijn moet over SRD-basisloon berekend worden')

    # ──────────────────────────────────────────────────────────────────────
    # 10. Constraint: incompatibele lijn-valuta geblokkeerd
    # ──────────────────────────────────────────────────────────────────────

    def test_constraint_incompatible_line_currency_blocked(self):
        """EUR-lijn op USD-contract moet ValidationError geven."""
        contract = self._create_contract(
            wage=500.0,
            contract_currency=self.usd,
        )
        with self.assertRaises(ValidationError):
            self.env['hr.contract.sr.line'].create({
                'contract_id': contract.id,
                'name': 'Ongeldig EUR lijn',
                'sr_categorie': 'belastbaar',
                'amount_type': 'fixed',
                'amount': 100.0,
                'line_currency_id': self.eur.id,
            })

    # ──────────────────────────────────────────────────────────────────────
    # 11. init()-migratie: NULL line_currency_id krijgt SRD
    # ──────────────────────────────────────────────────────────────────────

    def test_migration_null_line_currency_gets_srd(self):
        """
        Simuleer een pre-migratie record door line_currency_id op NULL te zetten
        via SQL (na tijdelijk verwijderen van de NOT NULL constraint),
        roep dan init() aan en controleer dat het record SRD heeft gekregen.

        PostgreSQL DDL is transactioneel, dus de schema-wijziging wordt samen
        met de testdata teruggerold aan het einde van de TransactionCase.
        """
        contract = self._create_contract(wage=5000.0, contract_currency=self.srd)
        line = self.env['hr.contract.sr.line'].create({
            'contract_id': contract.id,
            'name': 'Oud Record Pre-Migratie',
            'sr_categorie': 'belastbaar',
            'amount_type': 'fixed',
            'amount': 250.0,
            'line_currency_id': self.srd.id,
        })
        # Tijdelijk NOT NULL constraint laten vallen om pre-migratie staat te simuleren
        # (PostgreSQL DDL is transactioneel en wordt samen met de testdata teruggerold)
        self.env.cr.execute(
            "ALTER TABLE hr_contract_sr_line ALTER COLUMN line_currency_id DROP NOT NULL"
        )
        # Simuleer pre-migratie staat: zet line_currency_id op NULL via SQL
        self.env.cr.execute(
            "UPDATE hr_contract_sr_line SET line_currency_id = NULL WHERE id = %s",
            (line.id,),
        )
        # Invalideer cache zodat Odoo de DB-waarde opnieuw leest
        line.invalidate_recordset(['line_currency_id'])

        # Roep init() aan — dit simuleert wat de module-update doet
        self.env['hr.contract.sr.line'].init()

        # Herlaad en verifieer
        line.invalidate_recordset(['line_currency_id'])
        self.assertEqual(
            line.line_currency_id, self.srd,
            'init() moet NULL line_currency_id instellen op SRD',
        )
        # Herstel NOT NULL constraint (transactioneel — maar voor de zekerheid expliciet)
        self.env.cr.execute(
            "ALTER TABLE hr_contract_sr_line ALTER COLUMN line_currency_id SET NOT NULL"
        )

    # ──────────────────────────────────────────────────────────────────────
    # 12. line_currency_id standaard = contractvaluta bij aanmaken nieuwe lijn
    # ──────────────────────────────────────────────────────────────────────

    def test_new_line_defaults_to_contract_currency(self):
        """Nieuwe lijn op USD-contract krijgt standaard line_currency_id = USD."""
        contract = self._create_contract(wage=500.0, contract_currency=self.usd)
        line = self.env['hr.contract.sr.line'].create({
            'contract_id': contract.id,
            'name': 'Nieuwe Toelage',
            'sr_categorie': 'belastbaar',
            'amount_type': 'fixed',
            'amount': 100.0,
            # line_currency_id NIET opgegeven — moet uit contract komen
        })
        self.assertEqual(
            line.line_currency_id, self.usd,
            'Nieuwe lijn op USD-contract moet standaard USD lijn-valuta hebben',
        )
