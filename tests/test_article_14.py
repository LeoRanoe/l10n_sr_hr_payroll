# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Unittests voor de Suriname Loonbelasting module (l10n_sr_hr_payroll).

Testgevallen zijn gebaseerd op de voorbeeldberekeningen uit de
Wet Loonbelasting 2026 (Artikel 14) context.

De broncontext bevat intern tegenstrijdige verwijzingen naar
heffingskorting, maar de formele Art. 14 formules trekken die niet af.
De runtime en regressietests volgen daarom de expliciete formuleblokken.
"""

from datetime import date

from odoo.tests import common, tagged
from odoo.tools import float_compare

from odoo.addons.l10n_sr_hr_payroll.models import sr_artikel14_calculator as calc


def _fn_period_2026_7():
    return date(2026, 3, 26), date(2026, 4, 8)


def _fn_period_2026_10():
    return date(2026, 5, 7), date(2026, 5, 20)


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
                         employee=None, aantal_kinderen=None):
        """Hulpfunctie om een testcontract aan te maken."""
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
            'name': f'Testcontract — {emp.name}',
            'employee_id': emp.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': wage,
            'sr_salary_type': salary_type,
            'sr_aantal_kinderen': aantal_kinderen if aantal_kinderen is not None else (4 if kinderbijslag else 0),
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

    def test_context_rekenvoorbeeld_volgt_formule_zonder_heffingskorting(self):
        """Het bronvoorbeeld volgt de expliciete Art. 14 formule zonder HK-afslag."""
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 4, 30))

        salaris = 20255.60
        kinderbijslag = 500.00
        belastb_toelagen = 1300.00
        vr_geneesk_beh = 16.67
        fisc_aftrek_kb = 212.50

        bruto_per_maand = (
            salaris + kinderbijslag + belastb_toelagen + vr_geneesk_beh - fisc_aftrek_kb
        )
        result = calc.calculate_lb(bruto_per_maand, 12, params)

        self.assertAlmostEqual(bruto_per_maand, 21859.77, places=2)
        self.assertAlmostEqual(result['forfaitaire_jaar'], 4800.00, places=2)
        self.assertAlmostEqual(result['belastbaar_jaar'], 149517.24, places=2)
        self.assertAlmostEqual(result['lb_per_periode'], 2634.71, places=2)
        self.assertAlmostEqual(result['aov_per_periode'], 858.39, places=2)

        # De bron noemt HK elders, maar de formele LB-formule vermindert die niet.
        self.assertAlmostEqual(result['lb_per_periode'], result['lb_jaar'] / 12, places=2)

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
    # Bruto SRD 20.255,60 → LB na HK ≈ 4.695,13 → AOV ≈ 794,22 → Netto ≈ 14.766,25
    # ──────────────────────────────────────────────────────────────────────
    def test_maandloon_voorbeeld_context(self):
        """
        Controleer loonbelasting en AOV voor het voorbeeldsalaris uit de context.
        Bruto maandloon: SRD 20.255,60
                Bruto jaarloon : SRD 243.067,20
                Forfaitaire    : 4% × 243.067,20 = 9.722,69 → max SRD 4.800
                Belastingvrij  : SRD 108.000 (Art. 13)
                Belastbaar     : 243.067,20 - 4.800 - 108.000 = 130.267,20
        Schijven       :
          S1: 42.000 × 8%  =  3.360,00
          S2: 42.000 × 18% =  7.560,00
          S3: 42.000 × 28% = 11.760,00
                    S4: (130.267,20 - 126.000) × 38% = 4.267,20 × 38% = 1.621,54
                    Totaal lb jaar  = 24.301,54
                    LB per maand vóór HK = 24.301,54 / 12 = 2.025,13
                    Heffingskorting = 750,00
                    In te houden LB = 2.025,13 - 750,00 = 1.275,13
        AOV grondslag   : 20.255,60 - 400 = 19.855,60
        AOV per maand   : 19.855,60 × 4% = 794,22
        Nettoloon       : 20.255,60 - 1.275,13 - 794,22 = 18.186,25
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

        hk = self._get_line_total(payslip, 'SR_HK')

        # Heffingskorting verlaagt SR_LB; nettoloon volgt daarna bruto + LB + AOV.
        self.assertAlmostEqual(hk, 750.0, places=2,
                       msg='Heffingskorting moet exact SRD 750 per maand zijn')
        self.assertAlmostEqual(net, gross + lb + aov, places=2,
                               msg='Nettoloon berekening klopt niet')

        self.assertAlmostEqual(abs(lb), 1275.13, places=2,
                       msg='LB voor het referentiesalaris wijkt af (belastingvrij Art.13 = SRD 108.000)')
        self.assertAlmostEqual(abs(aov), 794.22, places=2,
                       msg='AOV voor het referentiesalaris wijkt af van het 2026 rekenvoorbeeld')
        self.assertAlmostEqual(net, 18186.25, places=2,
                       msg='Nettoloon voor het referentiesalaris moet tot op de cent kloppen')

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
        payslip_fn = self._compute_payslip(contract_fn, *_fn_period_2026_7())
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

    def test_tax_bracket_html_toont_correcte_grenzen(self):
        """De contractreferentie moet expliciete schijfranges en de open bovengrens tonen."""
        params = calc.fetch_params_from_rule_parameter(self.env, date(2026, 4, 30))
        html = calc.generate_tax_bracket_html(params)

        self.assertIn('t/m SRD 42.000', html)
        self.assertIn('SRD 42.001 – SRD 84.000', html)
        self.assertIn('SRD 84.001 – SRD 126.000', html)
        self.assertIn('Boven SRD 126.000', html)


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
        date_from = date(2026, 5, 1)
        date_to = date(2026, 5, 31)
        if salary_type == 'fn':
            date_from, date_to = _fn_period_2026_10()
        payslip = self.env['hr.payslip'].create({
            'name': 'AOV Testloonstrook',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
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
        date_from = date(2026, 5, 1)
        date_to = date(2026, 5, 31)
        if salary_type == 'fn':
            date_from, date_to = _fn_period_2026_10()
        payslip = self.env['hr.payslip'].create({
            'name': 'Breakdown Testloonstrook',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date_from,
            'date_to': date_to,
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        return payslip

    def test_breakdown_dict_bevat_alle_sleutels(self):
        """_get_sr_artikel14_breakdown() geeft alle verwachte sleutels terug."""
        payslip = self._make_payslip(wage=20000.0)
        bd = payslip._get_sr_artikel14_breakdown()

        verwachte_sleutels = [
            'periodes', 'is_fn', 'fn_period_label', 'fn_period_indicator',
            'payslip_layout', 'payslip_layout_label',
            'period_title', 'employee_reference', 'employment_start_date', 'bank_account_number', 'bank_name', 'hourly_wage',
            'basic', 'toelagen', 'kinderbijslag',
            'bruto_per_periode', 'bruto_totaal', 'bruto_jaarloon',
            'grondslag_belasting_per_periode', 'grondslag_belasting_jaar',
            'belastingvrij_jaar', 'forfaitaire_pct', 'forfaitaire_per_periode', 'forfaitaire_jaar',
            'forfaitaire_max_per_periode',
            'belastbaar_jaarloon', 's1_grens', 's2_grens', 's3_grens',
            'lb_s1', 'lb_s2', 'lb_s3', 'lb_s4',
            'tax_brackets',
            'lb_jaar', 'lb_per_periode',
            'lb_bijz', 'lb_17a', 'lb_overwerk',
            'aov_bijz', 'aov_17a', 'aov_overwerk',
            'adjusted_bruto_per_periode', 'franchise_periode', 'aov_grondslag', 'aov_tarief_pct', 'aov_per_periode',
            'aftrek_bv', 'heffingskorting', 'pensioen', 'contract_inhoudingen', 'input_inhoudingen',
            'earnings_lines', 'deductions_lines', 'summary_cards',
            'payslip_line_rows', 'belasting_line_rows',
            'display_debit_total', 'display_credit_total', 'display_net_total',
            'belasting_paid_total', 'belasting_tax_total', 'belasting_aov_total',
            'totaal_lb', 'totaal_aov',
            'totaal_inhoudingen', 'netto',
        ]
        for sleutel in verwachte_sleutels:
            self.assertIn(sleutel, bd,
                          f'Ontbrekende sleutel in breakdown: {sleutel}')

    def test_breakdown_bevat_report_helper_lijsten(self):
        """Report helpers moeten voldoende data geven voor eenvoudige layouts."""
        payslip = self._make_payslip(wage=20000.0)
        bd = payslip._get_sr_artikel14_breakdown()

        self.assertEqual(bd['payslip_layout'], 'employee_simple')
        self.assertEqual(bd['payslip_layout_label'], 'Klassiek Debet / Credit')
        self.assertTrue(any(line['name'] == 'Salaris' for line in bd['earnings_lines']))
        self.assertTrue(any(card['label'] == 'Netto loon' for card in bd['summary_cards']))
        self.assertFalse(any(card['label'] == 'Heffingskorting' for card in bd['summary_cards']))
        self.assertTrue(any(row['name'] == 'SALARIS' for row in bd['payslip_line_rows']))
        self.assertIsInstance(bd['display_debit_total'], float)

    def test_breakdown_toont_andere_inhoudingen_als_generieke_nettopost(self):
        """Geaggregeerde contractinhoudingen moeten generiek als andere inhoudingen worden gelabeld."""
        contract = self.env['hr.contract'].create({
            'name': 'Breakdown Netto Inhouding Testcontract',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 20000.0,
            'sr_salary_type': 'monthly',
            'sr_vaste_regels': [(0, 0, {
                'name': 'Ziektekostenpremie',
                'sr_categorie': 'inhouding',
                'amount': 150.0,
            })],
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'Breakdown Netto Inhouding Testloonstrook',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()

        bd = payslip._get_sr_artikel14_breakdown()
        inhouding_row = next(row for row in bd['payslip_line_rows'] if row['code'] == 'SR_PENSIOEN')

        self.assertEqual(inhouding_row['name'], 'ANDERE INHOUDINGEN')
        self.assertTrue(any(line['name'] == 'Andere inhoudingen' for line in bd['deductions_lines']))

    def test_breakdown_aov_basis_toont_aftrek_bv_voor_franchise(self):
        """AOV weergave moet eerst Art. 10f aftrek verwerken en daarna pas de franchise."""
        contract = self.env['hr.contract'].create({
            'name': 'Breakdown AOV Aftrek Testcontract',
            'employee_id': self.employee.id,
            'company_id': self.company.id,
            'structure_type_id': self.structure_type.id,
            'wage': 5000.0,
            'sr_salary_type': 'monthly',
            'sr_vaste_regels': [(0, 0, {
                'type_id': self.env.ref('l10n_sr_hr_payroll.sr_line_type_pensioen').id,
                'amount': 1000.0,
            })],
            'date_start': date(2026, 1, 1),
            'state': 'open',
        })
        payslip = self.env['hr.payslip'].create({
            'name': 'Breakdown AOV Aftrek Testloonstrook',
            'employee_id': self.employee.id,
            'contract_id': contract.id,
            'struct_id': self.structure.id,
            'date_from': date(2026, 5, 1),
            'date_to': date(2026, 5, 31),
            'company_id': self.company.id,
        })
        payslip.compute_sheet()

        bd = payslip._get_sr_artikel14_breakdown()

        self.assertAlmostEqual(bd['bruto_per_periode'], 5000.0, places=2)
        self.assertAlmostEqual(bd['adjusted_bruto_per_periode'], 4000.0, places=2)
        self.assertAlmostEqual(bd['franchise_periode'], 400.0, places=2)
        self.assertAlmostEqual(bd['aov_grondslag'], 3600.0, places=2)
        self.assertAlmostEqual(bd['aov_per_periode'], 144.0, places=2)

    def test_payslip_layout_default_volgt_config_parameter(self):
        """Nieuwe loonstroken moeten de geconfigureerde standaardlayout overnemen."""
        icp = self.env['ir.config_parameter'].sudo()
        key = 'sr_payroll.sr_default_payslip_layout'
        old_value = icp.get_param(key)
        try:
            icp.set_param(key, 'compact')
            payslip = self._make_payslip(wage=18000.0)
            self.assertEqual(payslip.sr_payslip_layout, 'compact')
        finally:
            param = self.env['ir.config_parameter'].sudo().search([('key', '=', key)], limit=1)
            if old_value in (None, False, ''):
                param.unlink()
            else:
                icp.set_param(key, old_value)

    def test_payslip_layout_default_valt_terug_bij_verouderde_config_waarde(self):
        """Oude configwaarden zoals 'detailed' mogen niet meer als werknemerslayout terugkomen."""
        icp = self.env['ir.config_parameter'].sudo()
        key = 'sr_payroll.default_payslip_layout'
        old_value = icp.get_param(key)
        try:
            icp.set_param(key, 'detailed')
            payslip = self._make_payslip(wage=18000.0)
            self.assertEqual(payslip.sr_payslip_layout, 'employee_simple')
            self.assertEqual(payslip._sr_get_effective_payslip_layout(), 'employee_simple')
        finally:
            param = self.env['ir.config_parameter'].sudo().search([('key', '=', key)], limit=1)
            if old_value in (None, False, ''):
                param.unlink()
            else:
                icp.set_param(key, old_value)

    def test_breakdown_actieve_heffingskorting_volgt_payslip_netto(self):
        """
        Heffingskorting blijft zichtbaar voor audit, maar verlaagt de
        in te houden loonbelasting in plaats van netto apart te verhogen.
        """
        payslip = self._make_payslip(wage=25000.0)

        bd = payslip._get_sr_artikel14_breakdown()

        self.assertAlmostEqual(bd['heffingskorting'], 750.0, delta=0.01)
        self.assertAlmostEqual(bd['bruto_per_periode'], 25000.0, delta=0.01)
        self.assertAlmostEqual(
            bd['lb_voor_heffingskorting_per_periode'],
            bd['lb_per_periode'] + bd['heffingskorting_per_periode'],
            delta=0.01,
        )
        self.assertAlmostEqual(
            bd['netto'],
            sum(payslip.line_ids.filtered(lambda l: l.code == 'NET').mapped('total')),
            delta=0.01,
        )

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
            'date_from': _fn_period_2026_10()[0],
            'date_to': _fn_period_2026_10()[1],
            'company_id': self.company.id,
        })
        payslip.compute_sheet()
        bd = payslip._get_sr_artikel14_breakdown()
        self.assertEqual(bd['periodes'], 26)
        self.assertTrue(bd['is_fn'])
        self.assertEqual(bd['franchise_periode'], 0.0,
                         'Fortnight heeft geen AOV franchise')
        self.assertEqual(bd['fn_period_label'], '2026FN10')
        self.assertEqual(bd['fn_period_indicator'], '202610')

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

    def test_breakdown_gebruikt_historische_parameterwaarden_boven_live_config(self):
        belastingvrij_param = self.env['hr.rule.parameter'].search([
            ('code', '=', 'SR_BELASTINGVRIJ_JAAR')
        ], limit=1)
        config = self.env['ir.config_parameter'].sudo()
        old_config = config.get_param('sr_payroll.belastingvrij_jaar')
        jan_value = belastingvrij_param.parameter_version_ids.filtered(
            lambda value: value.date_from == date(2026, 1, 1)
        )[:1]
        old_jan_value = jan_value.parameter_value if jan_value else None
        jul_value = belastingvrij_param.parameter_version_ids.filtered(
            lambda value: value.date_from == date(2026, 7, 1)
        )[:1]
        old_jul_value = jul_value.parameter_value if jul_value else None

        try:
            if jan_value:
                jan_value.write({'parameter_value': 108000.0})
            else:
                jan_value = self.env['hr.rule.parameter.value'].create({
                    'rule_parameter_id': belastingvrij_param.id,
                    'date_from': date(2026, 1, 1),
                    'parameter_value': 108000.0,
                })
            if jul_value:
                jul_value.write({'parameter_value': 120000.0})
            else:
                jul_value = self.env['hr.rule.parameter.value'].create({
                    'rule_parameter_id': belastingvrij_param.id,
                    'date_from': date(2026, 7, 1),
                    'parameter_value': 120000.0,
                })
            config.set_param('sr_payroll.belastingvrij_jaar', 130000.0)
            contract = self.env['hr.contract'].create({
                'name': 'Historische Parameter Contract',
                'employee_id': self.employee.id,
                'company_id': self.company.id,
                'structure_type_id': self.structure_type.id,
                'wage': 20000.0,
                'sr_salary_type': 'monthly',
                'date_start': date(2026, 1, 1),
                'state': 'open',
            })
            payslip = self.env['hr.payslip'].create({
                'name': 'Historische Parameter Payslip',
                'employee_id': self.employee.id,
                'contract_id': contract.id,
                'struct_id': self.structure.id,
                'date_from': date(2026, 6, 1),
                'date_to': date(2026, 6, 30),
                'company_id': self.company.id,
            })
            payslip.compute_sheet()

            breakdown = payslip._get_sr_artikel14_breakdown()

            self.assertEqual(payslip._rule_parameter('SR_BELASTINGVRIJ_JAAR'), 108000.0)
            self.assertEqual(breakdown['belastingvrij_jaar'], 108000.0)
        finally:
            if jan_value:
                if old_jan_value is None:
                    jan_value.unlink()
                else:
                    jan_value.write({'parameter_value': old_jan_value})
            if jul_value:
                if old_jul_value is None:
                    jul_value.unlink()
                else:
                    jul_value.write({'parameter_value': old_jul_value})
            if old_config in (None, False, ''):
                config.search([('key', '=', 'sr_payroll.belastingvrij_jaar')], limit=1).unlink()
            else:
                config.set_param('sr_payroll.belastingvrij_jaar', old_config)
