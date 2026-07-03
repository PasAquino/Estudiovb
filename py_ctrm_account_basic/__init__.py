# Part of Odoo. See LICENSE file for full copyright and licensing details.

from . import models

def uninstall_hook(cr, registry):
    cr.execute(
        "DELETE FROM ir_model_data WHERE module = 'l10n_py'"
    )
