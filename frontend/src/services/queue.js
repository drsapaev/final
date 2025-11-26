// Единый сервис работы с очередью и приемом пациента

function getAuthToken() {
	return (
		localStorage.getItem('auth_token') ||
		localStorage.getItem('access_token') ||
		localStorage.getItem('token') ||
		''
	);
}

async function apiRequest(path, options = {}) {
	const base = options.absolute ? '' : 'http://localhost:8000';
	const token = getAuthToken();
	
	if (!token) {
		console.error('[queueService] No auth token found');
		throw new Error('Требуется авторизация. Пожалуйста, войдите в систему.');
	}
	
	const headers = {
		'Content-Type': 'application/json',
		...(options.headers || {}),
		...(token ? { Authorization: `Bearer ${token}` } : {})
	};
	
	console.log(`[queueService] ${options.method || 'GET'} ${path}`, { hasToken: !!token, tokenLength: token.length });
	
	const res = await fetch(`${base}/api/v1${path}`, {
		method: options.method || 'GET',
		headers,
		body: options.body ? JSON.stringify(options.body) : undefined,
	});
	
	if (!res.ok) {
		let detail = 'Ошибка запроса';
		let errorData = null;
		try {
			errorData = await res.json();
			detail = errorData.detail || errorData.message || detail;
		} catch (_) {
			detail = `HTTP ${res.status}: ${res.statusText}`;
		}
		
		console.error(`[queueService] Request failed: ${path}`, {
			status: res.status,
			statusText: res.statusText,
			detail,
			errorData
		});
		
		throw new Error(detail);
	}
	try {
		return await res.json();
	} catch (_) {
		return null;
	}
}

// Глобальное уведомление об обновлении очереди
function notifyQueueUpdate(specialty, action = 'update') {
	console.log('[queueService] notifyQueueUpdate:', { specialty, action });
	// Отправляем CustomEvent для синхронизации всех компонентов
	const event = new CustomEvent('queueUpdated', {
		detail: { specialty, action, timestamp: Date.now() }
	});
	window.dispatchEvent(event);
}

export const queueService = {
	// Очередь врача на сегодня по специальности
	getTodayQueue: async (specialty) => {
		return apiRequest(`/doctor/${encodeURIComponent(specialty)}/queue/today`);
	},

	// Вызвать пациента в кабинет (по id записи очереди)
	callPatient: async (entryId) => {
		const result = await apiRequest(`/doctor/queue/${entryId}/call`, { method: 'POST' });
		// Уведомляем об обновлении
		notifyQueueUpdate('all', 'patientCalled');
		return result;
	},

	// Начать прием пациента
	startVisit: async (entryId) => {
		const result = await apiRequest(`/doctor/queue/${entryId}/start-visit`, { method: 'POST' });
		// Уведомляем об обновлении
		notifyQueueUpdate('all', 'visitStarted');
		return result;
	},

	// Завершить прием пациента (можно передать med data)
	completeVisit: async (entryId, visitData) => {
		const result = await apiRequest(`/doctor/queue/${entryId}/complete`, {
			method: 'POST',
			body: visitData || {},
		});
		// Уведомляем об обновлении после завершения приема
		notifyQueueUpdate('all', 'visitCompleted');
		console.log('[queueService] completeVisit: отправлено уведомление об обновлении очереди');
		return result;
	},

	// Вызвать следующего ожидающего пациента по специальности
	callNextWaiting: async (specialty) => {
		const queue = await apiRequest(`/doctor/${encodeURIComponent(specialty)}/queue/today`);
		if (!queue?.entries?.length) return { success: false, message: 'Очередь пуста' };
		const waiting = queue.entries.find((e) => e.status === 'waiting');
		if (!waiting) return { success: false, message: 'Нет ожидающих пациентов' };
		await apiRequest(`/doctor/queue/${waiting.id}/call`, { method: 'POST' });
		// Уведомляем об обновлении
		notifyQueueUpdate(specialty, 'nextPatientCalled');
		return { success: true, entry: waiting };
	},
};
