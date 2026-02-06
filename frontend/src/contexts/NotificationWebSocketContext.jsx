
import React, { createContext, useContext, useEffect, useRef } from 'react';
import { useToast } from '../components/common/Toast';
import { tokenManager } from '../utils/tokenManager';

const NotificationWebSocketContext = createContext(null);

export function NotificationWebSocketProvider({ children }) {
    const ws = useRef(null);
    const { addToast } = useToast();
    const reconnectTimeout = useRef(null);

    useEffect(() => {
        connect();
        return () => {
            if (ws.current) {
                ws.current.close();
            }
            if (reconnectTimeout.current) {
                clearTimeout(reconnectTimeout.current);
            }
        };
    }, []);

    function connect() {
        const token = tokenManager.getAccessToken();
        if (!token) {
            // Retry later if no token (e.g. not logged in)
            reconnectTimeout.current = setTimeout(connect, 5000);
            return;
        }

        // Determine WebSocket Protocol (ws/wss) based on current page
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        // Use the backend host or default to same-origin with standard port
        // Simplification: assume backend on port 8000 or proxy. 
        // Ideally use environment variable.
        // Given the rest of the app:
        const host = window.location.hostname;
        // Standard backend port in dev is 8000. In prod, likely same port.
        // If we have API_URL environment variable, we should parse it.
        // For now, let's try a safe bet or a configurable url.
        // Assuming backend is at localhost:8000 for dev environments.

        // Better strategy: Use a known base URL config if available
        let wsUrl = `${protocol}//${host}:8000/api/v1/notification-websocket/ws/notifications/connect?token=${token}`;

        // BUT wait, in existing code, endpoints are often referenced via imports.
        // The endpoint I created is in `app/api/v1/endpoints/notification_websocket.py`
        // And registered as `notification_websocket.router` with tags=["notification-websocket"].
        // It does NOT have a prefix in `api.py`.
        // Wait, let's check api.py again.

        /*
        api_router.include_router(
            notification_websocket.router, tags=["notification-websocket"]
        )
        */

        // And the router implementation:
        // @router.websocket("/ws/notifications/connect")

        // So the full path is `/api/v1/ws/notifications/connect`.

        const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';
        // Convert http(s) to ws(s)
        const wsBase = apiBase.replace(/^http/, 'ws');
        wsUrl = `${wsBase}/ws/notifications/connect?token=${token}`;

        const socket = new WebSocket(wsUrl);

        socket.onopen = () => {
            console.log('Notification WebSocket Connected');
        };

        socket.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleMessage(data);
            } catch (e) {
                console.error('Error parsing WS message:', e);
            }
        };

        socket.onclose = () => {
            console.log('Notification WebSocket Disconnected. Reconnecting...');
            ws.current = null;
            reconnectTimeout.current = setTimeout(connect, 3000);
        };

        socket.onerror = (error) => {
            console.error('Notification WebSocket Error:', error);
            socket.close();
        };

        ws.current = socket;
    }

    function handleMessage(data) {
        if (data.type === 'notification') {
            const { title, message, data: meta } = data;
            // Use Toast to show notification
            // meta.type can be 'error', 'success', etc. if needed
            addToast({
                title: title,
                message: message,
                type: 'info', // Default to info, or map from meta.type
                duration: 5000,
                // Optional: onClick logic using meta (e.g. navigate to queued item)
            });

            // If browsers support Notification API and permission granted, we could also show system notification
            if (document.hidden && Notification.permission === 'granted') {
                new Notification(title, { body: message });
            }
        } else if (data.type === 'queue_update') {
            // Specific handling for queue updates if needed
            addToast({
                title: "Обновление очереди",
                message: `Ваш статус обновлен`,
                type: 'info'
            });
        }
    }

    return (
        <NotificationWebSocketContext.Provider value={{ ws: ws.current }}>
            {children}
        </NotificationWebSocketContext.Provider>
    );
}

export function useNotificationWebSocket() {
    return useContext(NotificationWebSocketContext);
}
