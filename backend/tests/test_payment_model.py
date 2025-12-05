from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.visit import Visit
from app.models.payment import Payment, PaymentVisit


def test_payment_and_payment_visit_relationships(db_session: Session):
    """Создание Visit + Payment + PaymentVisit и проверка связей и flush()."""

    # Создаем визит
    visit = Visit(
        patient_id=1,  # допустимое фиктивное значение, FK не строгий в тестовой БД
        status="open",
        notes="Test visit for payment model",
    )
    db_session.add(visit)
    db_session.flush()

    # Создаем платеж, связанный с визитом
    payment = Payment(
        visit_id=visit.id,
        amount=Decimal("100000.00"),
        currency="UZS",
        method="online",
        status="pending",
    )
    db_session.add(payment)
    db_session.flush()  # не должно выбрасывать ошибок sync rule / mapper

    # Создаем связь PaymentVisit
    pv = PaymentVisit(
        payment_id=payment.id,
        visit_id=visit.id,
        amount=Decimal("100000.00"),
    )
    db_session.add(pv)
    db_session.flush()

    # Проверяем навигацию отношений
    assert pv.payment is payment
    assert pv.visit is visit
    assert payment.payment_visits[0] is pv


