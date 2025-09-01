import React, { useEffect, useState, useRef } from 'react';
import PropTypes from 'prop-types';
import { openOnlineQueue, getOnlineQueueStats } from '../api/queues';
import { getApiBase } from '../api/client';

function formatDateYYYYMMDD(d) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export default function QueueTable({ department }) {
  const [stats, setStats] = useState(null);
  const wsRef = useRef(null);

  const todayStr = formatDateYYYYMMDD(new Date());

  useEffect(() => {
    // fetch stats initially
    refreshStats();

    // open queue (ensure start_number=0)
    openQueue();

    // open WS
    openQueueWS();

    return () => {
      // cleanup socket
      if (wsRef.current) {
        try { wsRef.current.close(); } catch (e) {
          // Игнорируем ошибки закрытия WebSocket
        }
        wsRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [department, todayStr]);

  async function refreshStats() {
    try {
      const res = await getOnlineQueueStats(department, todayStr);
      setStats(res);
    } catch (err) {
      console.error('Failed to load queue stats:', err);
    }
  }

  async function openQueue() {
    try {
      // note: backend expects POST /online-queue/open with params department & date_str & start_number
      await openOnlineQueue(department, todayStr, 0); // <-- start_number = 0
      await refreshStats();
    } catch (err) {
      console.error('Failed to open queue:', err);
    }
  }

  function openQueueWS() {
    try {
      const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const wsHost = 'localhost:8000'; // Бэкенд работает на порту 8000
      const token = localStorage.getItem('auth_token') || '';
      // build ws url: ws://localhost:8000/ws/queue?department=...&date_str=...&token=...
      const wsUrl = `${wsProto}//${wsHost}/ws/queue?department=${encodeURIComponent(
        department
      )}&date_str=${encodeURIComponent(todayStr)}${token ? `&token=${encodeURIComponent(token)}` : ''}`;

      // close previous
      if (wsRef.current) {
        try { wsRef.current.close(); } catch (e) {
          // Игнорируем ошибки закрытия WebSocket
        }
        wsRef.current = null;
      }

      const socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.addEventListener('open', () => {
        // console.log("Queue WS open", wsUrl);
      });

      socket.addEventListener('message', (ev) => {
        try {
          const data = JSON.parse(ev.data);
          // refresh or set stats based on event shape
          if (data?.stats) {
            setStats(data.stats);
          } else {
            // fallback to refreshing
            refreshStats();
          }
        } catch (e) {
          // not JSON — just refresh
          refreshStats();
        }
      });

      socket.addEventListener('close', () => {
        // console.info("Queue WS closed");
      });

      socket.addEventListener('error', (e) => {
        console.warn('Queue WS error', e);
      });
    } catch (e) {
      console.error('Failed to open queue WS', e);
    }
  }

  return (
    <div className="p-2">
      <h3>Queue — {department}</h3>
      {stats ? (
        <pre>{JSON.stringify(stats, null, 2)}</pre>
      ) : (
        <div>Loading...</div>
      )}
      <div className="space-x-2 mt-2">
        <button onClick={() => openQueue()}>Open queue (start 0)</button>
        <button onClick={() => refreshStats()}>Refresh</button>
      </div>
    </div>
  );
}

QueueTable.propTypes = {
  department: PropTypes.string.isRequired,
};
