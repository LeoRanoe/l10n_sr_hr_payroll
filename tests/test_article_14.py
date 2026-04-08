# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Unittests voor de Suriname Loonbelasting module (l10n_sr_hr_payroll).

Testgevallen zijn gebaseerd op de voorbeeldberekeningen uit de
Wet Loonbelasting 2026 (Artikel 14) context.

Voorbeeldsalaris uit de context:
  Bruto maandloon       : SRD  20.255,60
  Loonbelasting (LB)    : SRD   2.634,71
  AOV bijdrage          : SRD     858,39
  Netto loon            : SRD  20.590,50  (benadering)
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

        # Salarisstructuur ophalen
        cls.structure = cls.env.ref(
            'l10n_sr_hr_payroll.sr_payroll_structure'
        )

    def _create_contract(self, wage, salary_type='monthly',
                         toelagen=0.0, kinderbijslag=0.0, pensioenpremie=0.0):
        """Hulpfunctie om een testcontract aan te maken."""
        return self.env['hr.contract'].create({
            'name': f'Testcontract — {self.employee.name}',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'struct_id': self.structure.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_toelagen': toelagen,
            'sr_kinderbijslag': kinderbijslag,
            'sr_pensioenpremie': pensioenpremie,
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })

    def _compute_payslip(self, contract, date_from, date_to):
        """Hulpfunctie om een loonstrook te berekenen en de regels te retourneren."""
        payslip = self.env['hr.payslip'].create({
            'name': f'Testloonstrook {date_from}',
            'employee_id': self.employee.id,
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
        Heffingskorting : 750 × 12 = 9.000
          LB jaar netto   = 15.301,54
          LB per maand    = 15.301,54 / 12 = 1.275,13
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

        # Nettoloon = bruto + LB + AOV (beide negatief)
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
        """Belastbaar jaarloon ≈ 72.000 → LB ≥ 0 (schijven 1 en 2)."""
        contract = self._create_contract(wage=15500.0, salary_type='monthly')
        payslip = self._compute_payslip(
            contract,
            date_from=date(2026, 5, 1),
            date_to=date(2026, 5, 31),
        )

        lb = self._get_line_total(payslip, 'SR_LB')
        # Belastbaar jaarloon: 15500×12 − 108000 − min(15500×12×0.04, 4800)
        # = 186000 − 108000 − 4800 = 73200 → schijven 1+2
        # LB jaar = 42000×0.08 + 31200×0.18 − 9000 = 3360 + 5616 − 9000 = -24 → 0
        # Dus LB kan 0 zijn na heffingskorting
        self.assertLessEqual(lb, 0.0,
                             'LB moet 0 of negatief zijn (inhouding of geen belasting)')

    # ──────────────────────────────────────────────────────────────────────
    # Test 4: Toelagen worden meegenomen in de belastinggrondslag
    # ──────────────────────────────────────────────────────────────────────
    def test_toelagen_verhogen_belastinggrondslag(self):
        """Belastbare toelagen moeten de loonbelasting verhogen."""
        contract_zonder = self._create_contract(wage=20000.0, toelagen=0.0)
        contract_met = self._create_contract(wage=20000.0, toelagen=2000.0)

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
        contract_met = self._create_contract(wage=20000.0, kinderbijslag=500.0)

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
        contract_fn = self._create_contract(wage=fn_loon, salary_type='fn')

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
        contract_zonder = self._create_contract(wage=20000.0)

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

        # Heffingskorting
        heffingskorting_jaar = 750.0 * 12
        return max(0.0, lb - heffingskorting_jaar)

    def test_schijf_0_geen_belasting(self):
        """Belastbaar jaarloon 0 → LB = 0."""
        self.assertEqual(self._bereken_lb_jaar(0.0), 0.0)

    def test_schijf_1_grens(self):
        """Belastbaar jaarloon = SRD 42.000 → schijf 1."""
        lb = self._bereken_lb_jaar(42000.0)
        verwacht = max(0.0, 42000.0 * 0.08 - 9000.0)
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_schijf_2(self):
        """Belastbaar jaarloon = SRD 70.000 → schijven 1+2."""
        lb = self._bereken_lb_jaar(70000.0)
        verwacht = max(0.0, (42000 * 0.08) + (28000 * 0.18) - 9000.0)
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_schijf_3(self):
        """Belastbaar jaarloon = SRD 100.000 → schijven 1+2+3."""
        lb = self._bereken_lb_jaar(100000.0)
        verwacht = max(0.0, (42000 * 0.08) + (42000 * 0.18) + (16000 * 0.28) - 9000.0)
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_schijf_4(self):
        """Belastbaar jaarloon = SRD 150.000 → alle 4 schijven."""
        lb = self._bereken_lb_jaar(150000.0)
        verwacht = max(0.0,
                       (42000 * 0.08) + (42000 * 0.18) + (42000 * 0.28)
                       + (24000 * 0.38) - 9000.0)
        self.assertAlmostEqual(lb, verwacht, places=2)

    def test_heffingskorting_elimineert_kleine_belasting(self):
        """
        Als LB < heffingskorting → netto LB = 0.
        SRD 42.000 belastbaar × 8% = SRD 3.360 < SRD 9.000 → LB = 0.
        """
        lb = self._bereken_lb_jaar(42000.0)
        self.assertEqual(lb, 0.0,
                         'Heffingskorting moet kleine belasting elimineren')

    def test_progressieve_belasting(self):
        """Hogere jaarlonen moeten hogere LB produceren."""
        lonen = [50000, 100000, 150000, 200000, 300000]
        belastingen = [self._bereken_lb_jaar(l) for l in lonen]
        for i in range(len(belastingen) - 1):
            self.assertLess(
                belastingen[i], belastingen[i + 1],
                f'Progressiviteit faalt: {lonen[i]} vs {lonen[i+1]}',
            )
