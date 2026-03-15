from sqlalchemy import String

from app.models.online_queue import OnlineQueueEntry


def test_queue_entry_source_column_fits_current_runtime_values():
    source_column = OnlineQueueEntry.__table__.c.source

    assert isinstance(source_column.type, String)
    assert source_column.type.length == 24

    current_runtime_values = [
        "online",
        "desk",
        "confirmation",
        "morning_assignment",
        "migration",
        "batch_update",
        "force_majeure_transfer",
    ]

    max_length = max(len(value) for value in current_runtime_values)
    assert max_length == len("force_majeure_transfer")
    assert source_column.type.length >= max_length
