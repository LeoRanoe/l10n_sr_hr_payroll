#!/bin/bash
# deploy_vm.sh — run on the VM after pulling l10n_sr_hr_payroll changes
# Usage: sudo bash deploy_vm.sh
#
# Adjust these variables to match your VM setup:
ODOO_BIN="/opt/odoo/odoo-bin"
ODOO_CONF="/etc/odoo/odoo.conf"
ODOO_SERVICE="odoo"
ODOO_USER="odoo"

set -e

echo "=== Stopping Odoo service ==="
systemctl stop "$ODOO_SERVICE"

echo "=== Upgrading l10n_sr_hr_payroll (syncs new DB columns + XML data) ==="
sudo -u "$ODOO_USER" "$ODOO_BIN" \
  -c "$ODOO_CONF" \
  -u l10n_sr_hr_payroll \
  --stop-after-init

echo "=== Starting Odoo service ==="
systemctl start "$ODOO_SERVICE"

echo "=== Done. Odoo is running with the updated module. ==="
