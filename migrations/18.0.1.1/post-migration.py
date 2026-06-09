# Part of Odoo. See LICENSE file for full copyright and licensing details.


def migrate(cr, version):
    """Move old 2026 default config overrides to the corrected legal defaults."""
    replacements = (
        ('sr_payroll.belastingvrij_jaar', '108000.0', ('0', '0.0', '0.00')),
        ('sr_payroll.heffingskorting', '0.0', ('750', '750.0', '750.00')),
        ('sr_payroll.aov_franchise_maand', '0.0', ('400', '400.0', '400.00')),
    )
    for key, new_value, old_values in replacements:
        placeholders = ','.join(['%s'] * len(old_values))
        cr.execute(
            f"""
            UPDATE ir_config_parameter
               SET value = %s
             WHERE key = %s
               AND value IN ({placeholders})
            """,
            (new_value, key, *old_values),
        )

    obsolete_xmlids = (
        'sr_param_17a_schijf_4_grens_2026',
        'sr_param_17a_tarief_5_2026',
    )
    placeholders = ','.join(['%s'] * len(obsolete_xmlids))
    cr.execute(
        f"""
        DELETE FROM hr_rule_parameter_value
         WHERE id IN (
               SELECT res_id
                 FROM ir_model_data
                WHERE module = 'l10n_sr_hr_payroll'
                  AND model = 'hr.rule.parameter.value'
                  AND name IN ({placeholders})
         )
        """,
        obsolete_xmlids,
    )
    cr.execute(
        f"""
        DELETE FROM ir_model_data
         WHERE module = 'l10n_sr_hr_payroll'
           AND model = 'hr.rule.parameter.value'
           AND name IN ({placeholders})
        """,
        obsolete_xmlids,
    )

    holiday_updates = (
        ('sr_holiday_2026_03_31', '2026-03-20'),
        ('sr_holiday_2026_06_06', '2026-05-27'),
    )
    for xmlid, new_date in holiday_updates:
        cr.execute(
            """
            UPDATE sr_public_holiday
               SET date = %s
             WHERE id IN (
                   SELECT res_id
                     FROM ir_model_data
                    WHERE module = 'l10n_sr_hr_payroll'
                      AND model = 'sr.public.holiday'
                      AND name = %s
             )
            """,
            (new_date, xmlid),
        )

    missing_holidays = (
        ('sr_holiday_2026_08_09', 'Dag der Inheemsen', '2026-08-09'),
        ('sr_holiday_2026_10_10', 'Dag der Marrons', '2026-10-10'),
    )
    for xmlid, name, holiday_date in missing_holidays:
        cr.execute(
            """
            INSERT INTO sr_public_holiday (name, date, active)
            VALUES (%s, %s, TRUE)
            ON CONFLICT (date) DO NOTHING
            RETURNING id
            """,
            (name, holiday_date),
        )
        row = cr.fetchone()
        if not row:
            cr.execute(
                "SELECT id FROM sr_public_holiday WHERE date = %s",
                (holiday_date,),
            )
            row = cr.fetchone()
        if row:
            cr.execute(
                """
                INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
                VALUES ('l10n_sr_hr_payroll', %s, 'sr.public.holiday', %s, TRUE)
                ON CONFLICT (module, name) DO NOTHING
                """,
                (xmlid, row[0]),
            )
