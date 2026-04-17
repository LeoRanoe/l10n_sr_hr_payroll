# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    belastingvrij_jaar = fields.Float(
        string='Belastingvrije voet (SRD / jaar)',
        config_parameter='sr_payroll.belastingvrij_jaar',
    )
    forfaitaire_pct = fields.Float(
        string='Forfaitaire aftrek % (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.forfaitaire_pct',
    )
    forfaitaire_max_jaar = fields.Float(
        string='Forfaitaire aftrek maximum (SRD / jaar)',
        config_parameter='sr_payroll.forfaitaire_max_jaar',
    )
    schijf_1_grens = fields.Float(
        string='Schijf 1 grens (SRD / jaar)',
        config_parameter='sr_payroll.schijf_1_grens',
    )
    schijf_2_grens = fields.Float(
        string='Schijf 2 grens (SRD / jaar)',
        config_parameter='sr_payroll.schijf_2_grens',
    )
    schijf_3_grens = fields.Float(
        string='Schijf 3 grens (SRD / jaar)',
        config_parameter='sr_payroll.schijf_3_grens',
    )
    tarief_1 = fields.Float(
        string='Tarief schijf 1 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_1',
    )
    tarief_2 = fields.Float(
        string='Tarief schijf 2 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_2',
    )
    tarief_3 = fields.Float(
        string='Tarief schijf 3 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_3',
    )
    tarief_4 = fields.Float(
        string='Tarief schijf 4 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.tarief_4',
    )
    heffingskorting = fields.Float(
        string='Heffingskorting (SRD)',
        config_parameter='sr_payroll.heffingskorting',
        help='Wordt opgeslagen voor audit en toekomstige activering. De huidige SR_HK-regel is inactief.',
    )
    aov_tarief = fields.Float(
        string='AOV tarief (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.aov_tarief',
    )
    aov_franchise_maand = fields.Float(
        string='AOV franchise (SRD / maand)',
        config_parameter='sr_payroll.aov_franchise_maand',
    )
    bijz_beloning_max = fields.Float(
        string='Bijzondere beloning maximum (SRD / jaar)',
        config_parameter='sr_payroll.bijz_beloning_max',
    )
    akb_per_kind = fields.Float(
        string='AKB per kind (SRD / maand)',
        config_parameter='sr_payroll.akb_per_kind',
    )
    akb_max_bedrag = fields.Float(
        string='AKB maximum (SRD / maand)',
        config_parameter='sr_payroll.akb_max_bedrag',
    )
    overwerk_schijf_1_grens = fields.Float(
        string='Overwerk schijf 1 grens (SRD / tijdvak)',
        config_parameter='sr_payroll.overwerk_schijf_1_grens',
    )
    overwerk_schijf_2_grens = fields.Float(
        string='Overwerk schijf 2 grens (SRD / tijdvak)',
        config_parameter='sr_payroll.overwerk_schijf_2_grens',
    )
    overwerk_tarief_1 = fields.Float(
        string='Overwerk tarief 1 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_tarief_1',
    )
    overwerk_tarief_2 = fields.Float(
        string='Overwerk tarief 2 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_tarief_2',
    )
    overwerk_tarief_3 = fields.Float(
        string='Overwerk tarief 3 (decimaal)',
        digits=(16, 4),
        config_parameter='sr_payroll.overwerk_tarief_3',
    )