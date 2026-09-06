from pathlib import Path

from delivery.outbox import DeliveryOutbox


def test_delivery_outbox_survives_restart_and_deduplicates(tmp_path: Path) -> None:
    clock = [1_000.0]
    path = tmp_path / "outbox.sqlite3"
    first = DeliveryOutbox(path, clock=lambda: clock[0])
    item_id = first.enqueue(
        "job-1", "highlight-1", "+5491155550118", "José",
        "https://media.example/highlight", "Tu highlight", "vivoo-owner",
    )
    first.enqueue(
        "job-1", "highlight-1", "+5491155550118", "José",
        "https://media.example/highlight", "Tu highlight", "vivoo-owner",
    )

    restarted = DeliveryOutbox(path, clock=lambda: clock[0])
    assert restarted.pending_count() == 1
    assert restarted.claim_next().id == item_id


def test_sent_delivery_only_retries_callback(tmp_path: Path) -> None:
    clock = [2_000.0]
    outbox = DeliveryOutbox(tmp_path / "outbox.sqlite3", clock=lambda: clock[0])
    item_id = outbox.enqueue(
        "job-1", "highlight-1", "+5491155550118", "José",
        "https://media.example/highlight", "Tu highlight", "vivoo-owner",
    )
    item = outbox.claim_next()
    outbox.mark_sent(item.id)
    sent = outbox.claim_next()

    assert sent.id == item_id
    assert sent.state == "sent"
    outbox.complete(item_id)
    assert outbox.pending_count() == 0
