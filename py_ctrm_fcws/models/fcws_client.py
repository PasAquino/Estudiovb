import json
import logging
import time

import requests

from odoo import _, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class FCWSClient(models.AbstractModel):
    _name = "fcws.client"
    _description = "Cliente API FCWS (Factura Criterium Web Service)"

    # ----------------------------------------------------------------------
    # Configuración
    # ----------------------------------------------------------------------
    def _get_base_url(self):
        base_url = (self.env.company.fcws_base_url or "").strip().rstrip("/")
        if not base_url:
            raise ValidationError(
                _("Debe configurar la URL base del servicio FCWS en la compañía.")
            )
        return base_url

    def _build_url(self, endpoint):
        return f"{self._get_base_url()}/{endpoint.lstrip('/')}"

    def _get_headers(self):
        return {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
        }

    # ----------------------------------------------------------------------
    # Credenciales
    # ----------------------------------------------------------------------
    def _get_taxpayer_data(self):
        company = self.env.company
        is_prod = bool(company.fcws_is_production)
        contribuyente_id = (
            company.fcws_prod_user if is_prod else company.fcws_test_user
        )
        password = (
            company.fcws_prod_password if is_prod else company.fcws_test_password
        )

        if not password:
            raise ValidationError(
                _(
                    "Falta cargar la API key en la contraseña del entorno '%s' "
                    "de la compañía '%s'."
                )
                % ("Producción" if is_prod else "Test", company.display_name)
            )

        taxpayer = {"pass": password}
        if contribuyente_id:
            taxpayer["contribuyenteid"] = str(contribuyente_id).strip()

        _logger.info(
            "[FCWS] Empresa: %s | Ambiente: %s",
            company.name,
            "Producción" if is_prod else "Test",
        )

        return taxpayer

    # ----------------------------------------------------------------------
    # Llamadas HTTP
    # ----------------------------------------------------------------------
    def _request(self, endpoint, method="GET", data=None, timeout=30, max_retries=2):
        url = self._build_url(endpoint)
        headers = self._get_headers()
        payload = json.dumps(data or {}, ensure_ascii=False).encode("utf-8")

        _logger.info("[FCWS] %s %s", method, url)
        _logger.debug(
            "[FCWS] Payload JSON: %s",
            json.dumps(data or {}, ensure_ascii=False, indent=2),
        )

        last_error = None
        for attempt in range(1, max_retries + 2):
            try:
                if method.upper() == "POST":
                    response = requests.post(
                        url, headers=headers, data=payload, timeout=timeout
                    )
                else:
                    response = requests.get(url, headers=headers, timeout=timeout)

                _logger.debug(
                    "[FCWS] Response %s: %s",
                    response.status_code,
                    response.text[:800],
                )

                if not response.ok and response.status_code not in (400, 422):
                    raise ValidationError(
                        _("Error HTTP %s: %s")
                        % (response.status_code, response.text)
                    )

                try:
                    result = response.json()
                    if isinstance(result, list) and len(result) == 1:
                        result = result[0]
                    return result
                except ValueError:
                    if not response.ok:
                        raise ValidationError(
                            _("Error HTTP %s: %s")
                            % (response.status_code, response.text)
                        )
                    _logger.warning(
                        "[FCWS] Respuesta no JSON, devolviendo texto plano"
                    )
                    return response.text

            except ValidationError:
                raise
            except (requests.Timeout, requests.ConnectionError) as error:
                last_error = error
                if attempt <= max_retries:
                    wait = 2 ** (attempt - 1)
                    _logger.warning(
                        "[FCWS] %s en intento %d/%d, reintentando en %ds...",
                        type(error).__name__,
                        attempt,
                        max_retries + 1,
                        wait,
                    )
                    time.sleep(wait)
            except Exception as error:
                raise ValidationError(_("Error al llamar FCWS: %s") % str(error))

        if isinstance(last_error, requests.Timeout):
            raise ValidationError(
                _("Timeout conectando con FCWS tras %d intentos")
                % (max_retries + 1)
            )
        raise ValidationError(
            _("Error de conexión con FCWS tras %d intentos") % (max_retries + 1)
        )

    # ----------------------------------------------------------------------
    # Endpoints
    # ----------------------------------------------------------------------
    def send_invoice(self, data):
        return self._request("factura/", "POST", data)

    def send_credit_note(self, data):
        return self._request("notacredito/", "POST", data)

    def send_debit_note(self, data):
        return self._request("notadebito/", "POST", data)

    def send_self_invoice(self, data):
        return self._request("autofactura/", "POST", data)

    def send_delivery_note(self, data):
        return self._request("remision/", "POST", data)

    def create_batch(self, data):
        return self._request("lotes/crear/", "POST", data, timeout=60)

    def consult_batch(self, batch_number):
        return self._request(
            "lotes/detalle/",
            "POST",
            {
                "contribuyente": self._get_taxpayer_data(),
                "numero_lote": batch_number,
            },
            timeout=60,
        )

    def consult_document(self, cdc):
        return self._request(
            "documentos/consultar/",
            "POST",
            {
                "contribuyente": self._get_taxpayer_data(),
                "cdc": cdc,
            },
        )

    def consult_document_by_id(self, document_id):
        return self._request(
            "documentos/consultar/",
            "POST",
            {
                "contribuyente": self._get_taxpayer_data(),
                "id": document_id,
            },
        )

    def sync_document_state(self, cdc):
        return self._request(
            "documentos/estado-sifen/",
            "POST",
            {
                "contribuyente": self._get_taxpayer_data(),
                "cdc": cdc,
            },
        )

    def delete_document(self, cdc):
        return self._request(
            "documentos/eliminar/",
            "POST",
            {
                "contribuyente": self._get_taxpayer_data(),
                "cdc": cdc,
            },
        )

    def cancel_invoice(self, data):
        return self._request("evento/cancelacion/", "POST", data)

    def cancel_credit_note(self, data):
        return self._request("evento/cancelacion/", "POST", data)

    def cancel_debit_note(self, data):
        return self._request("evento/cancelacion/", "POST", data)

    def cancel_delivery_note(self, data):
        return self._request("evento/cancelacion/", "POST", data)

    def disable_invoice(self, data):
        return self._request("evento/inutilizacionnumfactura/", "POST", data)

    def disable_credit_note(self, data):
        return self._request("evento/inutilizacionnumnotacredito/", "POST", data)

    def disable_delivery_note(self, data):
        return self._request("evento/inutilizacionnumremision/", "POST", data)

    def consult_inutilization(self, data):
        return self._request(
            "evento/inutilizacion/consultar/", "POST", data, timeout=60
        )

    # ----------------------------------------------------------------------
    # Normalización de respuestas
    # ----------------------------------------------------------------------
    def _map_django_state(self, state):
        mapping = {
            "borrador": "Borrador",
            "generado_xml": "Listo",
            "listo": "Listo",
            "pendiente": "Pendiente",
            "reintentable": "Pendiente",
            "en_cola": "Pendiente",
            "cola": "Pendiente",
            "enviado": "Enviado",
            "aprobado": "Aprobado",
            "rechazado": "Rechazado",
            "cancelado": "Cancelado",
            "inutilizado": "Inutilizado",
            "error": "Error",
        }
        state = (state or "").lower()
        return mapping.get(state, state or "")

    def _extract_response_message(self, result, document=None, query=None):
        document = document or {}
        query = query or {}
        document_response = document.get("respuesta_sifen") or {}
        sifen_result = result.get("resultado_sifen") or {}
        general_message = (
            document.get("mensaje_sifen")
            or document.get("respuesta")
            or result.get("respuesta")
            or result.get("mensaje")
            or ""
        )
        detail_message = (
            document_response.get("mensaje")
            or query.get("mensaje")
            or query.get("mensaje_sifen")
            or sifen_result.get("mensaje")
            or result.get("error")
            or ""
        )
        if (
            general_message
            and detail_message
            and general_message != detail_message
        ):
            return f"{general_message}: {detail_message}"
        return general_message or detail_message

    def normalize_response(self, result):
        """Adapta las respuestas de la API vigente al formato usado por Odoo."""
        if not isinstance(result, dict):
            return result

        document = result.get("documento")
        if isinstance(document, dict):
            query = result.get("consulta_sifen") or {}
            sifen_result = result.get("resultado_sifen") or {}
            code = (
                query.get("codigo_respuesta")
                or query.get("codigo_sifen")
                or document.get("codigo_sifen")
                or sifen_result.get("codigo_respuesta")
                or ""
            )
            state = document.get("estado") or result.get("estado") or query.get("estado")
            normalized_state = self._map_django_state(state)
            if (state or "").lower() == "rechazado" and code == "0422":
                normalized_state = "Enviado"
            if not normalized_state and (
                result.get("cdc") or document.get("cdc") or document.get("id")
            ):
                normalized_state = "Pendiente"
            return {
                "estado": normalized_state,
                "cdc": result.get("cdc") or document.get("cdc"),
                "qr": result.get("qr") or document.get("qr_url"),
                "respuesta": self._extract_response_message(result, document, query),
                "protocolo": document.get("protocolo"),
                "envio_sifen": result.get("envio_sifen")
                or document.get("cola_sifen"),
                "xml_firmado": document.get("xml_firmado")
                or result.get("xml_firmado"),
                "raw": result,
            }

        invoice = result.get("factura")
        if isinstance(invoice, dict):
            qr = result.get("qr") or {}
            warning = result.get("warning") or {}
            sending = result.get("envio_sifen") or {}
            state = self._map_django_state(invoice.get("estado"))
            if not state and (result.get("cdc") or invoice.get("cdc")):
                state = "Pendiente"
            return {
                "estado": state,
                "cdc": result.get("cdc") or invoice.get("cdc"),
                "qr": qr.get("url") if isinstance(qr, dict) else qr,
                "respuesta": (
                    invoice.get("mensaje_sifen")
                    or sending.get("mensaje")
                    or sending.get("error_message")
                    or warning.get("error")
                    or result.get("error")
                    or result.get("mensaje")
                    or ""
                ),
                "protocolo": invoice.get("protocolo"),
                "envio_sifen": sending,
                "xml_firmado": result.get("xml_firmado"),
                "raw": result,
            }

        if "estado_documento" in result:
            sifen_result = result.get("resultado_sifen") or {}
            state = self._map_django_state(result.get("estado_documento"))
            if not state and result.get("cdc"):
                state = "Pendiente"
            return {
                "estado": state,
                "cdc": result.get("cdc"),
                "respuesta": (
                    sifen_result.get("mensaje")
                    or result.get("error")
                    or result.get("motivo")
                    or result.get("mensaje")
                    or ""
                ),
                "raw": result,
            }

        if result.get("ok") is False:
            sifen_result = result.get("resultado_sifen") or {}
            message = (
                sifen_result.get("mensaje")
                or result.get("error")
                or result.get("mensaje")
                or result.get("respuesta")
                or ""
            )
            code = sifen_result.get("codigo_respuesta") or ""
            lower_message = message.lower()
            if "cancelado" in lower_message:
                state = "Cancelado"
            elif "inutilizado" in lower_message:
                state = "Inutilizado"
            elif "pendiente" in lower_message:
                state = "Pendiente"
            elif "cdc encontrado" in lower_message or code == "0422":
                state = "Enviado"
            else:
                state = "Error"
            return {
                "estado": state,
                "respuesta": f"[{code}] {message}" if code else message,
                "raw": result,
            }

        if result.get("estado") or result.get("cdc"):
            state = self._map_django_state(result.get("estado"))
            if not state and result.get("cdc"):
                state = "Pendiente"
            return {
                "estado": state,
                "cdc": result.get("cdc"),
                "qr": result.get("qr") or result.get("qr_url"),
                "respuesta": result.get("respuesta")
                or result.get("mensaje")
                or result.get("error")
                or "",
                "raw": result,
            }

        return result
