odoo.define('wizard.resolucion90.generator', function (require) {
"use strict";

    var core = require('web.core');
    var _t = core._t;

    var qweb = core.qweb;

    var GenerateWizardResolucion90 = {

        open_window_wizard_resolucion: function (ev) {
            ev.preventDefault();
            this.do_action({
                name: 'Generar Resolucion 90',
                res_model: 'resolucion.90.21',
                views: [[false, 'form']],
                type: 'ir.actions.act_window',
                target: 'new',
                view_mode: 'form',
            });
        },
    }
    return GenerateWizardResolucion90;
});


odoo.define('py_ctrm_90.custom_tree_view', function (require) {
"use strict";

    var core = require('web.core');
    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var GenerateWizardResolucion90_21 = require('wizard.resolucion90.generator');
    var viewRegistry = require('web.view_registry');

    var Resolucion90ListController = ListController.extend(GenerateWizardResolucion90_21, {
        buttons_template: 'WizardGeneratorResolucion90.buttons',
        events: _.extend({}, ListController.prototype.events, {
            'click .o_button_generate_wizard': 'open_window_wizard_resolucion',
        }),
    });

    var BillsListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: Resolucion90ListController,
        }),
    });

    viewRegistry.add('resolucion90_tree', BillsListView);
});
