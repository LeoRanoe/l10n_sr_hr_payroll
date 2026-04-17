# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Integratietests voor de Suriname Loonbelasting module (l10n_sr_hr_payroll).

Deze tests volgen de volledige loonverwerkingscyclus:
  1. Werknemer + contract aanmaken
  2. Loonstrook genereren met compute_sheet()
  3. Controleren of alle SR-salarisregels aanwezig zijn
  4. Verificatie van de berekende bedragen (LB, AOV, netto)
  5. Live preview computed fields op het contract

De integratietests zijn bewust gescheiden van de unit tests om
duidelijk onderscheid te maken tussen geïsoleerde logica verificatie
en end-to-end loonverwerkingsflows.
"""

from datetime import date

from odoo.exceptions import UserError
from odoo.tests import common, tagged


def _fn_period_2026_9():
    return date(2026, 4, 23), date(2026, 5, 6)


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestIntegratieVolledigeCyclus(common.TransactionCase):
    """
    End-to-end loonverwerkingscyclus test:
    contract aanmaken → loonstrook genereren → bedragen verifiëren.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.company = cls.env['res.company'].create({
            'name': 'Test SR Integratie Bedrijf',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Integratie Testwerknemer SR',
            'company_id': cls.company.id,
        })
        cls.employee_b = cls.env['hr.employee'].create({
            'name': 'Integratie Testwerknemer SR B',
            'company_id': cls.company.id,
        })
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

    def _maak_contract(self, wage, salary_type='monthly',
                       toelagen=0.0, kinderbijslag=0.0, pensioenpremie=0.0,
                       employee=None, date_start=None, aantal_kinderen=None):
        emp = employee or self.employee
        vaste_regels = []
        if toelagen:
            vaste_regels.append((0, 0, {'name': 'Belastbare Toelagen', 'sr_categorie': 'belastbaar', 'amount': toelagen}))
        if kinderbijslag:
            vaste_regels.append((0, 0, {
                'name': 'Kinderbijslag',
                'type_id': self.env.ref('l10n_sr_hr_payroll.sr_line_type_kinderbijslag').id,
                'sr_categorie': 'vrijgesteld',
                'amount': kinderbijslag,
            }))
        if pensioenpremie:
            vaste_regels.append((0, 0, {'name': 'Pensioenpremie', 'sr_categorie': 'inhouding', 'amount': pensioenpremie}))
        return self.env['hr.contract'].create({
            'name': f'Integratie Contract {salary_type} {wage}',
            'employee_id': emp.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_aantal_kinderen': aantal_kinderen if aantal_kinderen is not None else (4 if kinderbijslag else 0),
            'sr_vaste_regels': vaste_regels,
            'date_start': date_start or date(2026, 1, 1),
            'state': 'open',
        })

    def _maak_input(self, xmlid, amount):
        input_type = self.env.ref(xmlid)
        return {
            'name': input_type.name,
            'input_type_id': input_type.id,
            'amount': amount,
        }

    def _maak_loonstrook(self, contract, date_from=None, date_to=None, inputs=None):
        if not date_from or not date_to:
            if contract.sr_salary_type == 'fn':
                date_from, date_to = _fn_period_2026_9()
            else:
                date_from = date_from or date(2026, 5, 1)
                date_to = date_to or date(2026, 5, 31)
        payslip_vals = {
            'name': f'Integratie Loonstrook {date_from}',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.company.id,
        }
        if inputs:
            payslip_vals['input_line_ids'] = [(0, 0, input_vals) for input_vals in inputs]
        payslip = self.env['hr.payslip'].create(payslip_vals)
        payslip.compute_sheet()
        return payslip

    def _haal_regel(self, payslip, code):
        return payslip.line_ids.filtered(lambda l: l.code == code)

    def _haal_totaal(self, payslip, code):
        regel = self._haal_regel(payslip, code)
        return regel.total if regel else 0.0

    # ──────────────────────────────────────────────────────────────────
    # Test 1: Alle SR salarisregels aanwezig na compute_sheet
    # ──────────────────────────────────────────────────────────────────
    def test_alle_sr_regels_aanwezig(self):
        """Na compute_sheet() moeten alle SR salarisregelcodes aanwezig zijn."""
        contract = self._maak_contract(wage=20000.0)
        payslip = self._maak_loonstrook(contract)

        verwachte_codes = ['BASIC', 'GROSS', 'SR_LB', 'SR_AOV', 'NET']
        aanwezige_codes = payslip.line_ids.mapped('code')

        for code in verwachte_codes:
            self.assertIn(
                code, aanwezige_codes,
                f'Salarisregel met code "{code}" ontbreekt op de loonstrook',
            )

    def test_toekomstige_placeholder_schijven_blokkeren_huidige_berekening_niet(self):
        """Extra Art. 14 parametercodes zonder actieve waarde mogen 2026 payroll niet breken."""
        country = self.env.ref('base.sr')
        self.env['hr.rule.parameter'].create({
            'name': 'Test reserve schijfgrens zonder waarde',
            'code': 'SR_SCHIJF_99_GRENS',
            'country_id': country.id,
        })
        self.env['hr.rule.parameter'].create({
            'name': 'Test reserve tarief zonder waarde',
            'code': 'SR_TARIEF_100',
            'country_id': country.id,
        })

        contract = self._maak_contract(wage=20000.0)
        payslip = self._maak_loonstrook(contract)

        self.assertTrue(
            bool(self._haal_regel(payslip, 'SR_LB')),
            'Reserve Art. 14 parametercodes zonder actieve waarde mogen de payroll niet blokkeren',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 2: Netto = Bruto + alle inhoudingen (balanscontrole)
    # ──────────────────────────────────────────────────────────────────
    def test_netto_is_bruto_min_inhoudingen(self):
        """NET = GROSS + SR_LB + SR_AOV (LB en AOV zijn negatief, geen HK)."""
        contract = self._maak_contract(wage=20000.0)
        payslip = self._maak_loonstrook(contract)

        gross = self._haal_totaal(payslip, 'GROSS')
        lb = self._haal_totaal(payslip, 'SR_LB')
        aov = self._haal_totaal(payslip, 'SR_AOV')
        net = self._haal_totaal(payslip, 'NET')

        self.assertAlmostEqual(
            net, gross + lb + aov, places=2,
            msg='Nettoloon ≠ Bruto + LB + AOV (saldo klopt niet)',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 3: Nettoloon ligt altijd LAGER dan brutoloon (bij belastbaar loon)
    # ──────────────────────────────────────────────────────────────────
    def test_netto_lager_dan_bruto(self):
        """Nettoloon moet lager zijn dan brutoloon voor belastbaar loon."""
        contract = self._maak_contract(wage=20000.0)
        payslip = self._maak_loonstrook(contract)

        gross = self._haal_totaal(payslip, 'GROSS')
        net = self._haal_totaal(payslip, 'NET')

        self.assertGreater(gross, 0.0, 'Brutoloon moet positief zijn')
        self.assertLess(net, gross, 'Nettoloon moet lager zijn dan brutoloon')

    # ──────────────────────────────────────────────────────────────────
    # Test 4: Toelagen onderdeel van GROSS
    # ──────────────────────────────────────────────────────────────────
    def test_toelagen_in_gross(self):
        """Belastbare toelagen moeten worden opgeteld bij GROSS."""
        contract_zonder = self._maak_contract(wage=15000.0, toelagen=0.0)
        contract_met = self._maak_contract(wage=15000.0, toelagen=3000.0, employee=self.employee_b)

        payslip_zonder = self._maak_loonstrook(contract_zonder)
        payslip_met = self._maak_loonstrook(contract_met)

        gross_zonder = self._haal_totaal(payslip_zonder, 'GROSS')
        gross_met = self._haal_totaal(payslip_met, 'GROSS')

        self.assertAlmostEqual(
            gross_met, gross_zonder + 3000.0, places=2,
            msg='Toelagen moeten GROSS met SRD 3.000 verhogen',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 5: Kinderbijslag verhoogt NET maar niet GROSS belastinggrondslag
    # ──────────────────────────────────────────────────────────────────
    def test_kinderbijslag_verhoogt_net_niet_lb(self):
        """
        Kinderbijslag verhoogt het nettoloon (belastingvrij) maar
        mag de loonbelasting NIET verhogen.
        """
        kinderbijslag = 500.0
        contract_zonder = self._maak_contract(wage=20000.0)
        contract_met = self._maak_contract(
            wage=20000.0, kinderbijslag=kinderbijslag, employee=self.employee_b
        )

        payslip_zonder = self._maak_loonstrook(contract_zonder)
        payslip_met = self._maak_loonstrook(contract_met)

        lb_zonder = self._haal_totaal(payslip_zonder, 'SR_LB')
        lb_met = self._haal_totaal(payslip_met, 'SR_LB')
        net_zonder = self._haal_totaal(payslip_zonder, 'NET')
        net_met = self._haal_totaal(payslip_met, 'NET')

        self.assertEqual(lb_zonder, lb_met,
                         'Kinderbijslag mag LB NIET beïnvloeden')
        self.assertAlmostEqual(
            net_met, net_zonder + kinderbijslag, places=2,
            msg='Kinderbijslag moet NET met het exacte bedrag verhogen',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 6: Pensioenpremie inhouding correct
    # ──────────────────────────────────────────────────────────────────
    def test_pensioenpremie_inhouding(self):
        """
        Pensioenpremie moet als negatieve inhouding op de loonstrook staan
        en het nettoloon met het exacte premiebedrag verlagen.
        """
        premie = 1000.0
        contract_zonder = self._maak_contract(wage=20000.0)
        contract_met = self._maak_contract(wage=20000.0, pensioenpremie=premie, employee=self.employee_b)

        payslip_zonder = self._maak_loonstrook(contract_zonder)
        payslip_met = self._maak_loonstrook(contract_met)

        pensioen = self._haal_totaal(payslip_met, 'SR_PENSIOEN')
        net_zonder = self._haal_totaal(payslip_zonder, 'NET')
        net_met = self._haal_totaal(payslip_met, 'NET')

        self.assertAlmostEqual(pensioen, -premie, places=2,
                               msg='Pensioenpremie inhouding klopt niet')
        self.assertAlmostEqual(
            net_met, net_zonder - premie, places=2,
            msg='Nettoloon na pensioenpremie klopt niet',
        )

    def test_bijzondere_beloningen_gecombineerd_in_een_marginale_berekening(self):
        """Vakantie + Art. 17 beloning moeten via één belastbaar totaal doorwerken."""
        contract = self._maak_contract(wage=20000.0)
        payslip = self._maak_loonstrook(
            contract,
            inputs=[
                self._maak_input('l10n_sr_hr_payroll.sr_input_vakantietoelage', 24000.0),
                self._maak_input('l10n_sr_hr_payroll.sr_input_bijz_beloning', 1200.0),
            ],
        )

        belastbaar_bijz = payslip._sr_bijz_belastbaar_totaal()
        aov_bijz = self._haal_totaal(payslip, 'SR_AOV_BIJZ')
        lb_bijz = self._haal_totaal(payslip, 'SR_LB_BIJZ')

        self.assertAlmostEqual(
            belastbaar_bijz, 5700.0, places=2,
            msg='Gecombineerde Art. 17 grondslag klopt niet',
        )
        self.assertAlmostEqual(
            aov_bijz, -19.0, places=2,
            msg='AOV op gecombineerde bijzondere beloningen klopt niet',
        )
        self.assertLess(lb_bijz, 0.0, 'LB bijzondere beloningen moet een inhouding zijn')

    def test_bijzondere_beloningen_ytd_cap_volgt_historische_contractstaat(self):
        """YTD vrijstellingsgebruik moet vorige slips met hun eigen loon/contract lezen."""
        vorig_contract = self._maak_contract(
            wage=2000.0,
            employee=self.employee,
            date_start=date(2026, 1, 1),
        )
        vorige_slip = self._maak_loonstrook(
            vorig_contract,
            date_from=date(2026, 3, 1),
            date_to=date(2026, 3, 31),
            inputs=[self._maak_input('l10n_sr_hr_payroll.sr_input_vakantietoelage', 9000.0)],
        )
        vorige_slip.write({'state': 'done'})
        vorig_contract.write({'state': 'close'})

        nieuw_contract = self._maak_contract(
            wage=6000.0,
            employee=self.employee,
            date_start=date(2026, 7, 1),
        )
        huidige_slip = self._maak_loonstrook(
            nieuw_contract,
            date_from=date(2026, 8, 1),
            date_to=date(2026, 8, 31),
            inputs=[self._maak_input('l10n_sr_hr_payroll.sr_input_vakantietoelage', 7000.0)],
        )

        self.assertAlmostEqual(
            huidige_slip._sr_bijz_belastbaar_totaal(), 0.0, places=2,
            msg='YTD-cap moet de historische vrijstelling uit vorige slips correct meenemen',
        )

    def test_uitkering_ineens_artikel_17a_regels(self):
        """Art. 17a moet eigen LB-schijven en volledige AOV gebruiken."""
        contract = self._maak_contract(wage=20000.0)
        payslip = self._maak_loonstrook(
            contract,
            inputs=[self._maak_input('l10n_sr_hr_payroll.sr_input_uitkering_ineens', 100000.0)],
        )

        self.assertAlmostEqual(
            self._haal_totaal(payslip, 'SR_LB_17A'), -12400.0, places=2,
            msg='LB op uitkering ineens (Art. 17a) klopt niet',
        )
        self.assertAlmostEqual(
            self._haal_totaal(payslip, 'SR_AOV_17A'), -4000.0, places=2,
            msg='AOV op uitkering ineens (Art. 17a) klopt niet',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 7: Fortnight loonstrook — juiste periodestructuur
    # ──────────────────────────────────────────────────────────────────
    def test_fortnight_loonstrook_aangemaakt(self):
        """
        Fortnight contract genereert een geldige loonstrook met
        SR_LB en SR_AOV regels. Geen AOV franchise voor fortnight.
        """
        fn_loon = 8000.0  # SRD 8.000 per fortnight
        contract = self._maak_contract(wage=fn_loon, salary_type='fn')
        payslip = self._maak_loonstrook(
            contract,
            date_from=_fn_period_2026_9()[0],
            date_to=_fn_period_2026_9()[1],
        )

        aov = self._haal_totaal(payslip, 'SR_AOV')
        # AOV fortnight: geen franchise (context: "geen franchise per FN")
        expected_aov = -(fn_loon * 0.04)
        self.assertAlmostEqual(aov, expected_aov, places=2,
                               msg='AOV fortnight (geen franchise) klopt niet')
        self.assertEqual(
            payslip._get_sr_artikel14_breakdown()['fn_period_label'], '2026FN9'
        )

    def test_fortnight_loonstrook_weigert_ongeldig_2026_tijdvak(self):
        """2026 FN-loonstroken buiten de contextkalender moeten worden geweigerd."""
        contract = self._maak_contract(wage=8000.0, salary_type='fn')

        with self.assertRaises(UserError):
            self._maak_loonstrook(
                contract,
                date_from=date(2026, 5, 1),
                date_to=date(2026, 5, 14),
            )

    # ──────────────────────────────────────────────────────────────────
    # Test 8: Breakdown dict consistent met SR_LB salarisregel (integratiecheck)
    # ──────────────────────────────────────────────────────────────────
    def test_breakdown_consistent_met_salarisregel(self):
        """
        _get_sr_artikel14_breakdown() lb_per_periode moet overeenkomen
        met de berekende SR_LB salarisregel.
        """
        contract = self._maak_contract(wage=25000.0)
        payslip = self._maak_loonstrook(contract)

        bd = payslip._get_sr_artikel14_breakdown()
        lb_regel = self._haal_totaal(payslip, 'SR_LB')

        if bd:
            self.assertAlmostEqual(
                bd['lb_per_periode'], abs(lb_regel), delta=0.05,
                msg='breakdown lb_per_periode ≠ SR_LB.total (integratieconflict)',
            )


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestIntegratieContractPreview(common.TransactionCase):
    """
    Tests voor de live preview computed fields op hr.contract.
    Verifieert dat de 5 sr_preview_* velden realistische waarden bevatten.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test SR Preview Bedrijf',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Preview Testwerknemer',
            'company_id': cls.company.id,
        })
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

    def _maak_contract(self, wage, salary_type='monthly',
                       toelagen=0.0, kinderbijslag=0.0, pensioenpremie=0.0,
                       aantal_kinderen=None):
        vaste_regels = []
        if toelagen:
            vaste_regels.append((0, 0, {'name': 'Belastbare Toelagen', 'sr_categorie': 'belastbaar', 'amount': toelagen}))
        if kinderbijslag:
            vaste_regels.append((0, 0, {
                'name': 'Kinderbijslag',
                'type_id': self.env.ref('l10n_sr_hr_payroll.sr_line_type_kinderbijslag').id,
                'sr_categorie': 'vrijgesteld',
                'amount': kinderbijslag,
            }))
        if pensioenpremie:
            vaste_regels.append((0, 0, {'name': 'Pensioenpremie', 'sr_categorie': 'inhouding', 'amount': pensioenpremie}))
        return self.env['hr.contract'].create({
            'name': f'Preview Contract {salary_type} {wage}',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_aantal_kinderen': aantal_kinderen if aantal_kinderen is not None else (4 if kinderbijslag else 0),
            'sr_vaste_regels': vaste_regels,
            'date_start': date(2026, 1, 1),
            'state': 'draft',
        })

    # ──────────────────────────────────────────────────────────────────
    # Test 1: Preview velden zijn positief voor een normaal loon
    # ──────────────────────────────────────────────────────────────────
    def test_preview_bruto_positief(self):
        """sr_preview_bruto moet gelijk zijn aan wage (geen toelagen)."""
        contract = self._maak_contract(wage=20000.0)
        self.assertAlmostEqual(
            contract.sr_preview_bruto, 20000.0, places=2,
            msg='sr_preview_bruto moet gelijk zijn aan wage',
        )

    def test_preview_netto_positief(self):
        """sr_preview_netto moet positief zijn voor een normaal contract."""
        contract = self._maak_contract(wage=20000.0)
        self.assertGreater(
            contract.sr_preview_netto, 0.0,
            'sr_preview_netto moet positief zijn',
        )

    def test_preview_netto_lager_dan_bruto(self):
        """sr_preview_netto moet lager zijn dan sr_preview_bruto."""
        contract = self._maak_contract(wage=20000.0)
        self.assertLess(
            contract.sr_preview_netto, contract.sr_preview_bruto,
            'Preview netto moet lager zijn dan preview bruto',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 2: Preview belastbaar jaarloon correct berekend
    # ──────────────────────────────────────────────────────────────────
    def test_preview_belastbaar_jaar_berekening(self):
        """
        Wage SRD 20.000/maand:
        Bruto jaar = 240.000
        Forfaitaire = min(240.000 × 4%, 4.800) = 4.800
        Belastbaar = 240.000 − 108.000 − 4.800 = 127.200
        """
        contract = self._maak_contract(wage=20000.0)
        verwacht = 20000.0 * 12 - 108000.0 - 4800.0  # = 127.200
        self.assertAlmostEqual(
            contract.sr_preview_belastbaar_jaar, verwacht, places=2,
            msg='sr_preview_belastbaar_jaar klopt niet',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 3: Preview LB niet negatief
    # ──────────────────────────────────────────────────────────────────
    def test_preview_lb_niet_negatief(self):
        """sr_preview_lb_periode mag nooit negatief zijn."""
        for wage in [5000.0, 10000.0, 20000.0, 50000.0]:
            contract = self._maak_contract(wage=wage)
            self.assertGreaterEqual(
                contract.sr_preview_lb_periode, 0.0,
                f'sr_preview_lb_periode is negatief voor wage={wage}',
            )

    # ──────────────────────────────────────────────────────────────────
    # Test 4: Preview voor laag loon → LB = 0
    # ──────────────────────────────────────────────────────────────────
    def test_preview_lb_nul_voor_laag_loon(self):
        """
        Wage SRD 5.000/maand → jaarloon SRD 60.000 < belastingvrij SRD 108.000
        → belastbaar jaarloon = 0 → LB = 0.
        """
        contract = self._maak_contract(wage=5000.0)
        self.assertEqual(
            contract.sr_preview_lb_periode, 0.0,
            'LB preview moet 0 zijn voor loon onder belastingvrije grens',
        )
        self.assertEqual(
            contract.sr_preview_belastbaar_jaar, 0.0,
            'Belastbaar jaarloon preview moet 0 zijn voor laag loon',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 5: Preview met toelagen verhoogt bruto en LB
    # ──────────────────────────────────────────────────────────────────
    def test_preview_toelagen_verhogen_bruto_en_lb(self):
        """Toelagen moeten sr_preview_bruto en sr_preview_lb_periode verhogen."""
        contract_zonder = self._maak_contract(wage=20000.0)
        contract_met = self._maak_contract(wage=20000.0, toelagen=3000.0)

        self.assertGreater(
            contract_met.sr_preview_bruto, contract_zonder.sr_preview_bruto,
            'Toelagen moeten sr_preview_bruto verhogen',
        )
        self.assertGreaterEqual(
            contract_met.sr_preview_lb_periode,
            contract_zonder.sr_preview_lb_periode,
            'Toelagen moeten sr_preview_lb_periode verhogen of gelijk houden',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 6: Preview met kinderbijslag verhoogt bruto maar niet LB
    # ──────────────────────────────────────────────────────────────────
    def test_preview_kinderbijslag_verhoogt_bruto_niet_lb(self):
        """
        Kinderbijslag moet sr_preview_bruto verhogen maar
        sr_preview_lb_periode gelijk laten.
        """
        contract_zonder = self._maak_contract(wage=20000.0)
        contract_met = self._maak_contract(wage=20000.0, kinderbijslag=500.0)

        self.assertGreater(
            contract_met.sr_preview_bruto, contract_zonder.sr_preview_bruto,
            'Kinderbijslag moet sr_preview_bruto verhogen',
        )
        self.assertEqual(
            contract_zonder.sr_preview_lb_periode,
            contract_met.sr_preview_lb_periode,
            'Kinderbijslag mag sr_preview_lb_periode NIET veranderen',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 7: Preview AOV correct voor maand/fortnight
    # ──────────────────────────────────────────────────────────────────
    def test_preview_aov_maandloon_met_franchise(self):
        """
        Maandloon SRD 5.000 → AOV grondslag = 5.000 − 400 = 4.600
        sr_preview_aov_periode = 4.600 × 4% = 184.
        """
        contract = self._maak_contract(wage=5000.0, salary_type='monthly')
        verwacht = (5000.0 - 400.0) * 0.04
        self.assertAlmostEqual(
            contract.sr_preview_aov_periode, verwacht, places=2,
            msg='sr_preview_aov_periode maandloon klopt niet',
        )

    def test_preview_aov_fortnight_geen_franchise(self):
        """
        Fortnight SRD 5.000 → AOV grondslag = 5.000 (geen franchise)
        sr_preview_aov_periode = 5.000 × 4% = 200.
        """
        contract = self._maak_contract(wage=5000.0, salary_type='fn')
        verwacht = 5000.0 * 0.04  # geen franchise
        self.assertAlmostEqual(
            contract.sr_preview_aov_periode, verwacht, places=2,
            msg='sr_preview_aov_periode fortnight klopt niet',
        )

    # ──────────────────────────────────────────────────────────────────
    # Test 8: Preview netto = bruto - LB - AOV - pensioen
    # ──────────────────────────────────────────────────────────────────
    def test_preview_netto_berekening(self):
        """sr_preview_netto = sr_preview_bruto − lb − aov − pensioen."""
        pensioen = 800.0
        contract = self._maak_contract(
            wage=20000.0, pensioenpremie=pensioen
        )
        verwacht_netto = (
            contract.sr_preview_bruto
            - contract.sr_preview_lb_periode
            - contract.sr_preview_aov_periode
            - pensioen
        )
        self.assertAlmostEqual(
            contract.sr_preview_netto, verwacht_netto, places=2,
            msg='sr_preview_netto berekening klopt niet',
        )


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestIntegratieLoonstructuur(common.TransactionCase):
    """
    Tests voor de SR loonstructuur setup:
    - Correcte verwijzing naar structuurtype
    - Structuur aanwezig en actief
    - Salarisregels aanwezig met juiste codes
    """

    def test_sr_structuur_aanwezig(self):
        """De SR loonstructuur moet aanwezig en actief zijn."""
        structuur = self.env.ref(
            'l10n_sr_hr_payroll.sr_payroll_structure', raise_if_not_found=False
        )
        self.assertIsNotNone(structuur,
                             'SR loonstructuur (sr_payroll_structure) niet gevonden')
        self.assertTrue(structuur.active if hasattr(structuur, 'active') else True,
                        'SR loonstructuur is niet actief')

    def test_sr_structuurtype_aanwezig(self):
        """Het SR loonstructuurtype moet aanwezig zijn."""
        struct_type = self.env.ref(
            'l10n_sr_hr_payroll.sr_payroll_structure_type',
            raise_if_not_found=False
        )
        self.assertIsNotNone(struct_type,
                             'SR structuurtype (sr_payroll_structure_type) niet gevonden')

    def test_sr_salarisregels_aanwezig(self):
        """
        De SR salarisregels moeten aanwezig zijn in de structuur.
        Minimaal vereist: SR_LB en SR_AOV.
        """
        structuur = self.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        aanwezige_codes = structuur.rule_ids.mapped('code')

        for code in ('SR_LB', 'SR_AOV'):
            self.assertIn(
                code, aanwezige_codes,
                f'Salarisregel "{code}" ontbreekt in de SR structuur',
            )

    def test_sr_regelparameters_aanwezig(self):
        """
        De SR regelparameters moeten geregistreerd zijn.
        Minimaal vereist: belastingvrij, schijfgrenzen, tarieven.
        """
        verwachte_codes = [
            'SR_BELASTINGVRIJ_JAAR',
            'SR_SCHIJF_1_GRENS',
            'SR_SCHIJF_4_GRENS',
            'SR_TARIEF_1',
            'SR_TARIEF_5',
            'SR_AOV_TARIEF',
        ]
        for code in verwachte_codes:
            param = self.env['hr.rule.parameter'].search(
                [('code', '=', code)], limit=1
            )
            self.assertTrue(
                bool(param),
                f'Regelparameter "{code}" niet gevonden in hr.rule.parameter',
            )
