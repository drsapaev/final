const BASE_COPY = {
  liveStatus: 'Clinic OS для EMR, очереди и платежей',
  navigationLabel: 'Навигация лендинга',
  languageSwitchLabel: 'Сменить язык',
  headerLogin: 'Войти',
  navigation: [
    { id: 'product', label: 'Продукт' },
    { id: 'modules', label: 'Модули' },
    { id: 'integrations', label: 'Интеграции' },
    { id: 'pricing', label: 'Тарифы' },
    { id: 'faq', label: 'FAQ' }
  ],
  hero: {
    eyebrow: 'Clinic OS для современной клиники',
    title: 'Единая система управления клиникой, которая держит EMR, очередь и платежи в одном ритме.',
    description:
      'MediClinic Pro собирает регистратуру, врача, QR-очередь, платежи, Telegram и отчеты в один workflow без ручных разрывов между командами.',
    primaryCta: 'Открыть демо',
    secondaryCta: 'Посмотреть интерфейс',
    proofChips: ['EMR врача', 'QR-очередь', 'Telegram-уведомления', 'Платежи и отчеты'],
    quickStats: [
      { value: '4', label: 'ключевые роли', detail: 'регистратура, врач, касса, руководитель' },
      { value: '1', label: 'единый workflow', detail: 'от регистрации до отчетов' },
      { value: '24/7', label: 'операционный контур', detail: 'контроль очереди, оплат и статусов' }
    ],
    visualPanels: [
      {
        label: 'Dashboard',
        title: 'Руководитель видит клинику в реальном времени',
        description: 'Очередь, загрузка кабинетов и сигналы смены собраны в одном окне.',
        bullets: ['Слоты и перегрузка врачей', 'Сигналы по задержкам и очереди', 'Сводка по выручке и статусам']
      },
      {
        label: 'QR Queue',
        title: 'Регистратура управляет потоком без хаоса в холле',
        description: 'QR-очередь, табло и маршрутизация пациентов работают как единый сценарий.',
        bullets: ['Проверка записи и создание визита', 'Маршрутизация в нужный кабинет', 'Прозрачная очередь для пациента']
      },
      {
        label: 'Doctor EMR',
        title: 'Врач ведет прием внутри живой карты пациента',
        description: 'История болезни, шаблоны осмотров и PDF-документы остаются внутри EMR.',
        bullets: ['Шаблоны осмотров и назначения', 'История визитов и вложения', 'Документы без ручной перепечатки']
      }
    ]
  },
  trust: {
    eyebrow: 'Что система закрывает с первого дня',
    title: 'Вместо пустых обещаний — конкретный операционный контур',
    description:
      'Каждая карточка показывает не абстрактную “автоматизацию”, а реальный блок клинической работы, который команда использует каждый день.',
    items: [
      { value: 'EMR + PDF', label: 'карта приема', detail: 'шаблоны осмотров, история болезни, документы' },
      { value: 'QR Queue', label: 'поток пациентов', detail: 'электронная очередь, табло, управление потоками' },
      { value: 'PayMe / Click / Apelsin', label: 'платежный контур', detail: 'касса, чеки и статусы услуг без ручной сверки' },
      { value: 'Telegram + Reports', label: 'коммуникации и аналитика', detail: 'напоминания, отчеты, нагрузка врачей и доходы' }
    ]
  },
  features: {
    eyebrow: 'Основные возможности',
    title: 'Критичные процессы клиники собираются в одной платформе',
    description:
      'Структура лендинга строится вокруг того, как реально работает клиника: прием, очередь, врач, оплата и контроль руководителя.',
    items: [
      {
        badge: 'EMR врача',
        title: 'Живая электронная карта пациента',
        description: 'Шаблоны осмотров, история болезни, назначения и PDF-документы остаются внутри одного приема.'
      },
      {
        badge: 'Регистратура',
        title: 'Быстрая регистрация и поиск пациента',
        description: 'Создание визита, проверка записи и маршрутизация пациента выполняются без лишних окон.'
      },
      {
        badge: 'Очередь',
        title: 'QR-очередь и управление потоками',
        description: 'Табло, очереди по кабинетам и прозрачный status flow снижают хаос в холле.'
      },
      {
        badge: 'Платежи',
        title: 'Касса и чеки внутри клинического сценария',
        description: 'PayMe, Click и Apelsin работают в одном процессе с услугами, а не отдельно от них.'
      },
      {
        badge: 'Уведомления',
        title: 'Telegram и напоминания без ручной рутины',
        description: 'Команда и пациенты получают нужные сигналы в момент записи, ожидания и завершения приема.'
      },
      {
        badge: 'Отчеты',
        title: 'Доходы, нагрузка и статистика по смене',
        description: 'Руководитель видит, где растет очередь, как загружены врачи и как меняется выручка.'
      }
    ]
  },
  workflow: {
    eyebrow: 'Как работает система',
    title: 'Пациент проходит путь от регистратуры до отчета без ручных разрывов',
    description:
      'Для сложного медицинского продукта лучше всего продает не список функций, а четкий end-to-end workflow клиники.',
    steps: [
      {
        title: '01. Пациент регистрируется',
        description: 'Регистратура находит пациента, подтверждает запись и запускает визит без бумажных обходов.'
      },
      {
        title: '02. Попадает в очередь',
        description: 'Система направляет пациента в нужный поток, а табло и команда видят актуальный статус.'
      },
      {
        title: '03. Врач ведет EMR',
        description: 'Прием, история болезни, документы и шаблоны осмотров остаются в единой карте пациента.'
      },
      {
        title: '04. Платеж и отчеты автоматически',
        description: 'Касса закрывает услуги, а руководитель сразу получает прозрачную картину по смене и выручке.'
      }
    ],
    flowLabel: 'Workflow клиники',
    flowNodes: ['Пациент', 'Регистратура', 'Очередь', 'Врач', 'EMR', 'Платеж', 'Отчеты'],
    flowSummary:
      'Именно эта цепочка показывает ценность продукта сильнее, чем длинный список модулей без контекста.'
  },
  modules: {
    eyebrow: 'Модули системы',
    title: 'Модульная архитектура под реальные направления клиники',
    description:
      'Базовый workflow можно усиливать отраслевыми модулями без потери единого контура данных.',
    items: [
      { title: 'EMR', description: 'История болезни, шаблоны приема, назначения и документы.' },
      { title: 'Стоматология', description: 'Карточка пациента, план лечения и рабочие сценарии врача.' },
      { title: 'Кардиология', description: 'Шаблоны осмотров, контроль показателей и динамика лечения.' },
      { title: 'Дерматология', description: 'Осмотры, фотофиксация и повторные визиты внутри EMR.' },
      { title: 'Лаборатория', description: 'Назначения, статусы анализов и связь результатов с визитом.' },
      { title: 'Рецепты', description: 'Назначения и документы, которые врач формирует прямо в процессе приема.' },
      { title: 'Отчеты', description: 'Доходы, статистика визитов, нагрузка врачей и контроль смен.' },
      { title: 'Финансы', description: 'Касса, статусы оплат, чеки и прозрачная картина по услугам.' }
    ]
  },
  screens: {
    eyebrow: 'Скриншоты интерфейса',
    title: 'Интерфейсы, которые команда понимает с первого дня',
    description:
      'Показываем не красивые абстракции, а реальные рабочие поверхности: dashboard, очередь, EMR, регистратура и аналитика.',
    items: [
      {
        label: 'Dashboard',
        title: 'Операционный центр смены',
        description: 'Очередь, кабинеты, касса и сигналы загрузки в одном экране.'
      },
      {
        label: 'Reception',
        title: 'Регистратура без ручной перегонки данных',
        description: 'Поиск пациента, запись, создание визита и переключение в очередь.'
      },
      {
        label: 'Queue',
        title: 'Прозрачная очередь для команды и пациента',
        description: 'QR-поток, табло и распределение по кабинетам без хаоса в холле.'
      },
      {
        label: 'EMR',
        title: 'Прием врача внутри живой карты',
        description: 'Осмотр, документы и история болезни не распадаются на отдельные инструменты.'
      },
      {
        label: 'Analytics',
        title: 'Аналитика по выручке и нагрузке',
        description: 'Руководитель видит результаты смены, перегрузки и точки роста без ручных отчетов.'
      }
    ]
  },
  integrations: {
    eyebrow: 'Интеграции',
    title: 'Интеграции, которые двигают поток без ручной работы',
    description:
      'Важна не просто интеграция как факт, а ее место в реальном клиническом сценарии.',
    items: [
      { title: 'Telegram', detail: 'Напоминания, служебные сигналы и контакт с пациентом.' },
      { title: 'PayMe', detail: 'Быстрые оплаты внутри общего статуса услуги.' },
      { title: 'Click', detail: 'Платежный сценарий без разрыва между кассой и визитом.' },
      { title: 'Apelsin', detail: 'Еще один локальный платежный канал внутри единого процесса.' },
      { title: 'QR check-in', detail: 'Вход пациента в очередь без лишней нагрузки на стойку.' },
      { title: 'PDF / печать', detail: 'Документы и чеки отдаются из системы, а не вручную.' }
    ]
  },
  security: {
    eyebrow: 'Безопасность',
    title: 'Контроль доступа и прозрачность действий для медицинской команды',
    description:
      'Для медицины важно не только удобство, но и предсказуемость: кто что делал, когда и в каком контексте.',
    items: [
      { title: 'Audit logs', description: 'Каждое важное действие можно отследить по роли, времени и сценарию.' },
      { title: 'Role system', description: 'Доступ по ролям снижает риск случайных или лишних изменений.' },
      { title: 'Change history', description: 'История изменений помогает разбирать спорные кейсы и внутренние проверки.' },
      { title: 'Backup-ready ops', description: 'Резервный контур и восстановление встроены в операционный подход, а не остаются “на потом”.' }
    ]
  },
  advantages: {
    eyebrow: 'Преимущества системы',
    title: 'До и после внедрения выглядят как две разные клиники',
    description:
      'Этот блок помогает быстро показать, что продукт убирает хаос не на словах, а в повседневных процессах.',
    beforeTitle: 'Без системы',
    afterTitle: 'С MediClinic Pro',
    beforeItems: [
      'Бумажные карты и разрозненные заметки',
      'Потеря контекста между регистратурой, врачом и кассой',
      'Хаос в очереди и непонятный статус пациента',
      'Отчеты собираются вручную в конце дня'
    ],
    afterItems: [
      'Единый EMR и общая карта пациента для команды',
      'Прозрачная очередь и понятный маршрут пациента',
      'Платежи и чеки встроены в клинический сценарий',
      'Аналитика по смене, доходам и нагрузке без ручной сборки'
    ]
  },
  pricing: {
    eyebrow: 'Тарифы',
    title: 'Три тарифа для малых клиник, растущих команд и сетей',
    description:
      'Точные условия зависят от модулей и интеграций, поэтому лендинг показывает понятную рамку выбора без выдуманных цифр.',
    footnote: 'Финальный состав и стоимость подтверждаем после демо по вашему workflow.',
    plans: [
      {
        name: 'Starter',
        audience: 'Для малых клиник',
        price: 'По запросу',
        note: 'Быстрый старт для одной команды и базового пациентского потока.',
        features: ['Регистратура и запись', 'EMR врача', 'Очередь пациентов', 'Базовые отчеты'],
        cta: 'Запросить демо'
      },
      {
        name: 'Professional',
        audience: 'Для растущих клиник',
        price: 'По запросу',
        note: 'Оптимум для клиник, которым нужен единый контур приема, платежей и аналитики.',
        features: ['Все из Starter', 'PayMe / Click / Apelsin', 'Telegram-уведомления', 'Расширенные отчеты и роли'],
        cta: 'Выбрать Professional',
        featured: true
      },
      {
        name: 'Enterprise',
        audience: 'Для сетей клиник',
        price: 'По запросу',
        note: 'Многофилиальный контур, дополнительные модули и внедрение под сложный поток.',
        features: ['Все из Professional', 'Модули по направлениям', 'Приоритетная поддержка', 'Индивидуальный rollout и SLA'],
        cta: 'Обсудить Enterprise'
      }
    ]
  },
  faq: {
    eyebrow: 'FAQ',
    title: 'Вопросы, которые чаще всего задают перед внедрением',
    description:
      'Хороший SaaS-лендинг снимает возражения до звонка или демо, а не перекладывает все на менеджера.',
    items: [
      {
        question: 'Сколько времени занимает внедрение?',
        answer: 'Базовый контур можно подготовить быстро, а точный срок зависит от числа ролей, модулей и текущих процессов клиники.'
      },
      {
        question: 'Можно ли перенести существующую базу пациентов?',
        answer: 'Да, внедрение можно строить вокруг импорта текущих данных и постепенного перевода команды на новый workflow.'
      },
      {
        question: 'Работает ли система на телефоне?',
        answer: 'Ключевые экраны адаптивны, поэтому руководитель и команда могут открывать важные части контура и с мобильных устройств.'
      },
      {
        question: 'Подойдет ли платформа для нескольких филиалов?',
        answer: 'Да, модульная архитектура и роли позволяют масштабировать систему от одной клиники до сети с несколькими площадками.'
      }
    ]
  },
  finalCta: {
    eyebrow: 'Финальный CTA',
    title: 'Переведите клинику на единый операционный контур',
    description:
      'Покажем демо именно по вашему workflow: регистратура, очередь, врач, EMR, платежи и отчеты в одном сценарии.',
    primaryCta: 'Запросить демо',
    secondaryCta: 'Активировать лицензию',
    bullets: [
      'Разберем ваш текущий patient flow и точки потерь',
      'Покажем релевантные модули и интеграции',
      'Поможем команде стартовать без долгого переходного периода'
    ]
  },
  contactLabels: {
    address: 'Адрес',
    phone: 'Телефон',
    schedule: 'График работы',
    support: 'Поддержка'
  },
  footer: {
    tagline: 'EMR, регистратура, очередь, платежи и аналитика в одном контуре.',
    groups: [
      {
        title: 'Продукт',
        links: [
          { label: 'Возможности', href: '#product' },
          { label: 'Workflow', href: '#workflow' },
          { label: 'Модули', href: '#modules' }
        ]
      },
      {
        title: 'Ресурсы',
        links: [
          { label: 'Интеграции', href: '#integrations' },
          { label: 'Тарифы', href: '#pricing' },
          { label: 'FAQ', href: '#faq' }
        ]
      }
    ],
    footnote: 'Подходит для частных клиник, диагностических центров и сетей клиник.'
  },
  activationTitle: 'Активация лицензии'
};

