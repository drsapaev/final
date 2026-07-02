from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints import admin_telegram
from app.models.telegram_config import (
    TelegramStaffConfirmationToken,
    TelegramStaffLinkToken,
)
from app.services.telegram_staff_link_token_service import (
    TelegramStaffLinkTokenService,
)
from app.services.telegram_staff_confirmation_token_service import (
    TelegramStaffConfirmationTokenService,
)
from app.services.telegram_bot_management_api_service import (
    TelegramBotManagementApiService,
)


@pytest.mark.unit
class TestTelegramBotManagementApiService:
    def _staff_link_token(
        self,
        *,
        user_id: int = 42,
        chat_id: int = 998877,
        nonce: str = "unitnonce",
    ) -> str:
        return admin_telegram.build_staff_link_start_token(
            user_id=user_id,
            chat_id=chat_id,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            nonce=nonce,
        )

    def test_get_stats_payload_uses_repository_counts(self):
        repository = SimpleNamespace(
            count_users_with_telegram=lambda: 10,
            count_active_users_with_telegram=lambda: 7,
            count_admin_users_with_telegram=lambda: 2,
            list_active_user_ids_with_telegram=lambda: [],
            list_users_with_telegram=lambda: [],
        )
        service = TelegramBotManagementApiService(db=None, repository=repository)

        payload = service.get_stats_payload()

        assert payload["total_users"] == 10
        assert payload["active_users"] == 7
        assert payload["admin_users"] == 2
        assert payload["messages_sent_today"] == 0

    def test_list_active_user_recipients_returns_ids(self):
        repository = SimpleNamespace(
            count_users_with_telegram=lambda: 0,
            count_active_users_with_telegram=lambda: 0,
            count_admin_users_with_telegram=lambda: 0,
            list_active_user_ids_with_telegram=lambda: [1, 2, 3],
            list_users_with_telegram=lambda: [],
        )
        service = TelegramBotManagementApiService(db=None, repository=repository)

        recipients = service.list_active_user_recipients()

        assert recipients == [1, 2, 3]
        assert service.count_admin_recipients() == 0

    def test_get_users_with_telegram_payload_maps_user_fields(self):
        repository = SimpleNamespace(
            count_users_with_telegram=lambda: 0,
            count_active_users_with_telegram=lambda: 0,
            count_admin_users_with_telegram=lambda: 0,
            list_active_user_ids_with_telegram=lambda: [],
            list_users_with_telegram=lambda: [
                SimpleNamespace(
                    id=5,
                    username="user5",
                    full_name="User Five",
                    role="Doctor",
                    telegram_chat_id="12345",
                    is_active=True,
                    created_at=datetime(2026, 2, 1, 10, 0, 0),
                )
            ],
        )
        service = TelegramBotManagementApiService(db=None, repository=repository)

        payload = service.get_users_with_telegram_payload()

        assert payload["total_count"] == 1
        assert payload["users"][0]["username"] == "user5"
        assert payload["users"][0]["telegram_chat_id"] == "12345"

    def test_staff_link_start_token_round_trips_with_hash_only_contract(self):
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        token = admin_telegram.build_staff_link_start_token(
            user_id=42,
            chat_id=998877,
            expires_at=expires_at,
            nonce="unitnonce",
        )
        parsed = admin_telegram.parse_staff_link_start_token(token)

        assert parsed is not None
        assert parsed["user_id"] == 42
        assert parsed["chat_id"] == 998877
        assert parsed["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )

    def test_staff_link_token_storage_contract_matches_model_columns(self):
        contract = admin_telegram.STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT
        table = TelegramStaffLinkToken.__table__

        assert table.name == contract["table"]
        assert contract["enabled"] is True
        assert contract["migration_created"] is True
        assert contract["runtime_write_enabled"] is True
        assert contract["migration_revision"] == "0025_telegram_staff_link_tokens"
        assert list(table.columns.keys()) == contract["columns"]
        assert contract["raw_token_storage_allowed"] is False
        assert "raw_token" not in table.columns
        assert "token" not in table.columns
        assert table.c.token_hash.unique is True
        assert table.c.token_hash.nullable is False
        assert table.c.staff_user_id.nullable is False
        assert table.c.telegram_chat_id.nullable is False
        assert table.c.expires_at.nullable is False

        staff_fk = next(iter(table.c.staff_user_id.foreign_keys))
        assert staff_fk.target_fullname == "users.id"
        assert staff_fk.ondelete == "CASCADE"

    def test_staff_link_token_storage_model_has_required_indexes(self):
        contract = admin_telegram.STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT
        table = TelegramStaffLinkToken.__table__

        assert "unique(token_hash)" in contract["required_indexes"]
        assert "index(staff_user_id)" in contract["required_indexes"]
        assert "index(telegram_chat_id)" in contract["required_indexes"]
        assert (
            "partial_index(expires_at) where consumed_at is null"
            in contract["required_indexes"]
        )

        indexes_by_name = {index.name: index for index in table.indexes}
        assert indexes_by_name["ix_telegram_staff_link_tokens_token_hash"].unique
        assert [
            column.name
            for column in indexes_by_name[
                "ix_telegram_staff_link_tokens_staff_user_id"
            ].columns
        ] == ["staff_user_id"]
        assert [
            column.name
            for column in indexes_by_name[
                "ix_telegram_staff_link_tokens_telegram_chat_id"
            ].columns
        ] == ["telegram_chat_id"]

        partial_index = indexes_by_name[
            "ix_telegram_staff_link_tokens_unconsumed_expires"
        ]
        assert [column.name for column in partial_index.columns] == ["expires_at"]
        assert (
            str(partial_index.dialect_options["postgresql"]["where"]).lower()
            == "consumed_at is null"
        )

    def test_staff_link_token_storage_model_has_required_constraints(self):
        contract = admin_telegram.STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT
        table = TelegramStaffLinkToken.__table__

        assert "expires_at > created_at" in contract["required_constraints"]
        assert (
            "consumed_at is null or consumed_at <= expires_at"
            in contract["required_constraints"]
        )
        assert "staff_user_id references users(id)" in contract[
            "required_constraints"
        ]

        constraint_names = {
            constraint.name for constraint in table.constraints if constraint.name
        }
        assert "ck_telegram_staff_link_tokens_expires_after_created" in constraint_names
        assert (
            "ck_telegram_staff_link_tokens_consumed_before_expiry"
            in constraint_names
        )

    def test_staff_confirmation_token_storage_contract_matches_model_columns(self):
        contract = admin_telegram.STAFF_BOT_CONFIRMATION_TOKEN_STORAGE_CONTRACT
        table = TelegramStaffConfirmationToken.__table__

        assert table.name == contract["table"]
        assert contract["enabled"] is True
        assert contract["migration_created"] is True
        assert contract["model_registered"] is True
        assert contract["runtime_write_enabled"] is True
        assert contract["runtime_consume_enabled"] is True
        assert contract["migration_revision"] == "0026_tg_staff_confirm_tokens"
        assert contract["repository"] == "TelegramStaffConfirmationTokenRepository"
        assert contract["service"] == "TelegramStaffConfirmationTokenService"
        assert list(table.columns.keys()) == contract["columns"]
        assert contract["raw_token_storage_allowed"] is False
        assert "raw_token" not in table.columns
        assert "token" not in table.columns
        assert table.c.token_hash.unique is True
        assert table.c.token_hash.nullable is False
        assert table.c.staff_user_id.nullable is False
        assert table.c.telegram_chat_id.nullable is False
        assert table.c.operation_key.nullable is False
        assert table.c.action_payload_hash.nullable is False
        assert table.c.expires_at.nullable is False

        staff_fk = next(iter(table.c.staff_user_id.foreign_keys))
        assert staff_fk.target_fullname == "users.id"
        assert staff_fk.ondelete == "CASCADE"

    def test_staff_confirmation_token_storage_model_has_required_indexes(self):
        contract = admin_telegram.STAFF_BOT_CONFIRMATION_TOKEN_STORAGE_CONTRACT
        table = TelegramStaffConfirmationToken.__table__

        assert "unique(token_hash)" in contract["required_indexes"]
        assert "index(staff_user_id)" in contract["required_indexes"]
        assert "index(telegram_chat_id)" in contract["required_indexes"]
        assert "index(operation_key)" in contract["required_indexes"]
        assert (
            "partial_index(expires_at) where consumed_at is null"
            in contract["required_indexes"]
        )

        indexes_by_name = {index.name: index for index in table.indexes}
        assert indexes_by_name[
            "ix_telegram_staff_confirmation_tokens_token_hash"
        ].unique
        assert [
            column.name
            for column in indexes_by_name[
                "ix_telegram_staff_confirmation_tokens_staff_user_id"
            ].columns
        ] == ["staff_user_id"]
        assert [
            column.name
            for column in indexes_by_name[
                "ix_telegram_staff_confirmation_tokens_telegram_chat_id"
            ].columns
        ] == ["telegram_chat_id"]
        assert [
            column.name
            for column in indexes_by_name[
                "ix_telegram_staff_confirmation_tokens_operation_key"
            ].columns
        ] == ["operation_key"]

        partial_index = indexes_by_name[
            "ix_telegram_staff_confirmation_tokens_unconsumed_expires"
        ]
        assert [column.name for column in partial_index.columns] == ["expires_at"]
        assert (
            str(partial_index.dialect_options["postgresql"]["where"]).lower()
            == "consumed_at is null"
        )

    def test_staff_confirmation_token_storage_model_has_required_constraints(self):
        contract = admin_telegram.STAFF_BOT_CONFIRMATION_TOKEN_STORAGE_CONTRACT
        table = TelegramStaffConfirmationToken.__table__

        assert "expires_at > created_at" in contract["required_constraints"]
        assert (
            "consumed_at is null or consumed_at <= expires_at"
            in contract["required_constraints"]
        )
        assert "operation_key is not empty" in contract["required_constraints"]
        assert "action_payload_hash is not empty" in contract["required_constraints"]
        assert "staff_user_id references users(id)" in contract[
            "required_constraints"
        ]

        constraint_names = {
            constraint.name for constraint in table.constraints if constraint.name
        }
        assert (
            "ck_telegram_staff_confirmation_tokens_expires_after_created"
            in constraint_names
        )
        assert (
            "ck_telegram_staff_confirmation_tokens_consumed_before_expiry"
            in constraint_names
        )
        assert (
            "ck_telegram_staff_confirmation_tokens_operation_not_empty"
            in constraint_names
        )
        assert (
            "ck_telegram_staff_confirmation_tokens_payload_hash_not_empty"
            in constraint_names
        )

    def test_staff_bot_status_remains_disabled_until_readiness_gates(self):
        status = admin_telegram._build_staff_bot_status(webhook_set=False)

        assert status["enabled"] is False
        assert status["state_changing_actions_enabled"] is False
        assert status["role_linking"]["enabled"] is True
        assert status["role_linking"]["runtime_handler_enabled"] is True
        assert status["authorization"]["ready"] is True
        assert status["authorization"]["runtime_read_only_enabled"] is True
        assert status["audit"]["ready"] is True
        assert status["audit"]["linking_events_ready"] is True
        assert status["audit"]["staff_command_events_ready"] is True
        assert status["audit"]["read_only_menu_events_ready"] is True
        assert status["audit"]["confirmation_request_events_ready"] is True
        assert status["audit"]["state_change_events_ready"] is True
        assert status["role_menus"]["read_only"] is True
        assert status["role_menus"]["runtime_enabled"] is True
        assert status["role_menus"]["state_changing_actions_enabled"] is False
        assert status["confirmations"]["ready"] is True
        assert status["confirmations"]["runtime_guard_enabled"] is True
        assert status["confirmations"]["deny_only_runtime_enabled"] is False
        assert status["confirmations"]["confirmation_request_runtime_enabled"] is True
        assert status["confirmations"]["confirmation_requests_create_tokens"] is True
        assert (
            status["confirmations"]["confirmation_token_runtime_enabled"] is True
        )
        assert (
            status["confirmations"]["idempotency_request_hash_runtime_enabled"]
            is True
        )
        assert status["confirmations"]["idempotency_key_returned_to_telegram"] is False
        assert status["confirmations"]["state_changing_actions_enabled"] is False
        assert (
            status["confirmations"]["default_state_change_decision"]
            == "deny_until_domain_adapters_and_action_enablement"
        )

        role_menu_enablement = status["role_menu_enablement_contract"]
        assert role_menu_enablement["enabled"] is True
        assert role_menu_enablement["runtime_menu_enabled"] is True
        assert role_menu_enablement["state_changing_menu_items_enabled"] is False
        assert role_menu_enablement["domain_data_commands_enabled"] is True
        assert role_menu_enablement["domain_data_commands_status"] == "complete"
        assert role_menu_enablement["domain_data_command_keys"] == [
            "staff_readiness",
            "queue_overview",
            "next_patient",
            "today_schedule",
            "emr_reminders",
            "unpaid_invoices",
            "paid_invoices",
            "reconciliation_alerts",
            "payment_status",
            "ready_reports",
            "pending_reports",
            "delivery_status",
            "integration_errors",
            "revenue_summary",
            "daily_summary",
        ]

    @pytest.mark.parametrize(
        ("webhook_set", "expected_transport"),
        [
            (False, "polling"),
            (True, "webhook"),
        ],
    )
    def test_staff_bot_status_exposes_contract_bundle_and_next_slice(
        self, webhook_set, expected_transport
    ):
        status = admin_telegram._build_staff_bot_status(webhook_set=webhook_set)

        assert status["transport"] == expected_transport
        assert status["next_slice"] == "dedicated_staff_bot_token_runtime_config"
        assert status["supported_roles"] == admin_telegram.STAFF_BOT_SUPPORTED_ROLES
        assert status["read_only_menu_contract"] == (
            admin_telegram.STAFF_BOT_READ_ONLY_MENU_CONTRACT
        )

        expected_contract_keys = {
            "token_contract",
            "linking_contract",
            "linking_runtime_contract",
            "link_token_validation_contract",
            "link_token_storage_contract",
            "confirmation_token_storage_contract",
            "authorization_contract",
            "command_registration_contract",
            "confirmation_contract",
            "domain_adapter_contract",
            "audit_contract",
        }
        assert expected_contract_keys <= set(status)
        assert status["link_token_storage_contract"] == (
            admin_telegram.STAFF_BOT_LINK_TOKEN_STORAGE_CONTRACT
        )
        assert status["link_token_validation_contract"]["storage_contract"] == (
            status["link_token_storage_contract"]
        )
        assert status["confirmation_token_storage_contract"] == (
            admin_telegram.STAFF_BOT_CONFIRMATION_TOKEN_STORAGE_CONTRACT
        )
        assert status["confirmation_contract"]["token_storage_contract"] == (
            status["confirmation_token_storage_contract"]
        )
        assert status["domain_adapter_contract"] == (
            admin_telegram.STAFF_BOT_DOMAIN_ADAPTER_CONTRACT
        )
        assert status["confirmation_contract"]["domain_adapter_contract"] == (
            status["domain_adapter_contract"]
        )
        adapters_by_operation = {
            adapter["operation_key"]: adapter
            for adapter in status["domain_adapter_contract"]["adapters"]
        }
        assert set(adapters_by_operation) == {
            "queue_call_or_skip_patient",
            "visit_cancel_or_move",
            "payment_status_change",
            "refund_issue",
            "doctor_schedule_change",
        }
        queue_adapter = adapters_by_operation["queue_call_or_skip_patient"]
        assert queue_adapter["adapter_key"] == "staff_queue_call_or_skip_adapter"
        assert queue_adapter["domain"] == "queue"
        assert queue_adapter["telegram_commands"] == ["/call", "/skip"]
        assert queue_adapter["runtime_enabled"] is True
        assert queue_adapter["runtime_owner"] == "QueueBusinessService"
        assert queue_adapter["runtime_methods"] == [
            "staff_call_next_patient",
            "staff_skip_queue_entry",
        ]
        assert "queue_time_not_rewritten" in queue_adapter["required_runtime_checks"]
        assert "queue_domain_mutation_adapter" not in queue_adapter["blocked_by"]
        assert "explicit_action_enablement" in queue_adapter["blocked_by"]
        visit_adapter = adapters_by_operation["visit_cancel_or_move"]
        assert (
            visit_adapter["adapter_key"] == "staff_queue_visit_cancel_or_move_adapter"
        )
        assert visit_adapter["domain"] == "queue"
        assert visit_adapter["telegram_commands"] == [
            "/cancel_visit",
            "/move_visit",
        ]
        assert visit_adapter["runtime_enabled"] is True
        assert visit_adapter["runtime_scope"] == "visit_record_and_queue_link_status"
        assert visit_adapter["runtime_owner"] == "TelegramStaffActionAdapterService"
        assert visit_adapter["runtime_methods"] == [
            "staff_cancel_visit",
            "staff_move_visit",
        ]
        assert visit_adapter["queue_link_runtime_owner"] == "QueueBusinessService"
        assert visit_adapter["queue_link_runtime_methods"] == [
            "staff_cancel_visit_queue_link",
            "staff_move_visit_queue_link",
        ]
        assert visit_adapter["visit_record_mutation_enabled"] is True
        assert "queue_fairness_not_reordered" in visit_adapter[
            "required_runtime_checks"
        ]
        assert "queue_time_not_rewritten" in visit_adapter[
            "required_runtime_checks"
        ]
        assert "visit_record_mutation_adapter" not in visit_adapter["blocked_by"]
        assert "explicit_action_enablement" in visit_adapter["blocked_by"]
        payment_adapter = adapters_by_operation["payment_status_change"]
        assert payment_adapter["adapter_key"] == "staff_payment_status_change_adapter"
        assert payment_adapter["domain"] == "payment"
        assert payment_adapter["telegram_commands"] == ["/payment_status"]
        assert payment_adapter["runtime_enabled"] is True
        assert payment_adapter["runtime_owner"] == "TelegramStaffActionAdapterService"
        assert payment_adapter["runtime_methods"] == ["staff_change_payment_status"]
        assert "payment_status_transition_validated_by_billing_service" in payment_adapter[
            "required_runtime_checks"
        ]
        assert "explicit_action_enablement" in payment_adapter["blocked_by"]
        refund_adapter = adapters_by_operation["refund_issue"]
        assert refund_adapter["adapter_key"] == "staff_payment_refund_adapter"
        assert refund_adapter["domain"] == "payment"
        assert refund_adapter["telegram_commands"] == ["/refund"]
        assert refund_adapter["runtime_enabled"] is True
        assert refund_adapter["runtime_owner"] == "TelegramStaffActionAdapterService"
        assert refund_adapter["runtime_methods"] == ["staff_refund_payment"]
        assert "refund_amount_within_available_balance" in refund_adapter[
            "required_runtime_checks"
        ]
        assert "explicit_action_enablement" in refund_adapter["blocked_by"]
        schedule_adapter = adapters_by_operation["doctor_schedule_change"]
        assert schedule_adapter["adapter_key"] == "staff_schedule_change_adapter"
        assert schedule_adapter["domain"] == "schedule"
        assert schedule_adapter["telegram_commands"] == ["/change_schedule"]
        assert schedule_adapter["runtime_enabled"] is True
        assert schedule_adapter["runtime_owner"] == "TelegramStaffActionAdapterService"
        assert schedule_adapter["runtime_methods"] == ["staff_change_doctor_schedule"]
        assert "schedule_time_range_validated" in schedule_adapter[
            "required_runtime_checks"
        ]
        assert "explicit_action_enablement" in schedule_adapter["blocked_by"]
        assert status["linking_contract"]["enabled"] is True
        assert (
            status["linking_runtime_contract"]["runtime_handler"]
            == "_handle_staff_link_start"
        )
        assert status["linking_runtime_contract"]["runtime_handler_enabled"] is True
        assert "audit_logs" in status["linking_runtime_contract"]["writes"]
        assert status["link_token_validation_contract"]["enabled"] is True
        assert status["link_token_validation_contract"]["handler_enabled"] is True
        assert (
            status["link_token_validation_contract"]["single_use_enforcement_enabled"]
            is True
        )
        assert status["link_token_validation_contract"]["token_storage_enabled"] is True
        assert (
            status["link_token_validation_contract"]["storage_migration_required"]
            is False
        )
        assert status["audit_contract"]["record_writer_enabled"] is True
        assert status["audit_contract"]["runtime_read_only_enabled"] is True
        assert "staff_link_created" in status["audit_contract"]["recorded_event_types"]
        assert (
            "staff_link_token_rejected"
            in status["audit_contract"]["recorded_event_types"]
        )
        assert (
            "staff_command_received"
            in status["audit_contract"]["recorded_event_types"]
        )
        assert (
            "staff_command_received"
            not in status["audit_contract"]["pending_event_types"]
        )
        assert (
            "staff_action_confirmation_requested"
            in status["audit_contract"]["recorded_event_types"]
        )
        assert (
            "staff_action_confirmation_requested"
            not in status["audit_contract"]["pending_event_types"]
        )
        assert status["confirmation_contract"]["enabled"] is True
        assert status["confirmation_contract"]["runtime_guard_enabled"] is True
        assert status["confirmation_contract"]["deny_only_runtime_enabled"] is False
        assert (
            status["confirmation_contract"]["confirmation_request_runtime_enabled"]
            is True
        )
        assert (
            status["confirmation_contract"]["confirmation_requests_create_tokens"]
            is True
        )
        assert (
            status["confirmation_contract"]["confirmation_token_runtime_enabled"]
            is True
        )
        assert (
            status["confirmation_contract"]["idempotency_request_hash_runtime_enabled"]
            is True
        )
        assert (
            status["confirmation_contract"]["idempotency_key_returned_to_telegram"]
            is False
        )
        assert status["confirmation_contract"]["state_changing_actions_enabled"] is False
        assert (
            "confirmation_token_persistence"
            not in status["confirmation_contract"]["runtime_blocked_by"]
        )
        assert (
            "idempotency_runtime"
            not in status["confirmation_contract"]["runtime_blocked_by"]
        )
        assert (
            status["confirmation_contract"]["runtime_blocked_by"][0]
            == "domain_service_action_adapters"
        )
        assert status["confirmations"]["domain_adapter_runtime_enabled"] is True
        assert status["confirmations"]["queue_action_adapter_runtime_enabled"] is True
        assert (
            status["confirmations"]["visit_queue_link_adapter_runtime_enabled"]
            is True
        )
        assert status["confirmations"]["domain_adapter_blockers"] == (
            admin_telegram.STAFF_BOT_DOMAIN_ADAPTER_CONTRACT["blocked_by"]
        )

    def test_staff_link_start_token_validator_reports_expired_reason(self):
        token = admin_telegram.build_staff_link_start_token(
            user_id=42,
            chat_id=998877,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            nonce="expirednonce",
        )

        result = admin_telegram.validate_staff_link_start_token(
            db=object(),
            token=token,
            telegram_chat_id=998877,
        )

        assert result["valid"] is False
        assert result["reason"] == "expired"
        assert result["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )
        assert admin_telegram.parse_staff_link_start_token(token) is None

    def test_staff_link_start_token_validator_accepts_active_staff(
        self, monkeypatch
    ):
        token = admin_telegram.build_staff_link_start_token(
            user_id=42,
            chat_id=998877,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            nonce="validnonce",
        )
        user = SimpleNamespace(id=42, role="Laboratory", is_active=True)

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return user

        db = SimpleNamespace(query=lambda _model: FakeQuery())
        monkeypatch.setattr(
            admin_telegram.crud_telegram,
            "get_telegram_user_by_chat_id",
            lambda _db, _chat_id: SimpleNamespace(user_id=None),
        )
        monkeypatch.setattr(
            admin_telegram.crud_telegram,
            "get_telegram_user_by_linked_user_id",
            lambda _db, _linked_user_id: None,
        )

        result = admin_telegram.validate_staff_link_start_token(
            db=db,
            token=token,
            telegram_chat_id=998877,
            enforce_single_use=False,
        )

        assert result["valid"] is True
        assert result["reason"] == "ok"
        assert result["user_id"] == 42
        assert result["chat_id"] == 998877
        assert result["role"] == "lab"
        assert result["single_use_enforced"] is False

    def test_staff_link_token_service_issues_hash_only_record(
        self, db_session, admin_user
    ):
        token = self._staff_link_token(user_id=admin_user.id, chat_id=700700)
        parsed = admin_telegram.parse_staff_link_start_token(token)
        service = TelegramStaffLinkTokenService(db_session)

        record = service.issue_token(
            token_hash=parsed["token_hash"],
            staff_user_id=admin_user.id,
            telegram_chat_id=700700,
            expires_at=parsed["expires_at"],
            issued_by_user_id=admin_user.id,
            request_id="req-storage-1",
        )
        db_session.commit()

        stored = (
            db_session.query(TelegramStaffLinkToken)
            .filter(TelegramStaffLinkToken.id == record.id)
            .one()
        )
        assert stored.token_hash == parsed["token_hash"]
        assert stored.token_hash != token
        assert stored.consumed_at is None
        assert stored.request_id == "req-storage-1"

    def test_staff_link_token_service_consumes_record_once(
        self, db_session, admin_user
    ):
        token = self._staff_link_token(user_id=admin_user.id, chat_id=700701)
        parsed = admin_telegram.parse_staff_link_start_token(token)
        service = TelegramStaffLinkTokenService(db_session)
        service.issue_token(
            token_hash=parsed["token_hash"],
            staff_user_id=admin_user.id,
            telegram_chat_id=700701,
            expires_at=parsed["expires_at"],
        )
        db_session.commit()

        first = service.consume_for_validation(
            token_hash=parsed["token_hash"],
            staff_user_id=admin_user.id,
            telegram_chat_id=700701,
        )
        second = service.consume_for_validation(
            token_hash=parsed["token_hash"],
            staff_user_id=admin_user.id,
            telegram_chat_id=700701,
        )

        assert first["valid"] is True
        assert first["single_use_enforced"] is True
        assert second == {"valid": False, "reason": "already_used"}

    def test_staff_confirmation_token_service_issues_hash_only_record(
        self, db_session, admin_user
    ):
        raw_token = "plain-confirm-token"
        service = TelegramStaffConfirmationTokenService(db_session)

        record = service.issue_token(
            token_hash="staff_confirmation_token:" + ("a" * 64),
            staff_user_id=admin_user.id,
            telegram_chat_id=700800,
            operation_key="payment_status_change",
            command_key="/payment_status",
            action_payload_hash="payload:" + ("b" * 64),
            target_type="payment",
            target_reference_hash="target:" + ("c" * 64),
            idempotency_key_hash="idempotency:" + ("d" * 64),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
            request_id="req-confirm-1",
        )

        stored = (
            db_session.query(TelegramStaffConfirmationToken)
            .filter(TelegramStaffConfirmationToken.id == record.id)
            .one()
        )
        assert stored.token_hash.startswith("staff_confirmation_token:")
        assert stored.token_hash != raw_token
        assert stored.operation_key == "payment_status_change"
        assert stored.command_key == "/payment_status"
        assert stored.action_payload_hash.startswith("payload:")
        assert stored.target_reference_hash.startswith("target:")
        assert stored.idempotency_key_hash.startswith("idempotency:")
        assert stored.consumed_at is None
        assert stored.request_id == "req-confirm-1"

    def test_staff_confirmation_token_service_consumes_record_once(
        self, db_session, admin_user
    ):
        service = TelegramStaffConfirmationTokenService(db_session)
        token_hash = "staff_confirmation_token:" + ("e" * 64)
        payload_hash = "payload:" + ("f" * 64)
        idempotency_hash = "idempotency:" + ("1" * 64)
        issued_at = datetime.now(timezone.utc)
        consumed_at = issued_at + timedelta(seconds=1)
        service.issue_token(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700801,
            operation_key="queue_call_or_skip_patient",
            command_key="/queue",
            action_payload_hash=payload_hash,
            target_type="queue",
            idempotency_key_hash=idempotency_hash,
            expires_at=issued_at + timedelta(minutes=2),
            request_id="req-confirm-once",
        )

        first = service.consume_for_confirmation(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700801,
            operation_key="queue_call_or_skip_patient",
            action_payload_hash=payload_hash,
            idempotency_key_hash=idempotency_hash,
            now=consumed_at,
        )
        second = service.consume_for_confirmation(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700801,
            operation_key="queue_call_or_skip_patient",
            action_payload_hash=payload_hash,
            idempotency_key_hash=idempotency_hash,
            now=consumed_at + timedelta(seconds=5),
        )

        assert first["valid"] is True
        assert first["reason"] == "ok"
        assert first["single_use_enforced"] is True
        assert first["operation_key"] == "queue_call_or_skip_patient"
        assert second == {
            "valid": False,
            "reason": "already_used",
            "single_use_enforced": True,
            "operation_key": "queue_call_or_skip_patient",
            "command_key": "/queue",
            "target_type": "queue",
            "request_id": "req-confirm-once",
            "consumed_at": consumed_at.isoformat(),
        }

    def test_staff_confirmation_token_service_rejects_expired_record_without_consuming(
        self, db_session, admin_user
    ):
        service = TelegramStaffConfirmationTokenService(db_session)
        token_hash = "staff_confirmation_token:" + ("7" * 64)
        payload_hash = "payload:" + ("8" * 64)
        idempotency_hash = "idempotency:" + ("9" * 64)
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(seconds=30)
        service.issue_token(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700803,
            operation_key="payment_status_change",
            command_key="/payment_status",
            action_payload_hash=payload_hash,
            target_type="payment",
            idempotency_key_hash=idempotency_hash,
            expires_at=expires_at,
            request_id="req-confirm-expired",
        )

        result = service.consume_for_confirmation(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700803,
            operation_key="payment_status_change",
            action_payload_hash=payload_hash,
            idempotency_key_hash=idempotency_hash,
            now=expires_at + timedelta(seconds=1),
        )
        stored = (
            db_session.query(TelegramStaffConfirmationToken)
            .filter(TelegramStaffConfirmationToken.token_hash == token_hash)
            .one()
        )

        assert result == {"valid": False, "reason": "expired"}
        assert stored.consumed_at is None

    @pytest.mark.parametrize(
        ("staff_user_delta", "telegram_chat_id"),
        [
            (1, 700804),
            (0, 700805),
        ],
    )
    def test_staff_confirmation_token_service_rejects_binding_mismatch_without_consuming(
        self, db_session, admin_user, staff_user_delta, telegram_chat_id
    ):
        service = TelegramStaffConfirmationTokenService(db_session)
        token_hash = "staff_confirmation_token:" + ("6" * 64)
        payload_hash = "payload:" + ("5" * 64)
        service.issue_token(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700804,
            operation_key="visit_cancel_or_move",
            command_key="/move",
            action_payload_hash=payload_hash,
            target_type="visit",
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
            request_id="req-confirm-binding",
        )

        result = service.consume_for_confirmation(
            token_hash=token_hash,
            staff_user_id=admin_user.id + staff_user_delta,
            telegram_chat_id=telegram_chat_id,
            operation_key="visit_cancel_or_move",
            action_payload_hash=payload_hash,
        )
        stored = (
            db_session.query(TelegramStaffConfirmationToken)
            .filter(TelegramStaffConfirmationToken.token_hash == token_hash)
            .one()
        )

        assert result == {"valid": False, "reason": "token_binding_mismatch"}
        assert stored.consumed_at is None

    def test_staff_confirmation_token_service_rejects_action_mismatch(
        self, db_session, admin_user
    ):
        service = TelegramStaffConfirmationTokenService(db_session)
        token_hash = "staff_confirmation_token:" + ("9" * 64)
        service.issue_token(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700802,
            operation_key="visit_cancel_or_move",
            action_payload_hash="payload:" + ("2" * 64),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
        )

        result = service.consume_for_confirmation(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700802,
            operation_key="visit_cancel_or_move",
            action_payload_hash="payload:" + ("3" * 64),
        )
        stored = (
            db_session.query(TelegramStaffConfirmationToken)
            .filter(TelegramStaffConfirmationToken.token_hash == token_hash)
            .one()
        )

        assert result == {"valid": False, "reason": "action_binding_mismatch"}
        assert stored.consumed_at is None

    def test_staff_confirmation_token_service_rejects_idempotency_mismatch_without_consuming(
        self, db_session, admin_user
    ):
        service = TelegramStaffConfirmationTokenService(db_session)
        token_hash = "staff_confirmation_token:" + ("4" * 64)
        payload_hash = "payload:" + ("3" * 64)
        service.issue_token(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700806,
            operation_key="payment_status_change",
            action_payload_hash=payload_hash,
            idempotency_key_hash="idempotency:" + ("2" * 64),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=2),
            request_id="req-confirm-idempotency",
        )

        result = service.consume_for_confirmation(
            token_hash=token_hash,
            staff_user_id=admin_user.id,
            telegram_chat_id=700806,
            operation_key="payment_status_change",
            action_payload_hash=payload_hash,
            idempotency_key_hash="idempotency:" + ("1" * 64),
        )
        stored = (
            db_session.query(TelegramStaffConfirmationToken)
            .filter(TelegramStaffConfirmationToken.token_hash == token_hash)
            .one()
        )

        assert result == {"valid": False, "reason": "action_binding_mismatch"}
        assert stored.consumed_at is None

    def test_staff_link_start_token_validator_consumes_storage_record(
        self, db_session, admin_user
    ):
        token = admin_telegram.issue_staff_link_start_token(
            db_session,
            user_id=admin_user.id,
            chat_id=700702,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            issued_by_user_id=admin_user.id,
            request_id="req-validator-consume",
            nonce="consumeonce",
        )

        result = admin_telegram.validate_staff_link_start_token(
            db=db_session,
            token=token,
            telegram_chat_id=700702,
        )
        replay = admin_telegram.validate_staff_link_start_token(
            db=db_session,
            token=token,
            telegram_chat_id=700702,
        )

        record = (
            db_session.query(TelegramStaffLinkToken)
            .filter(TelegramStaffLinkToken.token_hash == result["token_hash"])
            .one()
        )
        assert result["valid"] is True
        assert result["single_use_enforced"] is True
        assert record.consumed_at is not None
        assert replay["valid"] is False
        assert replay["reason"] == "already_used"

    def test_staff_link_start_token_validator_rejects_chat_mismatch(self):
        token = self._staff_link_token()

        def fail_query(_model):
            pytest.fail("chat mismatch should be rejected before user lookup")

        result = admin_telegram.validate_staff_link_start_token(
            db=SimpleNamespace(query=fail_query),
            token=token,
            telegram_chat_id=112233,
        )

        assert result["valid"] is False
        assert result["reason"] == "chat_mismatch"
        assert result["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )

    @pytest.mark.parametrize(
        ("user", "expected_reason", "expected_role"),
        [
            (
                SimpleNamespace(id=42, role="doctor", is_active=False),
                "staff_user_inactive",
                None,
            ),
            (
                SimpleNamespace(id=42, role="patient", is_active=True),
                "role_not_allowed",
                "patient",
            ),
        ],
    )
    def test_staff_link_start_token_validator_rejects_invalid_staff_user(
        self, user, expected_reason, expected_role
    ):
        token = self._staff_link_token()

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return user

        result = admin_telegram.validate_staff_link_start_token(
            db=SimpleNamespace(query=lambda _model: FakeQuery()),
            token=token,
            telegram_chat_id=998877,
        )

        assert result["valid"] is False
        assert result["reason"] == expected_reason
        if expected_role is not None:
            assert result["role"] == expected_role
        assert result["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )

    def test_staff_link_start_token_validator_rejects_linked_chat_conflict(
        self, monkeypatch
    ):
        token = self._staff_link_token(nonce="linkedchat")
        user = SimpleNamespace(id=42, role="doctor", is_active=True)

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return user

        monkeypatch.setattr(
            admin_telegram.crud_telegram,
            "get_telegram_user_by_chat_id",
            lambda _db, _chat_id: SimpleNamespace(user_id=777),
        )

        result = admin_telegram.validate_staff_link_start_token(
            db=SimpleNamespace(query=lambda _model: FakeQuery()),
            token=token,
            telegram_chat_id=998877,
        )

        assert result["valid"] is False
        assert result["reason"] == "telegram_account_already_linked"
        assert result["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )

    def test_staff_link_start_token_validator_rejects_staff_user_conflict(
        self, monkeypatch
    ):
        token = self._staff_link_token(nonce="stafflinked")
        user = SimpleNamespace(id=42, role="doctor", is_active=True)

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return user

        monkeypatch.setattr(
            admin_telegram.crud_telegram,
            "get_telegram_user_by_chat_id",
            lambda _db, _chat_id: SimpleNamespace(user_id=42),
        )
        monkeypatch.setattr(
            admin_telegram.crud_telegram,
            "get_telegram_user_by_linked_user_id",
            lambda _db, _linked_user_id: SimpleNamespace(chat_id=112233),
        )

        result = admin_telegram.validate_staff_link_start_token(
            db=SimpleNamespace(query=lambda _model: FakeQuery()),
            token=token,
            telegram_chat_id=998877,
        )

        assert result["valid"] is False
        assert result["reason"] == "staff_user_already_linked"
        assert result["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )
