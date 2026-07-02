# Part of Odoo. See LICENSE file for full copyright and licensing details.


ARTIKEL14_PARAMETER_ROWS = (
    (
        'sr_param_schijf_1_grens',
        'SR — Schijf 1 bovengrens — Art. 14 (belastbaar jaarloon, SRD)',
        'SR_SCHIJF_1_GRENS',
        'sr_param_schijf_1_grens_2026',
        '42000.0',
    ),
    (
        'sr_param_schijf_2_grens',
        'SR — Schijf 2 bovengrens — Art. 14 (belastbaar jaarloon, SRD)',
        'SR_SCHIJF_2_GRENS',
        'sr_param_schijf_2_grens_2026',
        '84000.0',
    ),
    (
        'sr_param_schijf_3_grens',
        'SR — Schijf 3 bovengrens — Art. 14 (belastbaar jaarloon, SRD)',
        'SR_SCHIJF_3_GRENS',
        'sr_param_schijf_3_grens_2026',
        '126000.0',
    ),
    (
        'sr_param_tarief_1',
        'SR — Tarief schijf 1 — Art. 14 (decimaal: 0.08 = 8%)',
        'SR_TARIEF_1',
        'sr_param_tarief_1_2026',
        '0.08',
    ),
    (
        'sr_param_tarief_2',
        'SR — Tarief schijf 2 — Art. 14 (decimaal: 0.18 = 18%)',
        'SR_TARIEF_2',
        'sr_param_tarief_2_2026',
        '0.18',
    ),
    (
        'sr_param_tarief_3',
        'SR — Tarief schijf 3 — Art. 14 (decimaal: 0.28 = 28%)',
        'SR_TARIEF_3',
        'sr_param_tarief_3_2026',
        '0.28',
    ),
    (
        'sr_param_tarief_4',
        'SR — Tarief schijf 4 — Art. 14 (decimaal: 0.38 = 38%)',
        'SR_TARIEF_4',
        'sr_param_tarief_4_2026',
        '0.38',
    ),
)


def _ensure_xmlid(cr, module, name, model, res_id, noupdate=True):
    cr.execute(
        """
        INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT (module, name)
        DO UPDATE SET model = EXCLUDED.model, res_id = EXCLUDED.res_id, noupdate = EXCLUDED.noupdate
        """,
        (module, name, model, res_id, noupdate),
    )


def _get_country_id(cr):
    cr.execute(
        """
        SELECT res_id
          FROM ir_model_data
         WHERE module = 'base'
           AND name = 'sr'
           AND model = 'res.country'
        """
    )
    row = cr.fetchone()
    return row[0] if row else None


def _ensure_rule_parameter(cr, country_id, xmlid_name, name, code):
    cr.execute(
        """
        SELECT id
          FROM hr_rule_parameter
         WHERE code = %s
         ORDER BY id
         LIMIT 1
        """,
        (code,),
    )
    row = cr.fetchone()
    if row:
        parameter_id = row[0]
        cr.execute(
            """
            UPDATE hr_rule_parameter
               SET name = %s,
                   country_id = COALESCE(country_id, %s)
             WHERE id = %s
            """,
            (name, country_id, parameter_id),
        )
    else:
        cr.execute(
            """
            INSERT INTO hr_rule_parameter (name, code, country_id)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (name, code, country_id),
        )
        parameter_id = cr.fetchone()[0]
    _ensure_xmlid(cr, 'l10n_sr_hr_payroll', xmlid_name, 'hr.rule.parameter', parameter_id)
    return parameter_id


def _ensure_rule_parameter_value(cr, parameter_id, xmlid_name, parameter_value):
    cr.execute(
        """
        SELECT id
          FROM hr_rule_parameter_value
         WHERE rule_parameter_id = %s
           AND date_from = DATE '2026-01-01'
         ORDER BY id
         LIMIT 1
        """,
        (parameter_id,),
    )
    row = cr.fetchone()
    if row:
        value_id = row[0]
        cr.execute(
            """
            UPDATE hr_rule_parameter_value
               SET parameter_value = %s
             WHERE id = %s
            """,
            (parameter_value, value_id),
        )
    else:
        cr.execute(
            """
            INSERT INTO hr_rule_parameter_value (rule_parameter_id, date_from, parameter_value)
            VALUES (%s, DATE '2026-01-01', %s)
            RETURNING id
            """,
            (parameter_id, parameter_value),
        )
        value_id = cr.fetchone()[0]
    _ensure_xmlid(cr, 'l10n_sr_hr_payroll', xmlid_name, 'hr.rule.parameter.value', value_id)


def migrate(cr, version):
    """Restore mandatory Art. 14 parameter records so upgrades cannot leave payroll without brackets."""
    country_id = _get_country_id(cr)
    for parameter_xmlid, name, code, value_xmlid, parameter_value in ARTIKEL14_PARAMETER_ROWS:
        parameter_id = _ensure_rule_parameter(cr, country_id, parameter_xmlid, name, code)
        _ensure_rule_parameter_value(cr, parameter_id, value_xmlid, parameter_value)