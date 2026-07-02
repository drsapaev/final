from __future__ import annotations


def test_legacy_print_pdf_routes_are_not_mounted(client, auth_headers):
    response_ticket = client.get("/api/v1/print/ticket.pdf", headers=auth_headers)
    response_invoice = client.get("/api/v1/print/invoice.pdf", headers=auth_headers)

    assert response_ticket.status_code == 404
    assert response_invoice.status_code == 404


def test_ssot_print_routes_remain_available(client, auth_headers, db_session):
    printers_response = client.get("/api/v1/print/printers", headers=auth_headers)
    assert printers_response.status_code == 200
    payload = printers_response.json()
    assert "printers" in payload
    assert isinstance(payload["printers"], list)
