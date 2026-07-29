# -*- coding: utf-8 -*-
import base64
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class StockPickingRemision(models.Model):
    """Extiende stock.picking con datos de la Nota de Remisión paraguaya."""
    _inherit = 'stock.picking'

    # ── Estado de la Remisión ────────────────────────────────────────────────
    remision_state = fields.Selection(
        selection=[('draft', 'Borrador'), ('confirmed', 'Confirmado')],
        string='Estado Remisión',
        default='draft',
        tracking=True,
        copy=False,
    )

    # ── Timbrado ─────────────────────────────────────────────────────────────
    remision_stamp_id = fields.Many2one(
        'account.journal.stamped',
        string='Timbrado',
        domain=[('type', '=', 2), ('state', '=', 'active')],
        copy=False,
    )
    remision_number = fields.Char(
        string='Nº Nota de Remisión',
        copy=False,
    )
    remision_stamp_number = fields.Char(
        string='Número Timbrado',
        related='remision_stamp_id.name',
        store=True,
    )
    remision_stamp_vigencia_ini = fields.Date(
        string='Vigencia Desde',
        related='remision_stamp_id.date_range_ini',
        store=True,
    )
    remision_stamp_vigencia_fin = fields.Date(
        string='Vigencia Hasta',
        related='remision_stamp_id.date_range_end',
        store=True,
    )

    # ── Datos del Traslado ────────────────────────────────────────────────────
    remision_fecha_inicio = fields.Date(
        string='Fecha de inicio del traslado',
        default=fields.Date.today,
    )
    remision_fecha_fin = fields.Date(
        string='Fecha de término del traslado',
        default=fields.Date.today,
    )
    remision_orden_trabajo = fields.Char(string='Orden de Trabajo')

    # ── Destinatario ─────────────────────────────────────────────────────────
    remision_ruc_destinatario = fields.Char(
        string='RUC o C.I. del Destinatario',
        compute='_compute_destinatario',
        store=True,
        readonly=False,
    )
    remision_nombre_razon_social = fields.Char(
        string='Nombre o Razón Social',
        compute='_compute_destinatario',
        store=True,
        readonly=False,
    )
    remision_nombre_fantasia = fields.Char(
        string='Nombre de Fantasía',
        compute='_compute_destinatario',
        store=True,
        readonly=False,
    )

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

    # ── Motivo del Traslado ───────────────────────────────────────────────────
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
    )
    remision_motivo_otros = fields.Char(string='Otros motivos (especifique)')

    # ── Cómputos ──────────────────────────────────────────────────────────────
    @api.depends('partner_id')
    def _compute_destinatario(self):
        for rec in self:
            if rec.partner_id:
                rec.remision_ruc_destinatario = rec.partner_id.vat or ''
                rec.remision_nombre_razon_social = rec.partner_id.name or ''
                rec.remision_nombre_fantasia = rec.partner_id.name or ''
            else:
                rec.remision_ruc_destinatario = ''
                rec.remision_nombre_razon_social = ''
                rec.remision_nombre_fantasia = ''

    # ── Acciones ──────────────────────────────────────────────────────────────
    def action_open_remision_wizard(self):
        """Abre el wizard para completar datos y confirmar la Nota de Remisión."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Confirmar Nota de Remisión',
            'res_model': 'wizard.remision.confirm',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_picking_id': self.id,
                'default_remision_fecha_inicio': self.remision_fecha_inicio,
                'default_remision_fecha_fin': self.remision_fecha_fin,
                'default_remision_ruc_destinatario': self.remision_ruc_destinatario,
                'default_remision_nombre_razon_social': self.remision_nombre_razon_social,
                'default_remision_nombre_fantasia': self.remision_nombre_fantasia,
                'default_remision_dir_partida': self.remision_dir_partida,
                'default_remision_dir_llegada': self.remision_dir_llegada,
                'default_remision_marca_vehiculo': self.remision_marca_vehiculo,
                'default_remision_rua_remolque': self.remision_rua_remolque,
                'default_remision_nombre_transportista': self.remision_nombre_transportista,
                'default_remision_ruc_transportista': self.remision_ruc_transportista,
                'default_remision_nombre_conductor': self.remision_nombre_conductor,
                'default_remision_ci_conductor': self.remision_ci_conductor,
                'default_remision_domicilio_conductor': self.remision_domicilio_conductor,
                'default_remision_factura_nro': self.remision_factura_nro,
                'default_remision_motivo': self.remision_motivo,
                'default_remision_motivo_otros': self.remision_motivo_otros,
                'default_remision_orden_trabajo': self.remision_orden_trabajo,
            },
        }

    def action_print_remision(self):
        """Genera e imprime la Nota de Remision con ReportLab (solo si está confirmada)."""
        self.ensure_one()
        if self.remision_state != 'confirmed':
            raise UserError(_('Solo se pueden imprimir Notas de Remision en estado Confirmado.'))

        from ..reports.nota_remision_reportlab import generate_nota_remision_pdf
        pdf_bytes = generate_nota_remision_pdf(self)

        filename = 'nota_remision_{}.pdf'.format(
            (self.remision_number or self.name or 'doc').replace('/', '-')
        )
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'type': 'binary',
            'datas': base64.b64encode(pdf_bytes).decode('utf-8'),
            'res_model': 'stock.picking',
            'res_id': self.id,
            'mimetype': 'application/pdf',
        })
        return {
            'type': 'ir.actions.act_url',
            'url': '/web/content/{}?download=true'.format(attachment.id),
            'target': 'new',
        }

    def action_reset_remision_draft(self):
        """Vuelve la remisión a estado Borrador."""
        self.ensure_one()
        self.write({'remision_state': 'draft'})

