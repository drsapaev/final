"""Published contracts for patient-bound notification delivery and RSVP."""

from fastapi.testclient import TestClient


def test_telegram_delivery_requires_typed_bodies_and_documents_failures(client: TestClient):
    spec = client.get('/openapi.json').json()
    paths = spec['paths']
    routes = {
        '/api/v1/telegram/bot/send-appointment-reminder': 'SendAppointmentReminderRequest',
        '/api/v1/telegram/bot/send-lab-notification': 'SendLabNotificationRequest',
        '/api/v1/telegram/appointment-reminder': 'SendAppointmentReminderIntegrationRequest',
        '/api/v1/telegram/lab-results-notification': 'SendLabResultsNotificationRequest',
        '/api/v1/telegram/send-qr-code': 'SendQrCodeRequest',
    }
    for path, request_model in routes.items():
        operation = paths[path]['post']
        schema = operation['requestBody']['content']['application/json']['schema']
        # A free-form `dict` alternative would hide the expected client contract.
        assert schema == {'$ref': f'#/components/schemas/{request_model}'}
        assert {'200', '400', '403', '404', '409', '422', '502', '503'} <= set(operation['responses'])
        for status_code in ('400', '403', '404', '409', '502', '503'):
            error_schema = operation['responses'][status_code]['content']['application/json']['schema']
            assert error_schema['$ref'] == '#/components/schemas/TelegramDeliveryError'
        assert operation.get('security')

    appointment = spec['components']['schemas']['AppointmentData']['properties']
    assert {'id', 'appointment_id'} <= appointment.keys()
    lab = spec['components']['schemas']['LabResultsData']['properties']
    assert {'id', 'lab_result_id', 'lab_results_id'} <= lab.keys()


def test_telegram_visit_bearer_routes_are_deprecated_and_never_claim_success(client: TestClient):
    spec = client.get('/openapi.json').json()
    for action in ('confirm', 'cancel'):
        operation = spec['paths'][f'/api/v1/telegram/visits/{action}']['post']
        assert operation['deprecated'] is True
        assert '200' not in operation['responses']
        denied = operation['responses']['403']
        assert 'Cache-Control' in denied['headers']
        assert denied['content']['application/json']['schema']['$ref'] == '#/components/schemas/TelegramVisitActionDenied'


def test_appointment_rsvp_is_nullable_and_not_writable(client: TestClient):
    schemas = client.get('/openapi.json').json()['components']['schemas']
    response = schemas['Appointment']['properties']['patient_confirmed_at']
    assert {variant['type'] for variant in response['anyOf']} == {'string', 'null'}
    for name in ('AppointmentCreate', 'AppointmentUpdate'):
        assert 'patient_confirmed_at' not in schemas[name]['properties']


def test_email_sms_document_resource_and_payment_refusals(client: TestClient):
    paths = client.get('/openapi.json').json()['paths']
    expected = {
        'send-appointment-reminder-enhanced': {'200', '403', '404', '409', '500'},
        'send-lab-results-enhanced': {'200', '403', '404', '409', '500'},
        'send-payment-confirmation-enhanced': {'200', '400', '403', '404', '409', '500'},
    }
    for endpoint, statuses in expected.items():
        operation = paths[f'/api/v1/email-sms/{endpoint}']['post']
        assert statuses <= set(operation['responses'])
        assert operation.get('security')
        assert 'HTTP 200 reports the attempt' in operation['description']


def test_canonical_telegram_notifications_document_delivery_outcomes(client: TestClient):
    paths = client.get('/openapi.json').json()['paths']
    routes = {
        'send-appointment-reminder': {'200', '400', '403', '404', '409', '422', '500', '502', '503'},
        'send-lab-results': {'200', '400', '403', '404', '409', '422', '500', '502', '503'},
        'send-lab-report-instance': {'200', '400', '403', '404', '409', '422', '500', '503'},
        'send-payment-confirmation': {'200', '400', '403', '404', '409', '422', '500', '502', '503'},
    }
    for endpoint, statuses in routes.items():
        operation = paths[f'/api/v1/telegram/{endpoint}']['post']
        assert statuses <= set(operation['responses'])
        assert operation.get('security')
        for status_code in statuses - {'200', '422'}:
            error_schema = operation['responses'][status_code]['content']['application/json']['schema']
            assert error_schema['$ref'] == '#/components/schemas/TelegramDeliveryError'

    for endpoint in ('send-lab-results', 'send-lab-report-instance', 'send-payment-confirmation'):
        assert 'success' in paths[f'/api/v1/telegram/{endpoint}']['post']['description']
