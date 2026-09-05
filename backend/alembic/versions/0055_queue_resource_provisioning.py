"""Baseline provisioning: departments, queue profiles, queue resource staff.

QD-0 of the desk-queue-join design (docs/runbooks/DESK_QUEUE_JOIN_DESIGN.md,
operator decision A). Root cause of the silent no-queue desk registrations
(patient 36, 2026-09-05): the new production database was created without
the baseline reference data the queue machinery requires —

- zero ``departments`` and ``queue_profiles`` (the wizard builds its
  service tabs from profiles; without the ``specialists`` profile the
  cardiology/ECG/EchoKG services are filtered out of the wizard);
- no resource staff accounts for doctorless queues
  (``lab_resource``/``general_resource``/``ecg_resource``) —
  ``prepare_wizard_queue_assignment`` resolves doctorless queue_tags to
  these users+doctors and returns None when they are missing.

Idempotent provisioning (all INSERTs are ON CONFLICT DO NOTHING; the
services UPDATEs are idempotent by code):

- 6 departments (cardiology, echokg, laboratory, stomatology, general,
  dermatology);
- 7 queue profiles: one ``specialists`` profile for the wizard tab
  (union of doctor-consult tags; NOT shown on the QR page) plus one
  profile per department for the QR join page;
- 3 resource staff accounts (``ecg_resource`` → Nurse, ``lab_resource``
  → Lab, ``general_resource`` → Nurse) + linked Doctor rows
  (specialty = served queue_tag, so ADR-001 same-specialty call
  permissions work). Unusable passwords — these accounts own queues,
  they are not logins.
- Service data corrections per clinical rules (2026-09-05 operator):
  ``K10 ЭКГ`` is performed by a nurse → ``requires_doctor = false``;
  ``K03 СМАД`` grouped under the ``echokg`` department.

Deliberately NOT provisioned here: a stomatology DOCTOR — S01
(`requires_doctor = true`) needs a real dentist chosen by the operator
(admin UI); until then desk registration of S01 fails LOUDLY by design
(QD-1 contract). The stomatology queue profile IS provisioned so the QR
page and wizard tab exist.

Downgrade removes exactly the rows this migration provisions (resource
users cascade their Doctor rows; queue profiles and departments are
deleted by key; service flags restored).
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# Revision identifiers — chained after 0054_queue_entry_attribution.
revision = "0055_queue_resource_provisioning"
down_revision = "0054_queue_entry_attribution"
branch_labels = None
depends_on = None

_DEPARTMENTS = sa.text(
    """
    INSERT INTO departments (key, name_ru, display_order, active)
    VALUES
        ('cardiology',  'Кардиология',    1, true),
        ('echokg',      'ЭКГ',            2, true),
        ('laboratory',  'Лаборатория',    3, true),
        ('stomatology', 'Стоматология',   4, true),
        ('general',     'Общая очередь',  5, true),
        ('dermatology', 'Дерматология',   6, true)
    ON CONFLICT (key) DO NOTHING
    """
)

_QUEUE_PROFILES = sa.text(
    """
    INSERT INTO queue_profiles
        (key, title, title_ru, queue_tags, department_key,
         display_order, is_active, show_on_qr_page, icon, created_at)
    VALUES
        ('specialists', 'Специалисты', 'Специалисты',
         '["cardio","cardiology","echokg","ecg","derma","dermatology","dental","dentistry","stomatology"]',
         NULL, 1, true, false, 'Stethoscope', NOW()),
        ('cardiology', 'Кардиология', 'Кардиология',
         '["cardio","cardiology"]', 'cardiology', 2, true, true, 'Heart', NOW()),
        ('echokg', 'ЭКГ', 'ЭКГ',
         '["ecg"]', 'echokg', 3, true, true, 'Activity', NOW()),
        ('laboratory', 'Лаборатория', 'Лаборатория',
         '["lab","laboratory"]', 'laboratory', 4, true, true, 'FlaskConical', NOW()),
        ('stomatology', 'Стоматология', 'Стоматология',
         '["dental","dentistry","stomatology"]', 'stomatology', 5, true, true, 'Tooth', NOW()),
        ('general', 'Общая очередь', 'Общая очередь',
         '["general"]', 'general', 6, true, false, 'Users', NOW()),
        ('dermatology', 'Дерматология', 'Дерматология',
         '["derma","dermatology"]', 'dermatology', 7, true, false, '', NOW())
    ON CONFLICT (key) DO NOTHING
    """
)

_RESOURCE_USERS = sa.text(
    """
    INSERT INTO users (username, hashed_password, role, is_active, is_superuser, must_change_password)
    VALUES
        ('ecg_resource',     '!disabled:queue-resource', 'Nurse', true, false, false),
        ('lab_resource',     '!disabled:queue-resource', 'Lab',   true, false, false),
        ('general_resource', '!disabled:queue-resource', 'Nurse', true, false, false)
    ON CONFLICT (username) DO NOTHING
    """
)

_RESOURCE_DOCTORS = sa.text(
    """
    INSERT INTO doctors (user_id, specialty, active, start_number_online, max_online_per_day)
    SELECT u.id, m.tag, true, 1, 15
    FROM (VALUES
        ('ecg_resource',     'ecg'),
        ('lab_resource',     'lab'),
        ('general_resource', 'general')
    ) AS m(username, tag)
    JOIN users u ON u.username = m.username
    ON CONFLICT (user_id) DO NOTHING
    """
)

_SERVICES_FIX = sa.text(
    """
    UPDATE services SET requires_doctor = false WHERE code = 'K10';
    UPDATE services SET department_key = 'echokg'
    WHERE code = 'K03' AND department_key IS NULL;
    """
)


def upgrade() -> None:
    op.execute(_DEPARTMENTS)
    op.execute(_QUEUE_PROFILES)
    op.execute(_RESOURCE_USERS)
    op.execute(_RESOURCE_DOCTORS)
    op.execute(_SERVICES_FIX)


def downgrade() -> None:
    op.execute(
        "DELETE FROM doctors WHERE user_id IN "
        "(SELECT id FROM users WHERE username IN "
        "('ecg_resource','lab_resource','general_resource'))"
    )
    op.execute(
        "DELETE FROM users WHERE username IN "
        "('ecg_resource','lab_resource','general_resource')"
    )
    op.execute(
        "DELETE FROM queue_profiles WHERE key IN "
        "('specialists','cardiology','echokg','laboratory','stomatology',"
        "'general','dermatology')"
    )
    op.execute(
        "DELETE FROM departments WHERE key IN "
        "('cardiology','echokg','laboratory','stomatology','general','dermatology')"
    )
    op.execute(
        "UPDATE services SET requires_doctor = true WHERE code = 'K10'"
    )
    op.execute(
        "UPDATE services SET department_key = NULL WHERE code = 'K03'"
    )
