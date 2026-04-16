# Part of Odoo. See LICENSE file for full copyright and licensing details.
"""
Centrale definitie van Surinaamse loonbelastingcategorieën.

Basis (3) — voor vaste contractregels (hr.contract.sr.line / .type):
  belastbaar, vrijgesteld, inhouding

Uitgebreid (7) — voor payslip input types (hr.payslip.input.type):
  + overwerk, vakantie, gratificatie, bijz_beloning
"""

SR_CATEGORIE_BASE = [
    ('belastbaar', 'Belastbaar  (Art. 14 — LB + AOV grondslag)'),
    ('vrijgesteld', 'Belastingvrij  (Art. 10 — geen LB of AOV)'),
    ('inhouding', 'Inhouding / Aftrek  (netto aftrek)'),
    ('aftrek_belastingvrij', 'Aftrek Belastingvrij  (Art. 10f — vermindert LB + AOV grondslag)'),
]

SR_CATEGORIE_EXTENDED = SR_CATEGORIE_BASE + [
    ('overwerk', 'Overwerk  (Art. 17c — eigen belastingschijven)'),
    ('vakantie', 'Vakantietoelage  (Art. 10i — belastingvrije vrijstelling)'),
    ('gratificatie', 'Gratificatie / Bonus  (Art. 10j — belastingvrije vrijstelling)'),
    ('bijz_beloning', 'Bijzondere Beloning  (Art. 17 — marginaal tarief methode)'),
    ('uitkering_ineens', 'Uitkering Ineens / Jubileum  (Art. 17a — eigen tariefschijven)'),
]