function deepMerge(base, override) {
  if (override === undefined) {
    return base;
  }

  if (Array.isArray(base)) {
    return override;
  }

  if (base && typeof base === 'object' && override && typeof override === 'object') {
    const result = { ...base };
    for (const key of Object.keys(override)) {
      result[key] = deepMerge(base[key], override[key]);
    }
    return result;
  }

  return override;
}

const EN_OVERRIDES = {
  liveStatus: 'Clinic OS for EMR, queue and payments',
  navigationLabel: 'Landing navigation',
  languageSwitchLabel: 'Change language',
  headerLogin: 'Login',
  navigation: [
    { id: 'product', label: 'Product' },
    { id: 'modules', label: 'Modules' },
    { id: 'integrations', label: 'Integrations' },
    { id: 'pricing', label: 'Pricing' },
    { id: 'faq', label: 'FAQ' }
  ],
  hero: {
    eyebrow: 'Clinic OS for modern medical teams',
    title: 'One clinic management system that keeps EMR, queue and payments in the same rhythm.',
    description:
      'MediClinic Pro brings reception, doctors, QR queue, payments, Telegram and reporting into one workflow with no manual gaps between teams.',
    primaryCta: 'Open demo',
    secondaryCta: 'View interface',
    proofChips: ['Doctor EMR', 'QR queue', 'Telegram alerts', 'Payments and reports'],
    quickStats: [
      { value: '4', label: 'core roles', detail: 'reception, doctor, cashier, leadership' },
      { value: '1', label: 'unified workflow', detail: 'from registration to reporting' },
      { value: '24/7', label: 'operational visibility', detail: 'queue, payments and status control' }
    ],
    visualPanels: [
      {
        label: 'Dashboard',
        title: 'Leadership sees the clinic in real time',
        description: 'Queue, room load and shift signals live in one operating window.',
        bullets: ['Slots and doctor overload', 'Delay and queue alerts', 'Revenue and status summary']
      },
      {
        label: 'QR Queue',
        title: 'Reception controls flow without front-desk chaos',
        description: 'QR queue, display board and patient routing work as one connected scenario.',
        bullets: ['Booking check and visit creation', 'Routing into the right room', 'A transparent queue for the patient']
      },
      {
        label: 'Doctor EMR',
        title: 'Doctors work inside a live patient record',
        description: 'History, exam templates and PDF documents stay inside the EMR during the visit.',
        bullets: ['Exam templates and treatment plans', 'Visit history and attachments', 'Documents without manual re-entry']
      }
    ]
  },
  trust: {
    eyebrow: 'What the platform covers on day one',
    title: 'Specific operational proof instead of vague promises',
    description:
      'Each card shows an actual part of the clinic workflow the team can use every day, not generic digital-transformation language.',
    items: [
      { value: 'EMR + PDF', label: 'visit record', detail: 'exam templates, medical history and documents' },
      { value: 'QR Queue', label: 'patient flow', detail: 'digital queue, display board and room routing' },
      { value: 'PayMe / Click / Apelsin', label: 'payment loop', detail: 'cashier, receipts and service statuses without manual reconciliation' },
      { value: 'Telegram + Reports', label: 'communication and analytics', detail: 'reminders, reports, doctor load and revenue visibility' }
    ]
  },
  features: {
    eyebrow: 'Core capabilities',
    title: 'Critical clinic workflows live inside one platform',
    description:
      'The landing is structured around how clinics actually operate: intake, queue, doctor workflow, payment and leadership visibility.',
    items: [
      {
        badge: 'Doctor EMR',
        title: 'A live patient record for every consultation',
        description: 'Exam templates, medical history, treatment plans and PDF documents stay inside one visit flow.'
      },
      {
        badge: 'Reception',
        title: 'Fast registration and patient lookup',
        description: 'Visit creation, booking verification and patient routing happen without bouncing between screens.'
      },
      {
        badge: 'Queue',
        title: 'QR queue and patient-flow control',
        description: 'Display boards, room queues and a clear status flow reduce front-desk chaos.'
      },
      {
        badge: 'Payments',
        title: 'Cashier and receipts inside the care workflow',
        description: 'PayMe, Click and Apelsin stay connected to services instead of living in a separate process.'
      },
      {
        badge: 'Notifications',
        title: 'Telegram alerts without manual follow-up',
        description: 'Patients and staff receive the right signals during booking, waiting and visit completion.'
      },
      {
        badge: 'Reports',
        title: 'Revenue, load and shift analytics',
        description: 'Leadership can see queue growth, doctor load and revenue changes without manual reporting.'
      }
    ]
  },
  workflow: {
    eyebrow: 'How it works',
    title: 'The patient moves from reception to reporting without manual breaks',
    description:
      'For a complex medical product, a clear end-to-end clinic workflow sells better than a disconnected feature list.',
    steps: [
      {
        title: '01. Patient registration',
        description: 'Reception finds the patient, confirms the booking and starts the visit without paper detours.'
      },
      {
        title: '02. Queue assignment',
        description: 'The system routes the patient into the right flow while the team and display board share the same status.'
      },
      {
        title: '03. Doctor works in EMR',
        description: 'Consultation, medical history, templates and documents stay in one connected patient record.'
      },
      {
        title: '04. Payment and reports update automatically',
        description: 'Cashier closes services while leadership instantly sees shift and revenue visibility.'
      }
    ],
    flowLabel: 'Clinic workflow',
    flowNodes: ['Patient', 'Reception', 'Queue', 'Doctor', 'EMR', 'Payment', 'Reports'],
    flowSummary:
      'This chain makes the product value obvious much faster than a long module list without context.'
  },
  modules: {
    eyebrow: 'System modules',
    title: 'A modular architecture for real clinic specialties',
    description:
      'The base workflow can grow with specialty modules while keeping one shared operational data layer.',
    items: [
      { title: 'EMR', description: 'Medical history, visit templates, prescriptions and documents.' },
      { title: 'Dentistry', description: 'Patient chart, treatment plan and dentist-specific workflows.' },
      { title: 'Cardiology', description: 'Exam templates, indicator tracking and treatment dynamics.' },
      { title: 'Dermatology', description: 'Consultations, photo capture and follow-up visits inside EMR.' },
      { title: 'Laboratory', description: 'Orders, lab-status tracking and result linkage to the visit.' },
      { title: 'Prescriptions', description: 'Treatment instructions and documents created directly during the consultation.' },
      { title: 'Reports', description: 'Revenue, visit statistics, doctor load and shift control.' },
      { title: 'Finance', description: 'Cashier flow, payment statuses, receipts and service-level clarity.' }
    ]
  },
  screens: {
    eyebrow: 'Interface previews',
    title: 'Interfaces the team can understand on day one',
    description:
      'Instead of abstract mockups, the page shows real operating surfaces: dashboard, queue, EMR, reception and analytics.',
    items: [
      {
        label: 'Dashboard',
        title: 'The operating center of the shift',
        description: 'Queue, rooms, cashier and load signals in one shared screen.'
      },
      {
        label: 'Reception',
        title: 'Reception without manual data relay',
        description: 'Patient lookup, booking, visit creation and queue handoff stay in one place.'
      },
      {
        label: 'Queue',
        title: 'A transparent queue for staff and patients',
        description: 'QR flow, display boards and room assignment without lobby chaos.'
      },
      {
        label: 'EMR',
        title: 'Doctor workflow inside a live chart',
        description: 'Consultation notes, documents and history stay together instead of splitting into separate tools.'
      },
      {
        label: 'Analytics',
        title: 'Revenue and load analytics',
        description: 'Leadership sees shift outcomes, overload and growth points without manual spreadsheets.'
      }
    ]
  },
  integrations: {
    eyebrow: 'Integrations',
    title: 'Integrations that move the workflow without manual work',
    description:
      'The important part is not just that an integration exists, but where it fits into the real clinic scenario.',
    items: [
      { title: 'Telegram', detail: 'Reminders, internal signals and direct patient communication.' },
      { title: 'PayMe', detail: 'Fast payments inside the shared service status.' },
      { title: 'Click', detail: 'A payment step that stays connected to the visit and cashier flow.' },
      { title: 'Apelsin', detail: 'Another local payment rail inside the same process.' },
      { title: 'QR check-in', detail: 'Patients join the queue without adding more reception workload.' },
      { title: 'PDF / print', detail: 'Documents and receipts come out of the system instead of manual preparation.' }
    ]
  },
  security: {
    eyebrow: 'Security',
    title: 'Access control and action visibility for medical teams',
    description:
      'In healthcare, convenience only works if every action stays traceable and operationally predictable.',
    items: [
      { title: 'Audit logs', description: 'Every important action can be traced by role, time and workflow step.' },
      { title: 'Role system', description: 'Role-based access reduces the risk of accidental or unnecessary changes.' },
      { title: 'Change history', description: 'Change history helps investigate disputes and internal reviews.' },
      { title: 'Backup-ready ops', description: 'Recovery and operational continuity are part of the system approach, not an afterthought.' }
    ]
  },
  advantages: {
    eyebrow: 'Why it is better',
    title: 'Before and after rollout feel like two different clinics',
    description:
      'This comparison helps visitors see how the platform removes everyday chaos, not just abstract inefficiency.',
    beforeTitle: 'Without the system',
    afterTitle: 'With MediClinic Pro',
    beforeItems: [
      'Paper records and scattered notes',
      'Context loss between reception, doctor and cashier',
      'Queue chaos and an unclear patient status',
      'Reports assembled manually at the end of the day'
    ],
    afterItems: [
      'One EMR and a shared patient chart for the team',
      'A transparent queue and a clear patient route',
      'Payments and receipts inside the care workflow',
      'Shift, revenue and doctor-load analytics without manual compilation'
    ]
  },
  pricing: {
    eyebrow: 'Pricing',
    title: 'Three plans for small clinics, growing teams and networks',
    description:
      'Exact pricing depends on modules and integrations, so the landing shows a clear decision frame instead of invented numbers.',
    footnote: 'Final scope and pricing are confirmed after a workflow-based demo.',
    plans: [
      {
        name: 'Starter',
        audience: 'For small clinics',
        price: 'On request',
        note: 'Fast launch for one team and a basic patient flow.',
        features: ['Reception and scheduling', 'Doctor EMR', 'Patient queue', 'Basic reports'],
        cta: 'Request a demo'
      },
      {
        name: 'Professional',
        audience: 'For growing clinics',
        price: 'On request',
        note: 'The best fit for clinics that need one operating loop for care, payments and analytics.',
        features: ['Everything in Starter', 'PayMe / Click / Apelsin', 'Telegram notifications', 'Advanced reports and roles'],
        cta: 'Choose Professional',
        featured: true
      },
      {
        name: 'Enterprise',
        audience: 'For clinic networks',
        price: 'On request',
        note: 'Multi-branch operations, extra modules and rollout support for complex flows.',
        features: ['Everything in Professional', 'Specialty modules', 'Priority support', 'Custom rollout and SLA'],
        cta: 'Talk about Enterprise'
      }
    ]
  },
  faq: {
    eyebrow: 'FAQ',
    title: 'Questions teams ask before rollout',
    description:
      'A strong SaaS landing addresses the key objections before a call instead of leaving everything to sales.',
    items: [
      {
        question: 'How long does implementation take?',
        answer: 'The base setup can be prepared quickly, while the full timeline depends on the number of roles, modules and current clinic workflows.'
      },
      {
        question: 'Can we migrate an existing patient database?',
        answer: 'Yes. The rollout can be organized around importing current data and gradually moving the team into the new workflow.'
      },
      {
        question: 'Does the system work on mobile devices?',
        answer: 'The key screens are responsive, so leadership and staff can open important parts of the workflow from mobile devices too.'
      },
      {
        question: 'Can the platform support multiple branches?',
        answer: 'Yes. The modular architecture and role system allow the product to scale from one clinic to a multi-branch network.'
      }
    ]
  },
  finalCta: {
    eyebrow: 'Final CTA',
    title: 'Move the clinic onto one operating loop',
    description:
      'We can show the demo around your actual workflow: reception, queue, doctor, EMR, payments and reporting in one scenario.',
    primaryCta: 'Request demo',
    secondaryCta: 'Activate license',
    bullets: [
      'Review your current patient flow and friction points',
      'Show the modules and integrations that fit your clinic',
      'Help the team launch without a painful transition period'
    ]
  },
  contactLabels: {
    address: 'Address',
    phone: 'Phone',
    schedule: 'Schedule',
    support: 'Support'
  },
  footer: {
    tagline: 'EMR, reception, queue, payments and analytics in one operating loop.',
    groups: [
      {
        title: 'Product',
        links: [
          { label: 'Capabilities', href: '#product' },
          { label: 'Workflow', href: '#workflow' },
          { label: 'Modules', href: '#modules' }
        ]
      },
      {
        title: 'Resources',
        links: [
          { label: 'Integrations', href: '#integrations' },
          { label: 'Pricing', href: '#pricing' },
          { label: 'FAQ', href: '#faq' }
        ]
      }
    ],
    footnote: 'Built for private clinics, diagnostics centers and multi-branch networks.'
  },
  activationTitle: 'License Activation'
};

