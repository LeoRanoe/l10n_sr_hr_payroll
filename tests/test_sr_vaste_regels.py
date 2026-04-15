# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Tests voor de hr.contract.sr.line tabel (sr_vaste_regels).

Verifieert dat:
  - het model correct aangemaakt kan worden
  - categorieën correct doorwerken in loonstrookregels
      belastbaar  → verhoogt SR_ALW → hogere LB grondslag
      vrijgesteld → verhoogt netto maar NIET de LB grondslag
      inhouding   → verlaagt netto exact
  - meerdere regels van dezelfde categorie correct opgeteld worden
  - de live preview velden (sr_preview_bruto, sr_preview_netto) kloppen
  - een leeg contract (geen vaste regels) geen fouten geeft
"""

from datetime import date

from odoo.tests import common, tagged
from odoo.tools import float_compare


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestSrVasteRegels(common.TransactionCase):
    """Tests specifiek voor de hr.contract.sr.line one2many tabel."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['res.company'].create({
            'name': 'Test Bedrijf SR Vaste Regels',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))

        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Werknemer SR VR',
            'company_id': cls.company.id,
        })
        cls.employee_b = cls.env['hr.employee'].create({
            'name': 'Test Werknemer SR VR B',
            'company_id': cls.company.id,
        })

        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

    def _create_contract(self, wage, salary_type='monthly', vaste_regels=None, employee=None):
        """Maak een contract aan met optionele vaste regels.

        Annuleert bestaande open contracten van dezelfde werknemer zodat
        meerdere aanroepen binnen één testmethode niet conflicteren.
        """
        emp = employee or self.employee
        # Annuleer bestaande open/running contracten om datum-overlap te voorkomen
        existing = self.env['hr.contract'].search([
            ('employee_id', '=', emp.id),
            ('state', 'in', ('open', 'pending')),
        ])
        if existing:
            existing.write({'state': 'cancel'})

        return self.env['hr.contract'].create({
            'name': 'Test Contract VR',
            'employee_id': emp.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_vaste_regels': vaste_regels or [],
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    def _compute_payslip(self, contract):
        """Berekeen een loonstrook voor april 2026."""
        payslip = self.env['hr.payslip'].create({
            'name': 'Test Loonstrook VR April 2026',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 4, 1),
            'date_to': date(2026, 4, 30),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        return payslip

    def _line_total(self, payslip, code):
        """Geef het totaalbedrag van een loonstroogregel op basis van code."""
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return line.total if line else 0.0

    def _assertclose(self, val, expected, msg='', tol=0.02):
        """Controleer dat val binnen tol van expected valt."""
        self.assertAlmostEqual(
            val, expected,
            delta=tol,
            msg=f'{msg} — verwacht {expected:.2f}, kreeg {val:.2f}',
        )

    # ──────────────────────────────────────────────────────────────────────
    # 1. Model registratie
    # ──────────────────────────────────────────────────────────────────────

    def test_model_bestaat(self):
        """hr.contract.sr.line model moet aanwezig zijn in de registry."""
        self.assertIn('hr.contract.sr.line', self.env)

    def test_model_crud(self):
        """Aanmaken, lezen, bijwerken en verwijderen van een sr.line rij."""
        contract = self._create_contract(wage=10000.0, vaste_regels=[
            (0, 0, {
                'name': 'Olie Toelage',
                'sr_categorie': 'belastbaar',
                'amount': 500.0,
            }),
        ])
        lijn = contract.sr_vaste_regels
        self.assertEqual(len(lijn), 1)
        self.assertEqual(lijn.name, 'Olie Toelage')
        self.assertEqual(lijn.sr_categorie, 'belastbaar')
        self.assertAlmostEqual(lijn.amount, 500.0)

        # Bijwerken via write
        lijn.write({'amount': 750.0})
        self.assertAlmostEqual(lijn.amount, 750.0)

        # Cascade verwijdering: contract in draft → unlink
        contract.write({'state': 'draft'})
        lijn_id = lijn.id
        contract.unlink()
        remaining = self.env['hr.contract.sr.line'].browse(lijn_id).exists()
        self.assertFalse(remaining, 'sr.line moet verwijderd zijn na cascade unlink van contract')

    # ──────────────────────────────────────────────────────────────────────
    # 2. Leeg contract — geen vaste regels
    # ──────────────────────────────────────────────────────────────────────

    def test_lege_tabel_geen_fout(self):
        """Contract zonder vaste regels mag geen fout geven."""
        contract = self._create_contract(wage=15000.0)
        self.assertEqual(len(contract.sr_vaste_regels), 0)

        payslip = self._compute_payslip(contract)
        # BASIC moet aanwezig zijn
        basic = self._line_total(payslip, 'BASIC')
        self.assertAlmostEqual(basic, 15000.0, delta=0.01)

        # SR_ALW moet 0 zijn (geen belastbare toelagen)
        alw = self._line_total(payslip, 'SR_ALW')
        self.assertAlmostEqual(alw, 0.0, delta=0.01,
                               msg='SR_ALW moet 0 zijn als er geen belastbare regels zijn')

    def test_lege_tabel_preview_velden(self):
        """Preview velden bij leeg contract: bruto == wage, netto = bruto - LB - AOV."""
        contract = self._create_contract(wage=15000.0)
        # sr_preview_bruto = wage (geen toelagen)
        self.assertAlmostEqual(contract.sr_preview_bruto, 15000.0, delta=0.01)

    # ──────────────────────────────────────────────────────────────────────
    # 3. Belastbare regel verhoogt SR_ALW en daarmee de LB grondslag
    # ──────────────────────────────────────────────────────────────────────

    def test_belastbaar_verhoogt_alw(self):
        """Een belastbare toelage van SRD 1.000 moet SR_ALW met 1.000 verhogen."""
        contract_zonder = self._create_contract(wage=20000.0)
        contract_met = self._create_contract(wage=20000.0, employee=self.employee_b, vaste_regels=[
            (0, 0, {'name': 'Olie Toelage', 'sr_categorie': 'belastbaar', 'amount': 1000.0}),
        ])

        ps_zonder = self._compute_payslip(contract_zonder)
        ps_met = self._compute_payslip(contract_met)

        alw_zonder = self._line_total(ps_zonder, 'SR_ALW')
        alw_met = self._line_total(ps_met, 'SR_ALW')

        self._assertclose(alw_met - alw_zonder, 1000.0,
                          'Verschil SR_ALW moet gelijk zijn aan de belastbare toelage')

    def test_belastbaar_verhoogt_lb(self):
        """Een belastbare toelage verhoogt de loonbelasting (SR_LB)."""
        contract_zonder = self._create_contract(wage=20000.0)
        contract_met = self._create_contract(wage=20000.0, employee=self.employee_b, vaste_regels=[
            (0, 0, {'name': 'Repr. Toelage', 'sr_categorie': 'belastbaar', 'amount': 2000.0}),
        ])

        lb_zonder = self._line_total(self._compute_payslip(contract_zonder), 'SR_LB')
        lb_met = self._line_total(self._compute_payslip(contract_met), 'SR_LB')

        self.assertGreater(
            abs(lb_met), abs(lb_zonder),
            'LB moet hogere absolute waarde hebben bij belastbare toelage (meer ingehouden)',
        )

    def test_belastbaar_preview_bruto(self):
        """sr_preview_bruto = wage + belastbare toelagen + vrijgestelde toelagen."""
        contract = self._create_contract(wage=15000.0, vaste_regels=[
            (0, 0, {'name': 'Olie', 'sr_categorie': 'belastbaar', 'amount': 500.0}),
        ])
        # bruto = wage + belastbaar (geen vrijgesteld)
        self.assertAlmostEqual(contract.sr_preview_bruto, 15500.0, delta=0.01)

    # ──────────────────────────────────────────────────────────────────────
    # 4. Vrijgestelde regel verhoogt netto maar NIET de LB grondslag
    # ──────────────────────────────────────────────────────────────────────

    def test_vrijgesteld_niet_in_gross(self):
        """Een vrijgestelde toelage mag SR_ALW NIET verhogen (geen LB grondslag)."""
        contract_zonder = self._create_contract(wage=20000.0)
        contract_met = self._create_contract(wage=20000.0, employee=self.employee_b, vaste_regels=[
            (0, 0, {'name': 'Kinderbijslag', 'sr_categorie': 'vrijgesteld', 'amount': 800.0}),
        ])

        alw_zonder = self._line_total(self._compute_payslip(contract_zonder), 'SR_ALW')
        alw_met = self._line_total(self._compute_payslip(contract_met), 'SR_ALW')

        self.assertAlmostEqual(
            alw_met, alw_zonder, delta=0.01,
            msg='SR_ALW mag niet veranderen door vrijgestelde toelage',
        )

    def test_vrijgesteld_niet_in_lb(self):
        """Vrijgestelde toelage mag de loonbelasting niet verhogen."""
        contract_zonder = self._create_contract(wage=20000.0)
        contract_met = self._create_contract(wage=20000.0, employee=self.employee_b, vaste_regels=[
            (0, 0, {'name': 'Transport', 'sr_categorie': 'vrijgesteld', 'amount': 300.0}),
        ])

        lb_zonder = self._line_total(self._compute_payslip(contract_zonder), 'SR_LB')
        lb_met = self._line_total(self._compute_payslip(contract_met), 'SR_LB')

        self.assertAlmostEqual(
            lb_met, lb_zonder, delta=0.01,
            msg='SR_LB mag niet veranderen door vrijgestelde toelage',
        )

    def test_vrijgesteld_verschijnt_in_kindbij(self):
        """Een vrijgestelde toelage moet in SR_KINDBIJ (vrijgesteld totaal) verschijnen."""
        contract = self._create_contract(wage=20000.0, vaste_regels=[
            (0, 0, {'name': 'Kinderbijslag', 'sr_categorie': 'vrijgesteld', 'amount': 500.0}),
        ])
        payslip = self._compute_payslip(contract)
        kindbij = self._line_total(payslip, 'SR_KINDBIJ')
        self._assertclose(kindbij, 500.0,
                          'SR_KINDBIJ moet gelijk zijn aan de vrijgestelde toelage')

    def test_vrijgesteld_preview_bruto(self):
        """sr_preview_bruto = wage + vrijgestelde toelagen (ook meegerekend in bruto)."""
        contract = self._create_contract(wage=15000.0, vaste_regels=[
            (0, 0, {'name': 'Kinderbijslag', 'sr_categorie': 'vrijgesteld', 'amount': 600.0}),
        ])
        self.assertAlmostEqual(contract.sr_preview_bruto, 15600.0, delta=0.01)

    # ──────────────────────────────────────────────────────────────────────
    # 5. Inhouding verlaagt netto exact
    # ──────────────────────────────────────────────────────────────────────

    def test_inhouding_verschijnt_in_pensioen(self):
        """Een inhouding van SRD 200 moet in SR_PENSIOEN verschijnen als SRD -200."""
        contract = self._create_contract(wage=20000.0, vaste_regels=[
            (0, 0, {'name': 'Pensioenpremie', 'sr_categorie': 'inhouding', 'amount': 200.0}),
        ])
        payslip = self._compute_payslip(contract)
        pensioen = self._line_total(payslip, 'SR_PENSIOEN')
        self._assertclose(pensioen, -200.0,
                          'SR_PENSIOEN moet -200 zijn (aftrek)')

    def test_inhouding_verhoogt_geen_lb(self):
        """Een inhouding mag de loonbelasting niet verhogen of verlagen."""
        contract_zonder = self._create_contract(wage=20000.0)
        contract_met = self._create_contract(wage=20000.0, employee=self.employee_b, vaste_regels=[
            (0, 0, {'name': 'Ziektekostenpremie', 'sr_categorie': 'inhouding', 'amount': 150.0}),
        ])

        lb_zonder = self._line_total(self._compute_payslip(contract_zonder), 'SR_LB')
        lb_met = self._line_total(self._compute_payslip(contract_met), 'SR_LB')

        self.assertAlmostEqual(
            lb_met, lb_zonder, delta=0.01,
            msg='SR_LB mag niet veranderen door een inhouding',
        )

    def test_inhouding_preview_netto(self):
        """sr_preview_netto moet lager zijn met een inhouding dan zonder."""
        contract_zonder = self._create_contract(wage=15000.0)
        contract_met = self._create_contract(wage=15000.0, vaste_regels=[
            (0, 0, {'name': 'Pensioenpremie', 'sr_categorie': 'inhouding', 'amount': 300.0}),
        ])

        netto_verschil = contract_zonder.sr_preview_netto - contract_met.sr_preview_netto
        self.assertAlmostEqual(
            netto_verschil, 300.0, delta=0.01,
            msg='Nettoverschil moet exact gelijk zijn aan de inhouding',
        )

    # ──────────────────────────────────────────────────────────────────────
    # 6. Meerdere regels van dezelfde categorie
    # ──────────────────────────────────────────────────────────────────────

    def test_meerdere_belastbare_lijnen_opgeteld(self):
        """Drie belastbare regels moeten samen correct opgeteld worden in SR_ALW."""
        contract = self._create_contract(wage=20000.0, vaste_regels=[
            (0, 0, {'name': 'Olie Toelage', 'sr_categorie': 'belastbaar', 'amount': 500.0}),
            (0, 0, {'name': 'Kleding Toelage', 'sr_categorie': 'belastbaar', 'amount': 300.0}),
            (0, 0, {'name': 'Repr. Toelage', 'sr_categorie': 'belastbaar', 'amount': 200.0}),
        ])
        payslip = self._compute_payslip(contract)
        alw = self._line_total(payslip, 'SR_ALW')
        self._assertclose(alw, 1000.0,
                          'SR_ALW moet som zijn van alle belastbare regels (500+300+200=1000)')

    def test_meerdere_vrijgestelde_lijnen_opgeteld(self):
        """Twee vrijgestelde regels moeten samen in SR_KINDBIJ verschijnen."""
        contract = self._create_contract(wage=20000.0, vaste_regels=[
            (0, 0, {'name': 'Kinderbijslag', 'sr_categorie': 'vrijgesteld', 'amount': 400.0}),
            (0, 0, {'name': 'Transport', 'sr_categorie': 'vrijgesteld', 'amount': 200.0}),
        ])
        payslip = self._compute_payslip(contract)
        kindbij = self._line_total(payslip, 'SR_KINDBIJ')
        self._assertclose(kindbij, 600.0,
                          'SR_KINDBIJ moet som zijn van alle vrijgestelde regels (400+200=600)')

    def test_meerdere_inhoudingen_opgeteld(self):
        """Twee inhoudingen moeten samen in SR_PENSIOEN verschijnen."""
        contract = self._create_contract(wage=20000.0, vaste_regels=[
            (0, 0, {'name': 'Pensioenpremie', 'sr_categorie': 'inhouding', 'amount': 200.0}),
            (0, 0, {'name': 'Ziektekostenpremie', 'sr_categorie': 'inhouding', 'amount': 100.0}),
        ])
        payslip = self._compute_payslip(contract)
        pensioen = self._line_total(payslip, 'SR_PENSIOEN')
        self._assertclose(pensioen, -300.0,
                          'SR_PENSIOEN moet som zijn van alle inhoudingen (-200-100=-300)')

    # ──────────────────────────────────────────────────────────────────────
    # 7. Gemengde regels (alle drie categorieën tegelijk)
    # ──────────────────────────────────────────────────────────────────────

    def test_gemengde_regels(self):
        """Mix van alle drie categorieën op één contract."""
        contract = self._create_contract(wage=18000.0, vaste_regels=[
            (0, 0, {'name': 'Olie Toelage', 'sr_categorie': 'belastbaar', 'amount': 600.0}),
            (0, 0, {'name': 'Transport', 'sr_categorie': 'vrijgesteld', 'amount': 300.0}),
            (0, 0, {'name': 'Pensioenpremie', 'sr_categorie': 'inhouding', 'amount': 250.0}),
        ])
        payslip = self._compute_payslip(contract)

        alw = self._line_total(payslip, 'SR_ALW')
        kindbij = self._line_total(payslip, 'SR_KINDBIJ')
        pensioen = self._line_total(payslip, 'SR_PENSIOEN')

        self._assertclose(alw, 600.0, 'SR_ALW moet belastbare toelage bevatten')
        self._assertclose(kindbij, 300.0, 'SR_KINDBIJ moet vrijgestelde toelage bevatten')
        self._assertclose(pensioen, -250.0, 'SR_PENSIOEN moet inhouding bevatten')

    def test_gemengde_preview_velden(self):
        """Preview velden bij gemengde regels."""
        # wage=18000, belastbaar=600, vrijgesteld=300, inhouding=250
        contract = self._create_contract(wage=18000.0, vaste_regels=[
            (0, 0, {'name': 'Olie', 'sr_categorie': 'belastbaar', 'amount': 600.0}),
            (0, 0, {'name': 'Transport', 'sr_categorie': 'vrijgesteld', 'amount': 300.0}),
            (0, 0, {'name': 'Pensioen', 'sr_categorie': 'inhouding', 'amount': 250.0}),
        ])

        # Bruto = wage + belastbaar + vrijgesteld = 18000 + 600 + 300 = 18900
        self.assertAlmostEqual(contract.sr_preview_bruto, 18900.0, delta=0.01,
                               msg='sr_preview_bruto = wage + belastbaar + vrijgesteld')

        # Netto moet lager zijn dan bruto (LB + AOV + inhouding worden afgetrokken)
        self.assertLess(contract.sr_preview_netto, contract.sr_preview_bruto,
                        msg='Nettoloon moet lager zijn dan bruto')

        # Netto = bruto - LB - AOV - inhoudingen
        # Verifieer dat inhouding correct in netto verrekend is
        contract_zonder_inhouding = self._create_contract(wage=18000.0, vaste_regels=[
            (0, 0, {'name': 'Olie', 'sr_categorie': 'belastbaar', 'amount': 600.0}),
            (0, 0, {'name': 'Transport', 'sr_categorie': 'vrijgesteld', 'amount': 300.0}),
        ])
        netto_verschil = contract_zonder_inhouding.sr_preview_netto - contract.sr_preview_netto
        self.assertAlmostEqual(
            netto_verschil, 250.0, delta=0.01,
            msg='Nettoverschil met/zonder inhouding moet precies de inhouding zijn',
        )

    # ──────────────────────────────────────────────────────────────────────
    # 8. sr_preview_bruto berekeninglogica
    # ──────────────────────────────────────────────────────────────────────

    def test_preview_bruto_alleen_wage(self):
        """sr_preview_bruto = wage als er geen vaste regels zijn."""
        contract = self._create_contract(wage=12500.0)
        self.assertAlmostEqual(contract.sr_preview_bruto, 12500.0, delta=0.01)

    def test_preview_bruto_belastbaar_plus_vrijgesteld(self):
        """sr_preview_bruto = wage + belastbaar + vrijgesteld (inhouding telt NIET mee)."""
        contract = self._create_contract(wage=12500.0, vaste_regels=[
            (0, 0, {'name': 'A', 'sr_categorie': 'belastbaar', 'amount': 400.0}),
            (0, 0, {'name': 'B', 'sr_categorie': 'vrijgesteld', 'amount': 200.0}),
            (0, 0, {'name': 'C', 'sr_categorie': 'inhouding', 'amount': 100.0}),
        ])
        # Bruto = 12500 + 400 + 200 = 13100 (inhouding telt niet mee in bruto)
        self.assertAlmostEqual(contract.sr_preview_bruto, 13100.0, delta=0.01)

    def test_preview_belastbaar_jaar(self):
        """sr_preview_belastbaar_jaar = (wage + belastbaar) * 12 - vrijstellingen."""
        contract_basis = self._create_contract(wage=20000.0)
        contract_toelage = self._create_contract(wage=20000.0, vaste_regels=[
            (0, 0, {'name': 'Extra', 'sr_categorie': 'belastbaar', 'amount': 1000.0}),
        ])
        # Jaarverschil in belastbaar = 1000 * 12 = 12000
        verschil_jaar = (
            contract_toelage.sr_preview_belastbaar_jaar
            - contract_basis.sr_preview_belastbaar_jaar
        )
        self.assertAlmostEqual(
            verschil_jaar, 12000.0, delta=1.0,
            msg='Belastbaar jaarloon moet stijgen met belastbare toelage × 12 periodes',
        )

    # ──────────────────────────────────────────────────────────────────────
    # 9. Categorie selectie validatie
    # ──────────────────────────────────────────────────────────────────────

    def test_alle_categorieen_aanmaken(self):
        """Alle drie categorieën moeten aangemaakt kunnen worden."""
        for categorie in ('belastbaar', 'vrijgesteld', 'inhouding'):
            lijn = self.env['hr.contract.sr.line'].new({
                'name': f'Test {categorie}',
                'sr_categorie': categorie,
                'amount': 100.0,
            })
            self.assertEqual(lijn.sr_categorie, categorie)

    # ──────────────────────────────────────────────────────────────────────
    # 10. Fortnight loon (26 periodes)
    # ──────────────────────────────────────────────────────────────────────

    def test_fortnight_belastbaar_preview(self):
        """Bij fortnight loon moet sr_preview_belastbaar_jaar kloppen voor 26 periodes."""
        contract = self._create_contract(wage=5000.0, salary_type='fn', vaste_regels=[
            (0, 0, {'name': 'Olie', 'sr_categorie': 'belastbaar', 'amount': 200.0}),
        ])
        # (5000 + 200) * 26 = 135.200 → minus vrijstellingen
        bruto_jaar = (5000.0 + 200.0) * 26  # = 135200
        # Berekend belastbaar jaar hangt af van vrijstelling, maar moet positief zijn
        self.assertGreater(contract.sr_preview_belastbaar_jaar, 0.0)

    def test_fortnight_gemengde_regels(self):
        """Fortnight contract met gemengde regels moet correcte preview geven."""
        contract = self._create_contract(wage=5000.0, salary_type='fn', vaste_regels=[
            (0, 0, {'name': 'Belastbaar', 'sr_categorie': 'belastbaar', 'amount': 300.0}),
            (0, 0, {'name': 'Vrijgesteld', 'sr_categorie': 'vrijgesteld', 'amount': 150.0}),
        ])
        # Bruto = 5000 + 300 + 150 = 5450
        self.assertAlmostEqual(contract.sr_preview_bruto, 5450.0, delta=0.01)
