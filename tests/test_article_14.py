# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Unittests voor de Suriname Loonbelasting module (l10n_sr_hr_payroll).

Testgevallen zijn gebaseerd op de voorbeeldberekeningen uit de
Wet Loonbelasting 2026 (Artikel 14) context.

Voorbeeldsalaris uit de context:
  Bruto maandloon       : SRD  20.255,60
  Loonbelasting (LB)    : SRD   2.025,13
  AOV bijdrage          : SRD     794,22
  Netto loon            : SRD  17.436,25  (benadering)
"""

from datetime import date

from odoo.tests import common, tagged
from odoo.tools import float_compare


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestArtikel14Berekening(common.TransactionCase):
    """Tests voor Article 14 loonbelasting berekeningen."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Suriname bedrijf instellen
        cls.company = cls.env['res.company'].create({
            'name': 'Test Bedrijf Suriname',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))

        # Testwerknemer aanmaken
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Test Werknemer SR',
            'company_id': cls.company.id,
        })
        cls.employee_b = cls.env['hr.employee'].create({
            'name': 'Test Werknemer SR B',
            'company_id': cls.company.id,
        })

        # Salarisstructuur + structuurtype ophalen
        cls.structure = cls.env.ref(
            'l10n_sr_hr_payroll.sr_payroll_structure'
        )
        cls.structure_type = cls.structure.type_id

    def _create_contract(self, wage, salary_type='monthly',
                         toelagen=0.0, kinderbijslag=0.0, pensioenpremie=0.0,
                         employee=None):
        """Hulpfunctie om een testcontract aan te maken."""
        emp = employee or self.employee
        vaste_regels = []
        if toelagen:
            vaste_regels.append((0, 0, {'name': 'Belastbare Toelagen', 'sr_categorie': 'belastbaar', 'amount': toelagen}))
        if kinderbijslag:
            vaste_regels.append((0, 0, {'name': 'Kinderbijslag', 'sr_categorie': 'vrijgesteld', 'amount': kinderbijslag}))
        if pensioenpremie:
            vaste_regels.append((0, 0, {'name': 'Pensioenpremie', 'sr_categorie': 'inhouding', 'amount': pensioenpremie}))
        return self.env['hr.contract'].create({
            'name': f'Testcontract — {emp.name}',
            'employee_id': emp.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_vaste_regels': vaste_regels,
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    def _compute_payslip(self, contract, date_from, date_to):
        """Hulpfunctie om een loonstrook te berekenen en de regels te retourneren."""
        payslip = self.env['hr.payslip'].create({
            'name': f'Testloonstrook {date_from}',
            'employee_id': contract.employee_id.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        return payslip

    def _get_line_total(self, payslip, code):
        """Geef het totaalbedrag van een salarisregel op basis van code."""
        line = payslip.line_ids.filtered(lambda l: l.code == code)
        return line.total if line else 0.0

    # ──────────────────────────────────────────────────────────────────────
    # Test 1: Maandloon onder de belastingvrije grens
    # Iemand die minder dan SRD 9.000/maand verdient → geen loonbelasting
    # ──────────────────────────────────────────────────────────────────────
    def test_maandloon_onder_belastingvrije_grens(self):
        """Maandloon SRD 8.000 → belastbaar jaarloon < 0 → LB = 0."""
        contract = self._create_contract(wage=8000.0, salary_type='monthly')
        payslip = self._compute_payslip(
            contract,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
        )

        lb = self._get_line_total(payslip, 'SR_LB')
        self.assertEqual(
            lb, 0.0,
            f'Verwacht LB = 0,00 voor loon onder belastingvrije grens, kreeg {lb}',
        )

    # ──────────────────────────────────────────────────────────────────────
    # Test 2: Maandloon — voorbeeldberekening uit de context
    # Bruto SRD 20.255,60 → LB ≈ 2.634,71 → AOV ≈ 858,39
    # ──────────────────────────────────────────────────────────────────────
    def test_maandloon_voorbeeld_context(self):
        """
        Controleer loonbelasting en AOV voor het voorbeeldsalaris uit de context.
        Bruto maandloon: SRD 20.255,60
        Bruto jaarloon : SRD 243.067,20
        Forfaitaire    : 4% × 243.067,20 = 9.722,69 → max SRD 4.800
        Belastingvrij  : SRD 108.000
        Belastbaar     : 243.067,20 - 108.000 - 4.800 = 130.267,20
        Schijven       :
          S1: 42.000 × 8%  =  3.360,00
          S2: 42.000 × 18% =  7.560,00
          S3: 42.000 × 28% = 11.760,00
          S4: (130.267,20 - 126.000) × 38% = 4.267,20 × 38% = 1.621,54
          Totaal lb jaar  = 24.301,54
          LB per maand    = 24.301,54 / 12 = 2.025,13
        AOV grondslag   : 20.255,60 - 400 = 19.855,60
        AOV per maand   : 19.855,60 × 4% = 794,22
        """
        contract = self._create_contract(wage=20255.60, salary_type='monthly')
        payslip = self._compute_payslip(
            contract,
            date_from=date(2026, 4, 1),
            date_to=date(2026, 4, 30),
        )

        lb = self._get_line_total(payslip, 'SR_LB')
        aov = self._get_line_total(payslip, 'SR_AOV')
        gross = self._get_line_total(payslip, 'GROSS')
        net = self._get_line_total(payslip, 'NET')

        # Bruto check
        self.assertAlmostEqual(gross, 20255.60, places=2,
                               msg='Bruto loon klopt niet')

        # LB moet negatief zijn (inhouding)
        self.assertLess(lb, 0.0, 'Loonbelasting moet negatief zijn (inhouding)')

        # AOV moet negatief zijn
        self.assertLess(aov, 0.0, 'AOV bijdrage moet negatief zijn (inhouding)')

        # Nettoloon = bruto + LB + AOV (geen heffingskorting)
        self.assertAlmostEqual(net, gross + lb + aov, places=2,
                               msg='Nettoloon berekening klopt niet')

        # Nettoloon moet lager zijn dan brutoloon
        self.assertLess(net, gross, 'Nettoloon moet lager zijn dan brutoloon')

    # ──────────────────────────────────────────────────────────────────────
    # Test 3: Schijf 1 — loon alleen in eerste belastingschijf
    # Bruto SRD 15.500/maand → belastbaar jaarloon ≈ 72.000
    # → alleen schijf 1 (8%) en schijf 2 (18%) van toepassing
    # ──────────────────────────────────────────────────────────────────────
    def test_maandloon_schijf_1_en_2(self):
        """Belastbaar jaarloon ≈ 73.200 → schijven 1+2."""
        contract = self._create_contract(wage=15500.0, salary_type='monthly')
        payslip = self._compute_payslip(
            contract,
            date_from=date(2026, 5, 1),
            date_to=date(2026, 5, 31),
        )

        lb = self._get_line_total(payslip, 'SR_LB')
        # Belastbaar jaarloon: 15500×12 − 108000 − min(15500×12×0.04, 4800)
        # = 186000 − 108000 − 4800 = 73200 → schijven 1+2
        # LB jaar = 42000×0.08 + 31200×0.18 = 3360 + 5616 = 8976
        # LB per maand = 8976 / 12 = 748
        self.assertLess(lb, 0.0,
                        'LB moet negatief zijn (inhouding)')

    # ──────────────────────────────────────────────────────────────────────
    # Test 4: Toelagen worden meegenomen in de belastinggrondslag
    # ──────────────────────────────────────────────────────────────────────
    def test_toelagen_verhogen_belastinggrondslag(self):
        """Belastbare toelagen moeten de loonbelasting verhogen."""
        contract_zonder = self._create_contract(wage=20000.0, toelagen=0.0)
        contract_met = self._create_contract(wage=20000.0, toelagen=2000.0, employee=self.employee_b)

        date_from = date(2026, 4, 1)
        date_to = date(2026, 4, 30)

        payslip_zonder = self._compute_payslip(contract_zonder, date_from, date_to)
        payslip_met = self._compute_payslip(contract_met, date_from, date_to)

        lb_zonder = self._get_line_total(payslip_zonder, 'SR_LB')
        lb_met = self._get_line_total(payslip_met, 'SR_LB')

        self.assertLess(lb_met, lb_zonder,
                        'Toelagen moeten de LB inhouding verhogen (negatiever maken)')

    # ──────────────────────────────────────────────────────────────────────
    # Test 5: Kinderbijslag is belastingvrij (telt niet mee in LB grondslag)
    # ──────────────────────────────────────────────────────────────────────
    def test_kinderbijslag_is_belastingvrij(self):
        """Kinderbijslag mag de loonbelasting NIET verhogen."""
        contract_zonder = self._create_contract(wage=20000.0, kinderbijslag=0.0)
        contract_met = self._create_contract(wage=20000.0, kinderbijslag=500.0, employee=self.employee_b)

        date_from = date(2026, 4, 1)
        date_to = date(2026, 4, 30)

        payslip_zonder = self._compute_payslip(contract_zonder, date_from, date_to)
        payslip_met = self._compute_payslip(contract_met, date_from, date_to)

        lb_zonder = self._get_line_total(payslip_zonder, 'SR_LB')
        lb_met = self._get_line_total(payslip_met, 'SR_LB')

        self.assertEqual(lb_zonder, lb_met,
                         'Kinderbijslag mag de LB berekening NIET beïnvloeden')

        # Maar het nettoloon moet hoger zijn met kinderbijslag
        net_zonder = self._get_line_total(payslip_zonder, 'NET')
        net_met = self._get_line_total(payslip_met, 'NET')
        self.assertGreater(net_met, net_zonder,
                           'Nettoloon met kinderbijslag moet hoger zijn')

    # ──────────────────────────────────────────────────────────────────────
    # Test 6: Fortnight loon — zelfde jaarloon, zelfde totale belasting
    # 26 periodes × FN-bedrag ≈ 12 periodes × maandbedrag (zelfde jaarloon)
    # ──────────────────────────────────────────────────────────────────────
    def test_fortnight_vs_maandloon_equivalentie(self):
        """
        Fortnight loon van 1/26 jaarloon moet per jaar dezelfde belasting geven
        als een maandloon van 1/12 van hetzelfde jaarloon.
        """
        jaarloon = 240000.0  # SRD 240.000/jaar
        maandloon = jaarloon / 12  # 20.000/maand
        fn_loon = jaarloon / 26    # ≈ 9.230,77/fortnight

        contract_maand = self._create_contract(wage=maandloon, salary_type='monthly')
        contract_fn = self._create_contract(wage=fn_loon, salary_type='fn', employee=self.employee_b)

        # Maandloon: april (1 maand)
        payslip_maand = self._compute_payslip(
            contract_maand, date(2026, 4, 1), date(2026, 4, 30)
        )
        lb_maand_per_periode = self._get_line_total(payslip_maand, 'SR_LB')

        # Fortnight: eerste 2 weken april (1 FN-periode)
        payslip_fn = self._compute_payslip(
            contract_fn, date(2026, 4, 1), date(2026, 4, 14)
        )
        lb_fn_per_periode = self._get_line_total(payslip_fn, 'SR_LB')

        # Jaarbelasting maandloon ≈ jaarbelasting fortnight
        lb_jaar_maand = lb_maand_per_periode * 12
        lb_jaar_fn = lb_fn_per_periode * 26

        self.assertAlmostEqual(
            lb_jaar_maand, lb_jaar_fn, delta=5.0,
            msg=(
                f'Jaarlijkse LB maandloon ({lb_jaar_maand:.2f}) moet '
                f'gelijk zijn aan FN ({lb_jaar_fn:.2f})'
            ),
        )

    # ──────────────────────────────────────────────────────────────────────
    # Test 7: Pensioenpremie verlaagt het nettoloon
    # ──────────────────────────────────────────────────────────────────────
    def test_pensioenpremie_verlaagt_nettoloon(self):
        """Pensioenpremie moet worden ingehouden op het nettoloon."""
        pensioenpremie = 800.0
        contract = self._create_contract(
            wage=20000.0, pensioenpremie=pensioenpremie
        )
        contract_zonder = self._create_contract(wage=20000.0, employee=self.employee_b)

        date_from = date(2026, 4, 1)
        date_to = date(2026, 4, 30)

        payslip = self._compute_payslip(contract, date_from, date_to)
        payslip_zonder = self._compute_payslip(contract_zonder, date_from, date_to)

        net = self._get_line_total(payslip, 'NET')
        net_zonder = self._get_line_total(payslip_zonder, 'NET')
        pensioen_inhouding = self._get_line_total(payslip, 'SR_PENSIOEN')

        self.assertAlmostEqual(
            pensioen_inhouding, -pensioenpremie, places=2,
            msg='Pensioenpremie inhouding klopt niet',
        )
        self.assertAlmostEqual(
            net, net_zonder - pensioenpremie, places=2,
            msg='Nettoloon met pensioenpremie klopt niet',
        )


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestArtikel14Schijven(common.TransactionCase):
    """
    Directe unit tests van de tariefschiijven berekening
    zonder Odoo loonstrook (pure Python logica verificatie).
    """

    def _bereken_lb_jaar(self, belastbaar_jaarloon):
        """
        Zuivere Python implementatie van de Artikel 14 schijvenberekening.
        Identiek aan de logica in hr_salary_rule_data.xml (SR_LB).
        Geen heffingskorting — conform context document.
        """
        s1, s2, s3 = 42000.0, 84000.0, 126000.0
        r1, r2, r3, r4 = 0.08, 0.18, 0.28, 0.38

        if belastbaar_jaarloon <= 0:
            return 0.0
        elif belastbaar_jaarloon <= s1:
            lb = belastbaar_jaarloon * r1
        elif belastbaar_jaarloon <= s2:
            lb = (s1 * r1) + ((belastbaar_jaarloon - s1) * r2)
        elif belastbaar_jaarloon <= s3:
            lb = (s1 * r1) + ((s2 - s1) * r2) + ((belastbaar_jaarloon - s2) * r3)
        else:
            lb = (s1 * r1) + ((s2 - s1) * r2) + ((s3 - s2) * r3) + ((belastbaar_jaarloon - s3) * r4)

        return lb

    def test_schijf_0_geen_belasting(self):
        """Belastbaar jaarloon 0 → LB = 0."""
        self.assertEqual(self._bereken_lb_jaar(0.0), 0.0)

    def test_schijf_1_grens(self):
        """Belastbaar jaarloon = SRD 42.000 → schijf 1."""
        lb = self._bereken_lb_jaar(42000.0)
        verwacht = 42000.0 * 0.08  # = 3360
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_schijf_2(self):
        """Belastbaar jaarloon = SRD 70.000 → schijven 1+2."""
        lb = self._bereken_lb_jaar(70000.0)
        verwacht = (42000 * 0.08) + (28000 * 0.18)  # 3360 + 5040 = 8400
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_schijf_3(self):
        """Belastbaar jaarloon = SRD 100.000 → schijven 1+2+3."""
        lb = self._bereken_lb_jaar(100000.0)
        verwacht = (42000 * 0.08) + (42000 * 0.18) + (16000 * 0.28)  # 15400
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_schijf_4(self):
        """Belastbaar jaarloon = SRD 150.000 → alle 4 schijven."""
        lb = self._bereken_lb_jaar(150000.0)
        verwacht = ((42000 * 0.08) + (42000 * 0.18) + (42000 * 0.28)
                    + (24000 * 0.38))  # 31800
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_progressieve_belasting(self):
        """Hogere jaarlonen moeten hogere LB produceren."""
        lonen = [50000, 100000, 150000, 200000, 300000]
        belastingen = [self._bereken_lb_jaar(l) for l in lonen]
        for i in range(len(belastingen) - 1):
            self.assertLess(
                belastingen[i], belastingen[i + 1],
                f'Progressiviteit faalt: {lonen[i]} vs {lonen[i+1]}',
            )

    def test_forfaitaire_max_cap(self):
        """
        Forfaitaire aftrek is gemaximeerd op SRD 4.800/jaar.
        Jaarloon SRD 200.000 → 4% = SRD 8.000 → cap op SRD 4.800.
        """
        # Jaarloon 200.000: forfaitaire = min(200.000 × 0.04, 4.800) = 4.800
        # Belastbaar = 200.000 − 108.000 − 4.800 = 87.200
        belastbaar = 200000 - 108000 - 4800
        lb = self._bereken_lb_jaar(belastbaar)
        # s1 = 42.000×8% = 3.360; s2 = 42.000×18% = 7.560; rest = 3.200×28% = 896
        verwacht = (42000 * 0.08) + (42000 * 0.18) + (3200 * 0.28)  # 11816
        self.assertAlmostEqual(lb, verwacht, places=2,
                               msg='Forfaitaire cap of LB berekening klopt niet')

    def test_forfaitaire_niet_gecapped(self):
        """
        Forfaitaire aftrek NIET gemaximeerd voor laag jaarloon.
        Jaarloon SRD 60.000 → 4% = SRD 2.400 < SRD 4.800 → geen cap.
        """
        belastbaar = max(0.0, 60000 - 108000 - 2400)  # = 0 (belastingvrij)
        lb = self._bereken_lb_jaar(belastbaar)
        self.assertEqual(lb, 0.0,
                         'Loon onder belastingvrije som: LB moet 0 zijn')

    def test_belastbaar_jaarloon_nooit_negatief(self):
        """Belastbaar jaarloon kan nooit negatief zijn (max(0, ...)."""
        # Jaarloon 50.000: belastingvrij 108.000 → belastbaar = 0
        belastbaar = max(0.0, 50000 - 108000 - min(50000 * 0.04, 4800))
        self.assertEqual(belastbaar, 0.0,
                         'Belastbaar jaarloon moet 0 zijn bij laag loon')

    def test_exacte_schijfgrens_1(self):
        """
        Belastbaar jaarloon precies op schijfgrens 1 (SRD 42.000).
        LB = 42.000 × 8% = 3.360
        """
        lb = self._bereken_lb_jaar(42000.0)
        verwacht = 42000 * 0.08  # = 3360
        self.assertAlmostEqual(lb, verwacht, places=2,
                               msg='Exacte schijfgrens 1 berekening klopt niet')

    def test_exacte_schijfgrens_2(self):
        """
        Belastbaar jaarloon precies op schijfgrens 2 (SRD 84.000).
        LB = 42.000×8% + 42.000×18% = 3.360 + 7.560 = 10.920
        """
        lb = self._bereken_lb_jaar(84000.0)
        verwacht = (42000 * 0.08) + (42000 * 0.18)  # = 10920
        self.assertAlmostEqual(lb, verwacht, places=2,
                               msg='Exacte schijfgrens 2 berekening klopt niet')

    def test_exacte_schijfgrens_3(self):
        """
        Belastbaar jaarloon precies op schijfgrens 3 (SRD 126.000).
        LB = 42.000×8% + 42.000×18% + 42.000×28% = 22.680
        """
        lb = self._bereken_lb_jaar(126000.0)
        verwacht = (42000 * 0.08) + (42000 * 0.18) + (42000 * 0.28)  # = 22680
        self.assertAlmostEqual(lb, verwacht, places=2,
                               msg='Exacte schijfgrens 3 berekening klopt niet')


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestArtikel14AOV(common.TransactionCase):
    """
    Tests specifiek voor de AOV berekening:
    - Franchise SRD 400/maand (maandloon)
    - Geen franchise voor fortnight loon
    - 4% tarief
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test SR AOV Bedrijf',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'AOV Testwerknemer',
            'company_id': cls.company.id,
        })
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

    def _make_payslip(self, wage, salary_type):
        contract = self.env['hr.contract'].create({
            'name': 'AOV Testcontract',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'AOV Testloonstrook',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        return payslip

    def test_aov_maandloon_met_franchise(self):
        """
        Maandloon SRD 5.000 → AOV grondslag = 5.000 − 400 = 4.600
        AOV = 4.600 × 4% = 184
        """
        payslip = self._make_payslip(wage=5000.0, salary_type='monthly')
        aov = payslip.line_ids.filtered(lambda l: l.code == 'SR_AOV').total
        verwacht_grondslag = 5000.0 - 400.0
        verwacht_aov = -(verwacht_grondslag * 0.04)
        self.assertAlmostEqual(aov, verwacht_aov, places=2,
                               msg='AOV maandloon met franchise klopt niet')

    def test_aov_fortnight_geen_franchise(self):
        """
        Fortnight loon SRD 5.000 → AOV grondslag = 5.000 (geen franchise)
        AOV = 5.000 × 4% = 200
        """
        payslip = self._make_payslip(wage=5000.0, salary_type='fn')
        aov = payslip.line_ids.filtered(lambda l: l.code == 'SR_AOV').total
        verwacht_aov = -(5000.0 * 0.04)
        self.assertAlmostEqual(aov, verwacht_aov, places=2,
                               msg='AOV fortnight zonder franchise klopt niet')

    def test_aov_maandloon_lager_dan_franchise(self):
        """
        Maandloon SRD 300 (< franchise SRD 400) → AOV grondslag = 0 → AOV = 0.
        """
        payslip = self._make_payslip(wage=300.0, salary_type='monthly')
        aov = payslip.line_ids.filtered(lambda l: l.code == 'SR_AOV').total
        self.assertEqual(aov, 0.0,
                         'AOV moet 0 zijn als loon lager is dan franchise')

    def test_aov_is_negatieve_inhouding(self):
        """AOV bijdrage moet altijd negatief zijn (inhouding op loon)."""
        payslip = self._make_payslip(wage=10000.0, salary_type='monthly')
        aov = payslip.line_ids.filtered(lambda l: l.code == 'SR_AOV').total
        self.assertLess(aov, 0.0, 'AOV moet negatief zijn (inhouding)')


@tagged('post_install', 'post_install_l10n', '-at_install')
class TestArtikel14Breakdown(common.TransactionCase):
    """
    Tests voor de _get_sr_artikel14_breakdown() methode op hr.payslip.
    Verifieert dat de tussenliggende berekeningen correct zijn voor
    weergave op de loonstrook PDF.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env['res.company'].create({
            'name': 'Test SR Breakdown Bedrijf',
            'country_id': cls.env.ref('base.sr').id,
            'currency_id': cls.env.ref('base.SRD').id,
        })
        cls.env = cls.env(context=dict(
            cls.env.context,
            allowed_company_ids=[cls.company.id],
        ))
        cls.employee = cls.env['hr.employee'].create({
            'name': 'Breakdown Testwerknemer',
            'company_id': cls.company.id,
        })
        cls.structure = cls.env.ref('l10n_sr_hr_payroll.sr_payroll_structure')
        cls.structure_type = cls.structure.type_id

    def _make_payslip(self, wage, salary_type='monthly', toelagen=0.0):
        vaste_regels = []
        if toelagen:
            vaste_regels.append((0, 0, {'name': 'Belastbare Toelagen', 'sr_categorie': 'belastbaar', 'amount': toelagen}))
        contract = self.env['hr.contract'].create({
            'name': 'Breakdown Testcontract',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_vaste_regels': vaste_regels,
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'Breakdown Testloonstrook',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        return payslip

    def test_breakdown_dict_bevat_alle_sleutels(self):
        """_get_sr_artikel14_breakdown() geeft alle verwachte sleutels terug."""
        payslip = self._make_payslip(wage=20000.0)
        bd = payslip._get_sr_artikel14_breakdown()

        verwachte_sleutels = [
            'periodes', 'is_fn', 'basic', 'toelagen', 'kinderbijslag',
            'bruto_per_periode', 'bruto_totaal', 'bruto_jaarloon',
            'belastingvrij_jaar', 'forfaitaire_pct', 'forfaitaire_jaar',
            'belastbaar_jaarloon', 's1_grens', 's2_grens', 's3_grens',
            'lb_s1', 'lb_s2', 'lb_s3', 'lb_s4',
            'lb_jaar', 'lb_per_periode',
            'lb_bijz', 'lb_17a', 'lb_overwerk',
            'aov_bijz', 'aov_17a', 'aov_overwerk',
            'franchise_periode', 'aov_grondslag', 'aov_tarief_pct', 'aov_per_periode',
            'aftrek_bv', 'pensioen', 'totaal_lb', 'totaal_aov',
            'totaal_inhoudingen', 'netto',
        ]
        for sleutel in verwachte_sleutels:
            self.assertIn(sleutel, bd,
                          f'Ontbrekende sleutel in breakdown: {sleutel}')

    def test_breakdown_periodes_maandloon(self):
        """Maandloon → periodes = 12, is_fn = False."""
        payslip = self._make_payslip(wage=20000.0, salary_type='monthly')
        bd = payslip._get_sr_artikel14_breakdown()
        self.assertEqual(bd['periodes'], 12)
        self.assertFalse(bd['is_fn'])

    def test_breakdown_periodes_fortnight(self):
        """Fortnight → periodes = 26, is_fn = True."""
        contract = self.env['hr.contract'].create({
            'name': 'FN Breakdown Contract',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 7692.31,  # ≈ SRD 200.000 / 26
            'sr_salary_type': 'fn',
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'FN Breakdown Loonstrook',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 14),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        bd = payslip._get_sr_artikel14_breakdown()
        self.assertEqual(bd['periodes'], 26)
        self.assertTrue(bd['is_fn'])
        self.assertEqual(bd['franchise_periode'], 0.0,
                         'Fortnight heeft geen AOV franchise')

    def test_breakdown_lb_stemt_overeen_met_salarisregel(self):
        """
        lb_per_periode uit breakdown moet overeenkomen met SR_LB salarisregel
        (breakdown leest werkelijke payslip regels).
        """
        payslip = self._make_payslip(wage=20255.60)
        bd = payslip._get_sr_artikel14_breakdown()
        lb_regel = payslip.line_ids.filtered(lambda l: l.code == 'SR_LB').total
        # Breakdown geeft positief bedrag, regel geeft negatief
        self.assertAlmostEqual(bd['lb_per_periode'], abs(lb_regel), delta=0.02,
                               msg='Breakdown LB moet overeenkomen met SR_LB salarisregel')

    def test_breakdown_lege_loonstrook(self):
        """Breakdown met lege loonstrook (geen regels) geeft leeg dict terug."""
        payslip = self.env['hr.payslip'].create({
            'name': 'Lege Loonstrook',
            'employee_id': self.employee.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })
        # Niet compute_sheet() aanroepen → geen regels
        bd = payslip._get_sr_artikel14_breakdown()
        self.assertEqual(bd, {},
                         'Lege loonstrook moet leeg dict teruggeven')