const UZ_OVERRIDES = {
  liveStatus: 'EMR, navbat va tolovlar uchun Clinic OS',
  navigationLabel: 'Landing navigatsiyasi',
  languageSwitchLabel: 'Tilni almashtirish',
  headerLogin: 'Kirish',
  navigation: [
    { id: 'product', label: 'Mahsulot' },
    { id: 'modules', label: 'Modullar' },
    { id: 'integrations', label: 'Integratsiyalar' },
    { id: 'pricing', label: 'Tariflar' },
    { id: 'faq', label: 'FAQ' }
  ],
  hero: {
    eyebrow: 'Zamonaviy klinika uchun Clinic OS',
    title: 'EMR, navbat va tolovlarni bitta ritmda ushlab turadigan yagona klinika boshqaruv tizimi.',
    description:
      'MediClinic Pro registratura, shifokor, QR-navbat, tolovlar, Telegram va hisobotlarni bitta workflow ichida birlashtiradi, jamoalar orasida qol mehnatisiz.',
    primaryCta: 'Demo ochish',
    secondaryCta: 'Interfeysni ko\'rish',
    proofChips: ['Shifokor EMR', 'QR-navbat', 'Telegram signal', 'Tolovlar va hisobotlar'],
    quickStats: [
      { value: '4', label: 'asosiy rol', detail: 'registratura, shifokor, kassa, rahbar' },
      { value: '1', label: 'yagona workflow', detail: 'royxatdan otkazishdan hisobotgacha' },
      { value: '24/7', label: 'operatsion korinish', detail: 'navbat, tolov va status nazorati' }
    ],
    visualPanels: [
      {
        label: 'Dashboard',
        title: 'Rahbar klinikani real vaqt rejimida koradi',
        description: 'Navbat, kabinet yuklamasi va smena signallari bitta oynada turadi.',
        bullets: ['Slotlar va shifokor yuklamasi', 'Kechikish va navbat signallari', 'Tushum va statuslar jamlanmasi']
      },
      {
        label: 'QR Queue',
        title: 'Registratura oqimni tartibsiz boshqaradi',
        description: 'QR-navbat, tablo va bemor marshruti bitta ulangan ssenariy sifatida ishlaydi.',
        bullets: ['Yozuvni tekshirish va vizit ochish', 'Kerakli kabinetga yonaltirish', 'Bemor uchun shaffof navbat']
      },
      {
        label: 'Doctor EMR',
        title: 'Shifokor qabulni tirik bemor kartasi ichida olib boradi',
        description: 'Tarix, korik shablonlari va PDF hujjatlar qabul davomida EMR ichida qoladi.',
        bullets: ['Korik shablonlari va tayinlovlar', 'Vizitlar tarixi va fayllar', 'Qolda qayta yozishsiz hujjatlar']
      }
    ]
  },
  trust: {
    eyebrow: 'Tizim birinchi kundan nimani yopadi',
    title: 'Bosh gaplar emas, aniq operatsion kontur',
    description:
      'Har bir karta jamoa har kuni ishlatadigan klinik jarayonning real qismini korsatadi, shunchaki umumiy raqamli transformatsiya gapini emas.',
    items: [
      { value: 'EMR + PDF', label: 'qabul kartasi', detail: 'korik shablonlari, tarix va hujjatlar' },
      { value: 'QR Queue', label: 'bemor oqimi', detail: 'elektron navbat, tablo va kabinetga yonaltirish' },
      { value: 'PayMe / Click / Apelsin', label: 'tolov konturi', detail: 'kassa, cheklar va xizmat statuslari qolda solishtirishsiz' },
      { value: 'Telegram + Reports', label: 'aloqa va analitika', detail: 'eslatmalar, hisobotlar, shifokor yuklamasi va tushum' }
    ]
  },
  features: {
    eyebrow: 'Asosiy imkoniyatlar',
    title: 'Klinikaning muhim jarayonlari bitta platformada yigiladi',
    description:
      'Landing klinika qanday ishlashiga qarab qurilgan: qabul, navbat, shifokor oqimi, tolov va rahbar nazorati.',
    items: [
      {
        badge: 'Shifokor EMR',
        title: 'Har bir qabul uchun tirik bemor kartasi',
        description: 'Korik shablonlari, kasallik tarixi, tayinlovlar va PDF hujjatlar bitta qabul oqimida qoladi.'
      },
      {
        badge: 'Registratura',
        title: 'Tez royxatdan otkazish va bemorni topish',
        description: 'Vizit ochish, yozuvni tekshirish va bemorni yonaltirish ortiqcha oynalarsiz bajariladi.'
      },
      {
        badge: 'Navbat',
        title: 'QR-navbat va oqimni boshqarish',
        description: 'Tablo, kabinet navbatlari va aniq status flow holldagi tartibsizlikni kamaytiradi.'
      },
      {
        badge: 'Tolovlar',
        title: 'Kassa va cheklar klinik ssenariy ichida',
        description: 'PayMe, Click va Apelsin xizmatlar bilan bitta jarayonda ishlaydi, alohida emas.'
      },
      {
        badge: 'Xabarnomalar',
        title: 'Telegram signallari qolda kuzatuvsiz',
        description: 'Bemor ham, jamoa ham yozuv, kutish va qabul yakunida kerakli signalni oz vaqtida oladi.'
      },
      {
        badge: 'Hisobotlar',
        title: 'Tushum, yuklama va smena analitikasi',
        description: 'Rahbar navbat qayerda oshayotganini, shifokorlar qanchalik bandligini va tushum qanday ozgarayotganini koradi.'
      }
    ]
  },
  workflow: {
    eyebrow: 'Tizim qanday ishlaydi',
    title: 'Bemor registraturadan hisobotgacha qolda uzilishsiz otadi',
    description:
      'Murakkab tibbiy mahsulot uchun eng kuchli sotuv vositasi uzilgan feature royxati emas, balki aniq end-to-end klinika workflowidir.',
    steps: [
      {
        title: '01. Bemor royxatdan otadi',
        description: 'Registratura bemorni topadi, yozuvni tasdiqlaydi va qabulni qogozsiz boshlaydi.'
      },
      {
        title: '02. Navbatga tushadi',
        description: 'Tizim bemorni togri oqimga yonaltiradi, jamoa va tablo esa bir xil statusni koradi.'
      },
      {
        title: '03. Shifokor EMR bilan ishlaydi',
        description: 'Qabul, tarix, shablonlar va hujjatlar bitta ulangan bemor kartasi ichida qoladi.'
      },
      {
        title: '04. Tolov va hisobotlar avtomatik yangilanadi',
        description: 'Kassa xizmatlarni yopadi, rahbar esa smena va tushum manzarasini darhol koradi.'
      }
    ],
    flowLabel: 'Klinika workflowi',
    flowNodes: ['Bemor', 'Registratura', 'Navbat', 'Shifokor', 'EMR', 'Tolov', 'Hisobotlar'],
    flowSummary:
      'Aynan shu zanjir mahsulot qiymatini kontekstsiz modullar royxatidan ancha tezroq ochib beradi.'
  },
  modules: {
    eyebrow: 'Tizim modullari',
    title: 'Klinikaning real yonalishlari uchun modulli arxitektura',
    description:
      'Asosiy workflowni yagona malumot konturini yoqotmasdan mutaxassislik modullari bilan kengaytirish mumkin.',
    items: [
      { title: 'EMR', description: 'Kasallik tarixi, qabul shablonlari, tayinlovlar va hujjatlar.' },
      { title: 'Stomatologiya', description: 'Bemor kartasi, davolash rejasi va stomatolog ish jarayonlari.' },
      { title: 'Kardiologiya', description: 'Korik shablonlari, korsatkichlar nazorati va davolash dinamikasi.' },
      { title: 'Dermatologiya', description: 'Koriklar, foto-fiksatsiya va EMR ichidagi qayta vizitlar.' },
      { title: 'Laboratoriya', description: 'Yonaltirishlar, analiz statuslari va natijalarni vizit bilan boglash.' },
      { title: 'Retseptlar', description: 'Tayinlovlar va hujjatlar shifokor tomonidan qabul vaqtida yaratiladi.' },
      { title: 'Hisobotlar', description: 'Tushum, vizit statistikasi, shifokor yuklamasi va smena nazorati.' },
      { title: 'Moliya', description: 'Kassa oqimi, tolov statuslari, cheklar va xizmatlar boyicha shaffoflik.' }
    ]
  },
  screens: {
    eyebrow: 'Interfeys korinishlari',
    title: 'Jamoa birinchi kundan tushunadigan interfeyslar',
    description:
      'Chiroyli abstraksiyalar emas, balki haqiqiy ish yuzalari korsatiladi: dashboard, navbat, EMR, registratura va analitika.',
    items: [
      {
        label: 'Dashboard',
        title: 'Smenaning operatsion markazi',
        description: 'Navbat, kabinetlar, kassa va yuklama signallari bitta ekranda.'
      },
      {
        label: 'Reception',
        title: 'Qolda malumot otkazmasiz registratura',
        description: 'Bemorni topish, yozuv, vizit ochish va navbatga otkazish bir joyda qoladi.'
      },
      {
        label: 'Queue',
        title: 'Jamoa va bemor uchun shaffof navbat',
        description: 'QR-oqim, tablo va kabinetga taqsimlash holldagi tartibsizliksiz ishlaydi.'
      },
      {
        label: 'EMR',
        title: 'Shifokor qabuli tirik karta ichida',
        description: 'Korik, hujjatlar va tarix alohida vositalarga parchalanib ketmaydi.'
      },
      {
        label: 'Analytics',
        title: 'Tushum va yuklama analitikasi',
        description: 'Rahbar smena natijalarini, ortiqcha yuklamani va osish nuqtalarini qolda jadvalsiz koradi.'
      }
    ]
  },
  integrations: {
    eyebrow: 'Integratsiyalar',
    title: 'Workflowni qolda ishlatmasdan oldinga suradigan integratsiyalar',
    description:
      'Muhim narsa integratsiya borligi emas, balki u real klinik ssenariyning qaysi joyiga togri kelishidir.',
    items: [
      { title: 'Telegram', detail: 'Eslatmalar, ichki signal va bemor bilan aloqa.' },
      { title: 'PayMe', detail: 'Xizmat statusi ichidagi tez tolovlar.' },
      { title: 'Click', detail: 'Vizit va kassa oqimi bilan boglangan tolov bosqichi.' },
      { title: 'Apelsin', detail: 'Shu jarayon ichidagi yana bir lokal tolov kanali.' },
      { title: 'QR check-in', detail: 'Bemor navbatga tushadi va registraturaga ortiqcha yuk tushirmaydi.' },
      { title: 'PDF / chop etish', detail: 'Hujjatlar va cheklar qolda emas, tizim ichidan chiqadi.' }
    ]
  },
  security: {
    eyebrow: 'Xavfsizlik',
    title: 'Tibbiy jamoa uchun kirish nazorati va harakatlarning shaffofligi',
    description:
      'Tibbiyotda qulaylik faqat har bir harakat kuzatiladigan va operatsion jihatdan bashorat qilinadigan bolsa qiymat beradi.',
    items: [
      { title: 'Audit logs', description: 'Har bir muhim amal rol, vaqt va workflow bosqichi boyicha kuzatiladi.' },
      { title: 'Role system', description: 'Rolga asoslangan kirish tasodifiy yoki ortiqcha ozgarishlar xavfini kamaytiradi.' },
      { title: 'Change history', description: 'Ozgarishlar tarixi tortishuvli holatlar va ichki tekshiruvlarni tahlil qilishga yordam beradi.' },
      { title: 'Backup-ready ops', description: 'Tiklash va uzluksiz ish tizimning asosiy yondashuviga kiritilgan, keyinga qoldirilmagan.' }
    ]
  },
  advantages: {
    eyebrow: 'Tizim afzalliklari',
    title: 'Joriy qilishdan oldin va keyin ikki xil klinikadek korinadi',
    description:
      'Bu blok mahsulot kundalik tartibsizlikni qanday olib tashlashini tezda korsatadi, shunchaki abstrakt samarasizlikni emas.',
    beforeTitle: 'Tizimsiz',
    afterTitle: 'MediClinic Pro bilan',
    beforeItems: [
      'Qogoz kartalar va tarqoq yozuvlar',
      'Registratura, shifokor va kassa orasida kontekst yoqolishi',
      'Navbatdagi tartibsizlik va bemor statusining noaniqligi',
      'Kun oxirida qolda yigiladigan hisobotlar'
    ],
    afterItems: [
      'Jamoa uchun yagona EMR va umumiy bemor kartasi',
      'Shaffof navbat va bemorning aniq marshruti',
      'Tolovlar va cheklar klinik workflow ichida',
      'Smena, tushum va shifokor yuklamasi boyicha analitika qolda yigmasdan'
    ]
  },
  pricing: {
    eyebrow: 'Tariflar',
    title: 'Kichik klinikalar, osayotgan jamoalar va tarmoqlar uchun uchta tarif',
    description:
      'Aniq narx modullar va integratsiyalarga bogliq, shuning uchun landing oylab topilgan raqamlar emas, tushunarli tanlov ramkasini korsatadi.',
    footnote: 'Aniq tarkib va narx demo song klinika workflowiga qarab belgilanadi.',
    plans: [
      {
        name: 'Starter',
        audience: 'Kichik klinikalar uchun',
        price: 'Sorov boyicha',
        note: 'Bitta jamoa va bazaviy bemor oqimi uchun tez start.',
        features: ['Registratura va yozuv', 'Shifokor EMR', 'Bemor navbati', 'Bazaviy hisobotlar'],
        cta: 'Demo sorash'
      },
      {
        name: 'Professional',
        audience: 'Osayotgan klinikalar uchun',
        price: 'Sorov boyicha',
        note: 'Qabul, tolovlar va analitika uchun yagona kontur kerak bolgan klinikalar uchun optimal variant.',
        features: ['Starter ichidagi hammasi', 'PayMe / Click / Apelsin', 'Telegram xabarnomalari', 'Kengaytirilgan hisobot va rollar'],
        cta: 'Professionalni tanlash',
        featured: true
      },
      {
        name: 'Enterprise',
        audience: 'Klinikalar tarmogi uchun',
        price: 'Sorov boyicha',
        note: 'Kop filialli ish, qoshimcha modullar va murakkab oqimlar uchun rollout yordami.',
        features: ['Professional ichidagi hammasi', 'Mutaxassislik modullari', 'Ustuvor yordam', 'Maxsus rollout va SLA'],
        cta: 'Enterprise ni muhokama qilish'
      }
    ]
  },
  faq: {
    eyebrow: 'FAQ',
    title: 'Joriy qilishdan oldin eng kop beriladigan savollar',
    description:
      'Kuchli SaaS landing asosiy etirozlarni qongiroqdan oldin yopadi, hammasini faqat savdo jamoasiga qoldirmaydi.',
    items: [
      {
        question: 'Joriy qilish qancha vaqt oladi?',
        answer: 'Bazaviy kontur tez tayyorlanadi, aniq muddat esa rollar, modullar va klinikaning hozirgi jarayonlariga bogliq.'
      },
      {
        question: 'Mavjud bemorlar bazasini kochirish mumkinmi?',
        answer: 'Ha. Joriy qilishni mavjud malumotlarni import qilish va jamoani yangi workflowga bosqichma-bosqich otkazish atrofida qurish mumkin.'
      },
      {
        question: 'Tizim telefonda ishlaydimi?',
        answer: 'Asosiy ekranlar moslashuvchan, shuning uchun rahbar va jamoa workflowning muhim qismlarini mobil qurilmalardan ham ochishi mumkin.'
      },
      {
        question: 'Platforma bir nechta filial uchun mosmi?',
        answer: 'Ha. Modulli arxitektura va rollar tizimni bitta klinikadan kop filialli tarmoqqacha kengaytirishga yordam beradi.'
      }
    ]
  },
  finalCta: {
    eyebrow: 'Yakuniy CTA',
    title: 'Klinikani yagona operatsion konturga otkazing',
    description:
      'Demo aynan sizning workflowingiz boyicha korsatiladi: registratura, navbat, shifokor, EMR, tolovlar va hisobotlar bitta ssenariyda.',
    primaryCta: 'Demo sorash',
    secondaryCta: 'Litsenziyani faollashtirish',
    bullets: [
      'Hozirgi patient flow va yoqotish nuqtalarini tahlil qilamiz',
      'Klinikangizga mos modullar va integratsiyalarni korsatamiz',
      'Jamoaga uzoq otish davrisiz start berishga yordam beramiz'
    ]
  },
  contactLabels: {
    address: 'Manzil',
    phone: 'Telefon',
    schedule: 'Ish vaqti',
    support: 'Yordam'
  },
  footer: {
    tagline: 'EMR, registratura, navbat, tolovlar va analitika bitta konturda.',
    groups: [
      {
        title: 'Mahsulot',
        links: [
          { label: 'Imkoniyatlar', href: '#product' },
          { label: 'Workflow', href: '#workflow' },
          { label: 'Modullar', href: '#modules' }
        ]
      },
      {
        title: 'Resurslar',
        links: [
          { label: 'Integratsiyalar', href: '#integrations' },
          { label: 'Tariflar', href: '#pricing' },
          { label: 'FAQ', href: '#faq' }
        ]
      }
    ],
    footnote: 'Xususiy klinikalar, diagnostika markazlari va klinikalar tarmoqlari uchun mos.'
  },
  activationTitle: 'Litsenziyani faollashtirish'
};

