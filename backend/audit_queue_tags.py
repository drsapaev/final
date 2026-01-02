"""
Queue Tag Audit Script
Проверяет соответствие queue_tag между Services и QueueProfiles
"""
import asyncio
from sqlalchemy import select
from app.db.session import async_session
from app.models.queue_profile import QueueProfile
from app.models.service import Service

async def audit():
    async with async_session() as db:
        # Get all queue profiles
        profiles = (await db.execute(select(QueueProfile))).scalars().all()
        print('=== QueueProfiles ===')
        all_tags = set()
        for p in profiles:
            tags = p.queue_tags or []
            all_tags.update(tags)
            print(f'{p.key}: queue_tags={tags}, is_active={p.is_active}, show_on_qr_page={p.show_on_qr_page}')
        
        print(f'\nВсего допустимых queue_tags: {sorted(all_tags)}')
        
        # Get all services with queue_tag
        services = (await db.execute(select(Service))).scalars().all()
        print(f'\n=== Services ({len(services)} total) ===')
        
        services_with_tag = [s for s in services if s.queue_tag]
        services_without_tag = [s for s in services if not s.queue_tag]
        
        print(f'С queue_tag: {len(services_with_tag)}')
        print(f'Без queue_tag: {len(services_without_tag)}')
        
        # Find orphan tags (services with queue_tag not in any profile)
        orphan_tags = set()
        for s in services_with_tag:
            if s.queue_tag not in all_tags:
                orphan_tags.add(s.queue_tag)
                print(f'  ⚠️ ORPHAN: Service "{s.name}" has queue_tag="{s.queue_tag}" not in any profile!')
        
        if not orphan_tags:
            print('  ✅ Все queue_tag в услугах соответствуют профилям')
        
        # Show services without queue_tag
        if services_without_tag:
            print(f'\n=== Services без queue_tag ({len(services_without_tag)}) ===')
            for s in services_without_tag[:10]:
                print(f'  - {s.name} (id={s.id})')
            if len(services_without_tag) > 10:
                print(f'  ... и ещё {len(services_without_tag)-10}')

if __name__ == "__main__":
    asyncio.run(audit())
