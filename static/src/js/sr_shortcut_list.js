/** @odoo-module **/
/**
 * SR Shortcut List Field — custom x2many widget that renders each
 * hr.contract.sr.line as a clean labelled form block instead of a table row.
 */
import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { Field } from "@web/views/fields/field";

export class SrShortcutListField extends X2ManyField {
    static template = "l10n_sr_hr_payroll.SrShortcutListField";
    static components = { ...X2ManyField.components, Field };

    /**
     * Look up the archInfo column descriptor for a given field name.
     * This carries the domain, options, and other arch-level attributes
     * so that Field will apply them correctly (e.g. domain on type_id).
     */
    fieldInfo(name) {
        return (this.archInfo.columns || []).find(
            (c) => c.type === "field" && c.name === name
        );
    }

    async removeRecord(record) {
        await this.list.delete(record);
    }

    async addRecord() {
        await this.onAdd({ editable: true });
    }
}

registry.category("fields").add("sr_shortcut_list", {
    ...x2ManyField,
    component: SrShortcutListField,
    displayName: "SR Shortcut Lijst",
    supportedTypes: ["one2many"],
});