const KK_OVERRIDES = {
  liveStatus: 'EMR, кезек және төлемдерге арналған Clinic OS',
  navigationLabel: 'Лендинг навигациясы',
  languageSwitchLabel: 'Тілді ауыстыру',
  headerLogin: 'Кіру',
  navigation: [
    { id: 'product', label: 'Өнім' },
    { id: 'modules', label: 'Модульдер' },
    { id: 'integrations', label: 'Интеграциялар' },
    { id: 'pricing', label: 'Тарифтер' },
    { id: 'faq', label: 'FAQ' }
  ],
  hero: {
    eyebrow: 'Заманауи клиникаға арналған Clinic OS',
    title: 'EMR, кезек және төлемдерді бір ырғақта ұстайтын клиниканы басқарудың бірыңғай жүйесі.',
    description:
      'MediClinic Pro тіркеуді, дәрігерді, QR-кезекті, төлемдерді, Telegram және есептерді бір workflow ішінде біріктіреді, командалар арасындағы қол еңбегін азайтады.',
    primaryCta: 'Демоны ашу',
    secondaryCta: 'Интерфейсті қарау',
    proofChips: ['Дәрігер EMR', 'QR-кезек', 'Telegram сигналдары', 'Төлемдер мен есептер'],
    quickStats: [
      { value: '4', label: 'негізгі рөл', detail: 'тіркеу, дәрігер, касса, басшылық' },
      { value: '1', label: 'бірыңғай workflow', detail: 'тіркеуден есепке дейін' },
      { value: '24/7', label: 'операциялық көрініс', detail: 'кезек, төлем және статус бақылауы' }
    ],
    visualPanels: [
      {
        label: 'Dashboard',
        title: 'Басшылық клиниканы нақты уақытта көреді',
        description: 'Кезек, кабинет жүктемесі және ауысым сигналдары бір терезеде тұрады.',
        bullets: ['Слоттар мен дәрігер жүктемесі', 'Кешігу мен кезек сигналдары', 'Түсім және статус жиынтығы']
      },
      {
        label: 'QR Queue',
        title: 'Тіркеу ағынды ретсіздіксіз басқарады',
        description: 'QR-кезек, табло және пациент маршруты бір байланысқан сценарий ретінде жұмыс істейді.',
        bullets: ['Жазылуды тексеру және визит ашу', 'Дұрыс кабинетке бағыттау', 'Пациент үшін ашық кезек']
      },
      {
        label: 'Doctor EMR',
        title: 'Дәрігер қабылдауды тірі пациент картасының ішінде жүргізеді',
        description: 'Тарих, қарау шаблондары және PDF құжаттар қабылдау кезінде EMR ішінде қалады.',
        bullets: ['Қарау шаблондары мен тағайындаулар', 'Визит тарихы мен файлдар', 'Қолмен қайта терусіз құжаттар']
      }
    ]
  },
  trust: {
    eyebrow: 'Жүйе бірінші күннен нені жабады',
    title: 'Бос уәделер емес, нақты операциялық контур',
    description:
      'Әр карточка команда күнде қолданатын клиникалық процестің нақты бөлігін көрсетеді, жай ғана жалпы цифрландыру сөзін емес.',
    items: [
      { value: 'EMR + PDF', label: 'қабылдау картасы', detail: 'қарау шаблондары, тарих және құжаттар' },
      { value: 'QR Queue', label: 'пациент ағыны', detail: 'электронды кезек, табло және кабинетке бағыттау' },
      { value: 'PayMe / Click / Apelsin', label: 'төлем контуры', detail: 'касса, түбіртек және қызмет статусы қолмен салыстырусыз' },
      { value: 'Telegram + Reports', label: 'байланыс және аналитика', detail: 'ескертулер, есептер, дәрігер жүктемесі және түсім көрінісі' }
    ]
  },
  features: {
    eyebrow: 'Негізгі мүмкіндіктер',
    title: 'Клиниканың маңызды процестері бір платформада жиналады',
    description:
      'Лендинг клиниканың шынайы жұмысына сүйеніп құрылған: қабылдау, кезек, дәрігер workflow-ы, төлем және басшылық бақылауы.',
    items: [
      {
        badge: 'Дәрігер EMR',
        title: 'Әр қабылдау үшін тірі пациент картасы',
        description: 'Қарау шаблондары, ауру тарихы, тағайындаулар және PDF құжаттар бір қабылдау ағынында қалады.'
      },
      {
        badge: 'Тіркеу',
        title: 'Жылдам тіркеу және пациентті табу',
        description: 'Визит ашу, жазылуды тексеру және пациентті бағыттау артық терезесіз орындалады.'
      },
      {
        badge: 'Кезек',
        title: 'QR-кезек және ағынды басқару',
        description: 'Табло, кабинет кезектері және анық status flow холлдағы ретсіздікті азайтады.'
      },
      {
        badge: 'Төлемдер',
        title: 'Касса мен түбіртектер клиникалық сценарийдің ішінде',
        description: 'PayMe, Click және Apelsin қызметтермен бір процесте жұмыс істейді, бөлек емес.'
      },
      {
        badge: 'Хабарламалар',
        title: 'Telegram сигналдары қолмен қадағалаусыз',
        description: 'Пациент пен команда жазылу, күту және қабылдау аяқталуында қажетті сигналды дер кезінде алады.'
      },
      {
        badge: 'Есептер',
        title: 'Түсім, жүктеме және ауысым аналитикасы',
        description: 'Басшылық кезек қай жерде өсіп жатқанын, дәрігерлердің қаншалықты бос емес екенін және түсімнің қалай өзгеретінін көреді.'
      }
    ]
  },
  workflow: {
    eyebrow: 'Жүйе қалай жұмыс істейді',
    title: 'Пациент тіркеуден есепке дейін қолмен үзіліссіз өтеді',
    description:
      'Күрделі медициналық өнім үшін ең күшті сату құралы үзілген feature тізімі емес, нақты end-to-end клиника workflow-ы.',
    steps: [
      {
        title: '01. Пациент тіркеледі',
        description: 'Тіркеу пациентті табады, жазылуды растайды және қабылдауды қағазсыз бастайды.'
      },
      {
        title: '02. Кезекке түседі',
        description: 'Жүйе пациентті дұрыс ағынға бағыттайды, ал команда мен табло бірдей статусты көреді.'
      },
      {
        title: '03. Дәрігер EMR ішінде жұмыс істейді',
        description: 'Қабылдау, тарих, шаблондар және құжаттар бір байланысқан пациент картасының ішінде қалады.'
      },
      {
        title: '04. Төлем мен есептер автоматты жаңарады',
        description: 'Касса қызметтерді жабады, ал басшылық ауысым мен түсім көрінісін бірден көреді.'
      }
    ],
    flowLabel: 'Клиника workflow-ы',
    flowNodes: ['Пациент', 'Тіркеу', 'Кезек', 'Дәрігер', 'EMR', 'Төлем', 'Есептер'],
    flowSummary:
      'Дәл осы тізбек өнімнің құнын контекссіз модульдер тізімінен әлдеқайда тезірек ашады.'
  },
  modules: {
    eyebrow: 'Жүйе модульдері',
    title: 'Клиниканың нақты бағыттарына арналған модульдік архитектура',
    description:
      'Негізгі workflow-ды бірыңғай дерек контурын жоғалтпай, мамандандырылған модульдермен кеңейтуге болады.',
    items: [
      { title: 'EMR', description: 'Ауру тарихы, қабылдау шаблондары, тағайындаулар және құжаттар.' },
      { title: 'Стоматология', description: 'Пациент картасы, емдеу жоспары және стоматолог workflow-ы.' },
      { title: 'Кардиология', description: 'Қарау шаблондары, көрсеткіштерді бақылау және ем динамикасы.' },
      { title: 'Дерматология', description: 'Қараулар, фотофиксация және EMR ішіндегі қайталама визиттер.' },
      { title: 'Зертхана', description: 'Жолдамалар, талдау статустары және нәтижелерді визитпен байланыстыру.' },
      { title: 'Рецепттер', description: 'Тағайындаулар мен құжаттарды дәрігер қабылдау кезінде бірден жасайды.' },
      { title: 'Есептер', description: 'Түсім, визит статистикасы, дәрігер жүктемесі және ауысым бақылауы.' },
      { title: 'Қаржы', description: 'Касса ағыны, төлем статустары, түбіртектер және қызмет бойынша ашықтық.' }
    ]
  },
  screens: {
    eyebrow: 'Интерфейс көріністері',
    title: 'Команда бірінші күннен түсінетін интерфейстер',
    description:
      'Әдемі абстракциялар емес, нақты жұмыс беттері көрсетіледі: dashboard, кезек, EMR, тіркеу және аналитика.',
    items: [
      {
        label: 'Dashboard',
        title: 'Ауысымның операциялық орталығы',
        description: 'Кезек, кабинеттер, касса және жүктеме сигналдары бір экранда.'
      },
      {
        label: 'Reception',
        title: 'Қолмен дерек тасымалдаусыз тіркеу',
        description: 'Пациентті табу, жазылу, визит ашу және кезекке өткізу бір жерде қалады.'
      },
      {
        label: 'Queue',
        title: 'Команда мен пациент үшін ашық кезек',
        description: 'QR-ағын, табло және кабинетке бөлу холлдағы ретсіздіксіз жұмыс істейді.'
      },
      {
        label: 'EMR',
        title: 'Дәрігер қабылдауы тірі карта ішінде',
        description: 'Қарау, құжаттар және тарих бөлек құралдарға бөлініп кетпейді.'
      },
      {
        label: 'Analytics',
        title: 'Түсім мен жүктеме аналитикасы',
        description: 'Басшылық ауысым нәтижелерін, артық жүктемені және өсу нүктелерін қолмен кестесіз көреді.'
      }
    ]
  },
  integrations: {
    eyebrow: 'Интеграциялар',
    title: 'Workflow-ды қолмен жұмыссыз ілгерілететін интеграциялар',
    description:
      'Маңыздысы интеграцияның бар болуы ғана емес, оның нақты клиникалық сценарийдегі орны.',
    items: [
      { title: 'Telegram', detail: 'Ескертулер, ішкі сигналдар және пациентпен байланыс.' },
      { title: 'PayMe', detail: 'Қызмет статусының ішіндегі жылдам төлемдер.' },
      { title: 'Click', detail: 'Визит пен касса ағынымен байланысқан төлем қадамы.' },
      { title: 'Apelsin', detail: 'Сол процестің ішіндегі тағы бір жергілікті төлем арнасы.' },
      { title: 'QR check-in', detail: 'Пациент кезекке түседі де, тіркеуге артық жүктеме қоспайды.' },
      { title: 'PDF / басып шығару', detail: 'Құжаттар мен түбіртектер қолмен емес, жүйенің ішінен шығады.' }
    ]
  },
  security: {
    eyebrow: 'Қауіпсіздік',
    title: 'Медициналық команда үшін қолжетімділік бақылауы және әрекет ашықтығы',
    description:
      'Медицинада ыңғайлылық әр әрекет бақыланатын және операциялық тұрғыдан болжамды болғанда ғана шынайы құндылық береді.',
    items: [
      { title: 'Audit logs', description: 'Әр маңызды әрекет рөл, уақыт және workflow қадамы бойынша бақыланады.' },
      { title: 'Role system', description: 'Рөлге негізделген қолжетімділік кездейсоқ немесе артық өзгерістер қаупін азайтады.' },
      { title: 'Change history', description: 'Өзгерістер тарихы даулы жағдайлар мен ішкі тексерулерді талдауға көмектеседі.' },
      { title: 'Backup-ready ops', description: 'Қалпына келтіру және үздіксіз жұмыс жүйенің негізгі тәсіліне енгізілген, кейінге қалдырылмаған.' }
    ]
  },
  advantages: {
    eyebrow: 'Жүйе артықшылықтары',
    title: 'Енгізуге дейін және кейін екі бөлек клиника сияқты көрінеді',
    description:
      'Бұл блок өнімнің күнделікті ретсіздікті қалай алып тастайтынын тез көрсетеді, жай ғана абстрактілі тиімсіздікті емес.',
    beforeTitle: 'Жүйесіз',
    afterTitle: 'MediClinic Pro-пен',
    beforeItems: [
      'Қағаз карталар және шашыраңқы жазбалар',
      'Тіркеу, дәрігер және касса арасында контекст жоғалуы',
      'Кезектегі ретсіздік және пациент статусының түсініксіздігі',
      'Күн соңында қолмен жиналатын есептер'
    ],
    afterItems: [
      'Команда үшін бірыңғай EMR және ортақ пациент картасы',
      'Ашық кезек және пациенттің анық маршруты',
      'Төлемдер мен түбіртектер клиникалық workflow ішінде',
      'Ауысым, түсім және дәрігер жүктемесі бойынша аналитика қолмен жинаусыз'
    ]
  },
  pricing: {
    eyebrow: 'Тарифтер',
    title: 'Шағын клиникаларға, өсіп жатқан командаларға және желілерге арналған үш тариф',
    description:
      'Нақты баға модульдер мен интеграцияларға байланысты, сондықтан лендинг ойдан шығарылған сандар емес, түсінікті таңдау шеңберін көрсетеді.',
    footnote: 'Нақты құрам мен баға workflow-ға негізделген демодан кейін бекітіледі.',
    plans: [
      {
        name: 'Starter',
        audience: 'Шағын клиникалар үшін',
        price: 'Сұраныс бойынша',
        note: 'Бір команда мен базалық пациент ағыны үшін жылдам старт.',
        features: ['Тіркеу және жазылу', 'Дәрігер EMR', 'Пациент кезегі', 'Негізгі есептер'],
        cta: 'Демо сұрау'
      },
      {
        name: 'Professional',
        audience: 'Өсіп жатқан клиникалар үшін',
        price: 'Сұраныс бойынша',
        note: 'Қабылдау, төлем және аналитика үшін бірыңғай контур қажет клиникаларға оңтайлы нұсқа.',
        features: ['Starter ішіндегі барлығы', 'PayMe / Click / Apelsin', 'Telegram хабарламалары', 'Кеңейтілген есептер мен рөлдер'],
        cta: 'Professional таңдау',
        featured: true
      },
      {
        name: 'Enterprise',
        audience: 'Клиника желілері үшін',
        price: 'Сұраныс бойынша',
        note: 'Көп филиалды жұмыс, қосымша модульдер және күрделі ағындар үшін rollout қолдауы.',
        features: ['Professional ішіндегі барлығы', 'Мамандандырылған модульдер', 'Басым қолдау', 'Арнайы rollout және SLA'],
        cta: 'Enterprise талқылау'
      }
    ]
  },
  faq: {
    eyebrow: 'FAQ',
    title: 'Енгізуге дейін жиі қойылатын сұрақтар',
    description:
      'Күшті SaaS лендингі негізгі қарсылықтарды қоңырауға дейін жабады, бәрін тек сату командасына қалдырмайды.',
    items: [
      {
        question: 'Енгізу қанша уақыт алады?',
        answer: 'Базалық контурды тез дайындауға болады, ал нақты мерзім рөлдер, модульдер және клиниканың қазіргі процестеріне байланысты.'
      },
      {
        question: 'Қазіргі пациент базасын көшіруге бола ма?',
        answer: 'Иә. Енгізуді ағымдағы деректерді импорттау және команданы жаңа workflow-ға кезең-кезеңімен көшіру айналасында ұйымдастыруға болады.'
      },
      {
        question: 'Жүйе телефонда жұмыс істей ме?',
        answer: 'Негізгі экрандар бейімделгіш, сондықтан басшылық пен команда workflow-дың маңызды бөліктерін мобильді құрылғылардан да аша алады.'
      },
      {
        question: 'Платформа бірнеше филиалға жарай ма?',
        answer: 'Иә. Модульдік архитектура мен рөлдер жүйені бір клиникадан көп филиалды желіге дейін масштабтауға көмектеседі.'
      }
    ]
  },
  finalCta: {
    eyebrow: 'Соңғы CTA',
    title: 'Клиниканы бірыңғай операциялық контурға көшіріңіз',
    description:
      'Демоны дәл сіздің workflow-ыңыз бойынша көрсетеміз: тіркеу, кезек, дәрігер, EMR, төлемдер және есептер бір сценарийде.',
    primaryCta: 'Демо сұрау',
    secondaryCta: 'Лицензияны белсендіру',
    bullets: [
      'Қазіргі patient flow және жоғалту нүктелерін талдаймыз',
      'Клиникаңызға сай модульдер мен интеграцияларды көрсетеміз',
      'Командаға ұзақ өтпелі кезеңсіз старт беруге көмектесеміз'
    ]
  },
  contactLabels: {
    address: 'Мекенжай',
    phone: 'Телефон',
    schedule: 'Жұмыс уақыты',
    support: 'Қолдау'
  },
  footer: {
    tagline: 'EMR, тіркеу, кезек, төлемдер және аналитика бір контурда.',
    groups: [
      {
        title: 'Өнім',
        links: [
          { label: 'Мүмкіндіктер', href: '#product' },
          { label: 'Workflow', href: '#workflow' },
          { label: 'Модульдер', href: '#modules' }
        ]
      },
      {
        title: 'Ресурстар',
        links: [
          { label: 'Интеграциялар', href: '#integrations' },
          { label: 'Тарифтер', href: '#pricing' },
          { label: 'FAQ', href: '#faq' }
        ]
      }
    ],
    footnote: 'Жеке клиникаларға, диагностика орталықтарына және клиникалар желісіне сай.'
  },
  activationTitle: 'Лицензияны белсендіру'
};

