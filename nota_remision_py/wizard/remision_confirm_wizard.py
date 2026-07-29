# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import datetime


class WizardRemisionConfirm(models.TransientModel):
    """Wizard para completar datos y confirmar la Nota de Remisión."""
    _name = 'wizard.remision.confirm'
    _description = 'Confirmar Nota de Remisión'

    picking_id = fields.Many2one('stock.picking', string='Transferencia', required=True)

    # ── Timbrado ─────────────────────────────────────────────────────────────
    stamp_journal_id = fields.Many2one(
        'account.journal.stamped',
        string='Talonario / Timbrado',
        domain=[('type', '=', 2), ('state', '=', 'active')],
        required=True,
        default=lambda self: self._default_stamp(),
    )
    assign_number = fields.Char(
        string='Número asignado a esta Remisión',
        compute='_compute_assign_number',
    )

    # ── Datos del Traslado ────────────────────────────────────────────────────
    remision_fecha_inicio = fields.Date(string='Fecha inicio traslado', default=fields.Date.today, required=True)
    remision_fecha_fin = fields.Date(string='Fecha término traslado', default=fields.Date.today, required=True)
    remision_orden_trabajo = fields.Char(string='Orden de Trabajo')

    # ── Destinatario ─────────────────────────────────────────────────────────
    remision_ruc_destinatario = fields.Char(string='RUC o C.I. del Destinatario')
    remision_nombre_razon_social = fields.Char(string='Nombre o Razón Social')
    remision_nombre_fantasia = fields.Char(string='Nombre de Fantasía')

    # ── Direcciones ──────────────────────────────────────────────────────────
    remision_dir_partida = fields.Char(string='Dirección punto de partida')
    remision_dir_llegada = fields.Char(string='Dirección punto de llegada')

    # ── Vehículo / Transporte ─────────────────────────────────────────────────
    remision_marca_vehiculo = fields.Char(string='Marca del vehículo de transporte')
    remision_rua_remolque = fields.Char(string='RUA del remolque/tractor/semirremolque')
    remision_nombre_transportista = fields.Char(string='Nombre o Razón Social del Transportista')
    remision_ruc_transportista = fields.Char(string='RUC del Transportista')
    remision_nombre_conductor = fields.Char(string='Nombre del Conductor')
    remision_ci_conductor = fields.Char(string='C.I. del Conductor')
    remision_domicilio_conductor = fields.Char(string='Domicilio del Conductor')
    remision_factura_nro = fields.Char(string='Factura Nº')

    # ── Motivo ────────────────────────────────────────────────────────────────
    remision_motivo = fields.Selection(
        selection=[
            ('venta', 'Venta'),
            ('importacion', 'Importación'),
            ('traslado_local', 'Traslado locales empresa'),
            ('emisor_movil', 'Emisor móvil'),
            ('exportacion', 'Exportación'),
            ('consignacion', 'Consignación'),
            ('transformacion', 'Transformación'),
            ('exhibicion', 'Exhibición'),
            ('compra', 'Compra'),
            ('devolucion', 'Devolución'),
            ('reparacion', 'Reparación'),
            ('ferias', 'Ferias'),
            ('garantia', 'Garantía'),
            ('gentileza', 'Gentileza'),
            ('instalacion', 'Instalación'),
            ('otros', 'Otros'),
        ],
        string='Motivo del Traslado',
        default='venta',
        required=True,
    )
    remision_motivo_otros = fields.Char(string='Otros motivos (especifique)')

    # ── Helpers ───────────────────────────────────────────────────────────────
    @api.model
    def _default_stamp(self):
        company_id = self.env.company.id
        return self.env['account.journal.stamped'].search(
            [('type', '=', 2), ('state', '=', 'active'), ('company_id', '=', company_id)],
            limit=1,
        )

    @api.depends('stamp_journal_id', 'stamp_journal_id.current_number')
    def _compute_assign_number(self):
        for rec in self:
            if rec.stamp_journal_id:
                sj = rec.stamp_journal_id
                today = datetime.now().date()
                if sj.date_range_end < today:
                    rec.assign_number = '⚠ Timbrado vencido'
                    continue
                nro = sj.current_number + 1
                rec.assign_number = '{}-{}-{}'.format(
                    sj.establishment_code,
                    sj.shipping_point,
                    str(nro).zfill(7),
                )
            else:
                rec.assign_number = ''

    def _format_number(self, sj):
        nro = sj.current_number + 1
        return '{}-{}-{}'.format(
            sj.establishment_code,
            sj.shipping_point,
            str(nro).zfill(7),
        )

    # ── Confirmar ─────────────────────────────────────────────────────────────
    def action_confirmar(self):
        self.ensure_one()
        sj = self.stamp_journal_id
        if not sj:
            raise ValidationError(_('Debe seleccionar un talonario/timbrado.'))

        today = datetime.now().date()
        if sj.date_range_end < today:
            raise ValidationError(_('El timbrado seleccionado está vencido.'))
        if sj.date_range_ini > today:
            raise ValidationError(_('La fecha de inicio del timbrado es posterior a hoy.'))

        remision_number = self._format_number(sj)

        # Escribir en el picking
        self.picking_id.write({
            'remision_state': 'confirmed',
            'remision_stamp_id': sj.id,
            'remision_number': remision_number,
            'remision_fecha_inicio': self.remision_fecha_inicio,
            'remision_fecha_fin': self.remision_fecha_fin,
            'remision_orden_trabajo': self.remision_orden_trabajo,
            'remision_ruc_destinatario': self.remision_ruc_destinatario,
            'remision_nombre_razon_social': self.remision_nombre_razon_social,
            'remision_nombre_fantasia': self.remision_nombre_fantasia,
            'remision_dir_partida': self.remision_dir_partida,
            'remision_dir_llegada': self.remision_dir_llegada,
            'remision_marca_vehiculo': self.remision_marca_vehiculo,
            'remision_rua_remolque': self.remision_rua_remolque,
            'remision_nombre_transportista': self.remision_nombre_transportista,
            'remision_ruc_transportista': self.remision_ruc_transportista,
            'remision_nombre_conductor': self.remision_nombre_conductor,
            'remision_ci_conductor': self.remision_ci_conductor,
            'remision_domicilio_conductor': self.remision_domicilio_conductor,
            'remision_factura_nro': self.remision_factura_nro,
            'remision_motivo': self.remision_motivo,
            'remision_motivo_otros': self.remision_motivo_otros,
        })

        # Avanzar el contador del timbrado
        sj.write({
            'number_used': sj.current_number,
            'current_number': sj.current_number + 1,
        })

        # Imprimir directamente al confirmar
        return self.picking_id.action_print_remision()

