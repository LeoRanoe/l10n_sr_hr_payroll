# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models
from odoo.exceptions import ValidationError

from . import sr_artikel14_calculator as calc


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    sr_currency_id = fields.Many2one(
        'res.currency',
        string='SRD Valuta',
        related='company_id.currency_id',
        readonly=True,
    )

    @api.model
    def _sr_default_param(self, code):
        return calc.get_config_parameter_default(code)

    belastingvrij_jaar = fields.Float(
        string='Belastingvrije voet (SRD / jaar)',
        config_parameter='sr_payroll.belastingvrij_jaar',
        default=lambda self: self._sr_default_param('SR_BELASTINGVRIJ_JAAR'),
    )
    forfaitaire_pct = fields.Float(
        string='Forfaitaire aftrek % (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.forfaitaire_pct',
        default=lambda self: self._sr_default_param('SR_FORFAITAIRE_PCT'),
    )
    forfaitaire_max_jaar = fields.Float(
        string='Forfaitaire aftrek maximum (SRD / jaar)',
        config_parameter='sr_payroll.forfaitaire_max_jaar',
        default=lambda self: self._sr_default_param('SR_FORFAITAIRE_MAX_JAAR'),
    )
    schijf_1_grens = fields.Float(
        string='Schijf 1 grens (SRD / jaar)',
        config_parameter='sr_payroll.schijf_1_grens',
        default=lambda self: self._sr_default_param('SR_SCHIJF_1_GRENS'),
    )
    schijf_2_grens = fields.Float(
        string='Schijf 2 grens (SRD / jaar)',
        config_parameter='sr_payroll.schijf_2_grens',
        default=lambda self: self._sr_default_param('SR_SCHIJF_2_GRENS'),
    )
    schijf_3_grens = fields.Float(
        string='Schijf 3 grens (SRD / jaar)',
        config_parameter='sr_payroll.schijf_3_grens',
        default=lambda self: self._sr_default_param('SR_SCHIJF_3_GRENS'),
    )
    tarief_1 = fields.Float(
        string='Tarief schijf 1 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_1',
        default=lambda self: self._sr_default_param('SR_TARIEF_1'),
    )
    tarief_2 = fields.Float(
        string='Tarief schijf 2 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_2',
        default=lambda self: self._sr_default_param('SR_TARIEF_2'),
    )
    tarief_3 = fields.Float(
        string='Tarief schijf 3 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_3',
        default=lambda self: self._sr_default_param('SR_TARIEF_3'),
    )
    tarief_4 = fields.Float(
        string='Tarief schijf 4 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_4',
        default=lambda self: self._sr_default_param('SR_TARIEF_4'),
    )
    heffingskorting = fields.Float(
        string='Heffingskorting (SRD)',
        config_parameter='sr_payroll.heffingskorting',
        default=lambda self: self._sr_default_param('SR_HEFFINGSKORTING'),
        help='Actieve netto heffingskorting: SRD per maand voor maandloon, pro-rata omgerekend voor FN.',
    )
    aov_tarief = fields.Float(
        string='AOV tarief (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.aov_tarief',
        default=lambda self: self._sr_default_param('SR_AOV_TARIEF'),
    )
    aov_franchise_maand = fields.Float(
        string='AOV franchise (SRD / maand)',
        config_parameter='sr_payroll.aov_franchise_maand',
        default=lambda self: self._sr_default_param('SR_AOV_FRANCHISE_MAAND'),
    )
    bijz_beloning_max = fields.Float(
        string='Vrijstelling vakantie/gratificatie per categorie (SRD / jaar)',
        config_parameter='sr_payroll.bijz_beloning_max',
        default=lambda self: self._sr_default_param('SR_BIJZ_VRIJSTELLING_MAX'),
        help='Jaarmaximum per categorie voor de vrijstelling van vakantietoelage en gratificatie/bonus.',
    )
    akb_per_kind = fields.Float(
        string='AKB per kind (SRD / maand)',
        config_parameter='sr_payroll.akb_per_kind',
        default=lambda self: self._sr_default_param('SR_KINDBIJ_MAX_KIND_MAAND'),
    )
    akb_max_bedrag = fields.Float(
        string='AKB maximum (SRD / maand)',
        config_parameter='sr_payroll.akb_max_bedrag',
        default=lambda self: self._sr_default_param('SR_KINDBIJ_MAX_MAAND'),
    )
    overwerk_schijf_1_grens = fields.Float(
        string='Overwerk schijf 1 grens (SRD / tijdvak)',
        config_parameter='sr_payroll.overwerk_schijf_1_grens',
        default=lambda self: self._sr_default_param('SR_OWK_SCHIJF_1_GRENS'),
    )
    overwerk_schijf_2_grens = fields.Float(
        string='Overwerk schijf 2 grens (SRD / tijdvak)',
        config_parameter='sr_payroll.overwerk_schijf_2_grens',
        default=lambda self: self._sr_default_param('SR_OWK_SCHIJF_2_GRENS'),
    )
    overwerk_tarief_1 = fields.Float(
        string='Overwerk tarief 1 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_tarief_1',
        default=lambda self: self._sr_default_param('SR_OWK_TARIEF_1'),
    )
    overwerk_tarief_2 = fields.Float(
        string='Overwerk tarief 2 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_tarief_2',
        default=lambda self: self._sr_default_param('SR_OWK_TARIEF_2'),
    )
    overwerk_tarief_3 = fields.Float(
        string='Overwerk tarief 3 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_tarief_3',
        default=lambda self: self._sr_default_param('SR_OWK_TARIEF_3'),
    )
    overwerk_factor_150 = fields.Float(
        string='Overwerk factor 150% (vermenigvuldiger)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_factor_150',
        default=1.5,
        help='Vermenigvuldiger voor overwerk op werkdagen (Ma–Za). Standaard: 1,5.',
    )
    overwerk_factor_200 = fields.Float(
        string='Overwerk factor 200% (vermenigvuldiger)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_factor_200',
        default=2.0,
        help='Vermenigvuldiger voor overwerk op zondag of wettelijke feestdagen. Standaard: 2,0.',
    )

    def _sr_ensure_non_negative(self, field_name, label):
        for settings in self:
            value = settings[field_name]
            if value is not False and value < 0:
                raise ValidationError(f'{label} mag niet negatief zijn.')

    @api.constrains(
        'belastingvrij_jaar',
        'forfaitaire_max_jaar',
        'aov_franchise_maand',
        'bijz_beloning_max',
        'akb_per_kind',
        'akb_max_bedrag',
        'heffingskorting',
        'schijf_1_grens',
        'schijf_2_grens',
        'schijf_3_grens',
        'overwerk_schijf_1_grens',
        'overwerk_schijf_2_grens',
        'overwerk_factor_150',
        'overwerk_factor_200',
    )
    def _check_non_negative_amounts(self):
        field_labels = {
            'belastingvrij_jaar': 'Belastingvrije voet',
            'forfaitaire_max_jaar': 'Forfaitaire aftrek maximum',
            'aov_franchise_maand': 'AOV franchise',
            'bijz_beloning_max': 'Vrijstelling vakantie/gratificatie per categorie',
            'akb_per_kind': 'AKB per kind',
            'akb_max_bedrag': 'AKB maximum',
            'heffingskorting': 'Heffingskorting',
            'schijf_1_grens': 'Schijf 1 grens',
            'schijf_2_grens': 'Schijf 2 grens',
            'schijf_3_grens': 'Schijf 3 grens',
            'overwerk_schijf_1_grens': 'Overwerk schijf 1 grens',
            'overwerk_schijf_2_grens': 'Overwerk schijf 2 grens',
            'overwerk_factor_150': 'Overwerk factor 150%',
            'overwerk_factor_200': 'Overwerk factor 200%',
        }
        for field_name, label in field_labels.items():
            self._sr_ensure_non_negative(field_name, label)

    @api.constrains(
        'forfaitaire_pct',
        'tarief_1',
        'tarief_2',
        'tarief_3',
        'tarief_4',
        'aov_tarief',
        'overwerk_tarief_1',
        'overwerk_tarief_2',
        'overwerk_tarief_3',
    )
    def _check_decimal_rates(self):
        rate_fields = {
            'forfaitaire_pct': 'Forfaitaire aftrek %',
            'tarief_1': 'Tarief schijf 1',
            'tarief_2': 'Tarief schijf 2',
            'tarief_3': 'Tarief schijf 3',
            'tarief_4': 'Tarief schijf 4',
            'aov_tarief': 'AOV tarief',
            'overwerk_tarief_1': 'Overwerk tarief 1',
            'overwerk_tarief_2': 'Overwerk tarief 2',
            'overwerk_tarief_3': 'Overwerk tarief 3',
        }
        for settings in self:
            for field_name, label in rate_fields.items():
                value = settings[field_name]
                if value is False:
                    continue
                if value < 0 or value > 1:
                    raise ValidationError(f'{label} moet als decimaal tussen 0 en 1 worden ingevoerd.')

    @api.constrains('schijf_1_grens', 'schijf_2_grens', 'schijf_3_grens')
    def _check_progressive_brackets(self):
        for settings in self:
            if not (settings.schijf_1_grens < settings.schijf_2_grens < settings.schijf_3_grens):
                raise ValidationError(
                    'De reguliere Art. 14 schijfgrenzen moeten strikt oplopend zijn.'
                )

    @api.constrains('overwerk_schijf_1_grens', 'overwerk_schijf_2_grens')
    def _check_overtime_brackets(self):
        for settings in self:
            if settings.overwerk_schijf_1_grens >= settings.overwerk_schijf_2_grens:
                raise ValidationError(
                    'De overwerkgrenzen moeten strikt oplopend zijn.'
                )

    @api.constrains('akb_per_kind', 'akb_max_bedrag')
    def _check_akb_limits(self):
        for settings in self:
            if settings.akb_per_kind and settings.akb_max_bedrag < settings.akb_per_kind:
                raise ValidationError(
                    'Het AKB maximum moet minimaal gelijk zijn aan het bedrag per kind.'
                )