export const LANDING_COPY = {
  ru: BASE_COPY,
  en: deepMerge(BASE_COPY, EN_OVERRIDES),
  uz: deepMerge(BASE_COPY, UZ_OVERRIDES),
  kk: deepMerge(BASE_COPY, KK_OVERRIDES)
};

export function buildGlassStyle(isDark, emphasis = 'default') {
  const baseStyle = {
    border: isDark ? '1px solid rgba(255, 255, 255, 0.12)' : '1px solid rgba(15, 23, 42, 0.08)',
    boxShadow: isDark ? '0 24px 80px rgba(2, 6, 23, 0.42)' : '0 24px 80px rgba(15, 23, 42, 0.12)',
    backdropFilter: 'blur(24px)',
    WebkitBackdropFilter: 'blur(24px)'
  };

  if (emphasis === 'hero') {
    return {
      ...baseStyle,
      background: isDark
        ? 'linear-gradient(155deg, rgba(15, 23, 42, 0.94), rgba(14, 165, 233, 0.18))'
        : 'linear-gradient(155deg, rgba(255, 255, 255, 0.96), rgba(14, 165, 233, 0.16))'
    };
  }

  if (emphasis === 'accent') {
    return {
      ...baseStyle,
      background: isDark
        ? 'linear-gradient(160deg, rgba(17, 24, 39, 0.88), rgba(34, 197, 94, 0.16))'
        : 'linear-gradient(160deg, rgba(255, 255, 255, 0.94), rgba(34, 197, 94, 0.14))'
    };
  }

  return {
    ...baseStyle,
    background: isDark
      ? 'linear-gradient(180deg, rgba(15, 23, 42, 0.84), rgba(15, 23, 42, 0.7))'
      : 'linear-gradient(180deg, rgba(255, 255, 255, 0.94), rgba(255, 255, 255, 0.78))'
  };
}
