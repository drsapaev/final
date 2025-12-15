import React from 'react';
import { Card, Badge, Button } from '../ui/macos';
import { Clock, User, ArrowRight, Loader } from 'lucide-react';

const QueuePositionCard = ({ queueEntry, onRefresh }) => {
    if (!queueEntry) return null;

    const {
        id,
        number,
        status,
        peopleBefore,
        estimatedWaitTime,
        doctorName,
        specialty,
        cabinet
    } = queueEntry;

    // Определение цветов и текстов в зависимости от статуса
    const getStatusConfig = (status) => {
        switch (status) {
            case 'waiting':
                return {
                    color: 'var(--mac-accent-blue)',
                    bgColor: 'rgba(0, 122, 255, 0.1)',
                    text: 'В ожидании',
                    description: `Перед вами ${peopleBefore || 0} чел.`
                };
            case 'called':
                return {
                    color: 'var(--mac-success)',
                    bgColor: 'rgba(52, 199, 89, 0.1)',
                    text: 'Вас вызывают!',
                    description: `Проходите в кабинет ${cabinet || '?'}`
                };
            case 'in_service':
            case 'in_cabinet':
                return {
                    color: 'var(--mac-warning)',
                    bgColor: 'rgba(255, 149, 0, 0.1)',
                    text: 'На приёме',
                    description: 'Идёт приём'
                };
            default:
                return {
                    color: 'var(--mac-text-secondary)',
                    bgColor: 'var(--mac-bg-secondary)',
                    text: 'Статус неизвестен',
                    description: ''
                };
        }
    };

    const config = getStatusConfig(status);

    return (
        <Card className="p-4" style={{ borderLeft: `4px solid ${config.color}` }}>
            <div className="flex justify-between items-start mb-2">
                <div>
                    <h3 className="text-lg font-bold" style={{ color: config.color }}>
                        Талон №{number}
                    </h3>
                    <p className="text-sm font-medium text-gray-700">
                        {specialty} • {doctorName || 'Врач'}
                    </p>
                </div>
                <Badge style={{ backgroundColor: config.bgColor, color: config.color }}>
                    {config.text}
                </Badge>
            </div>

            <div className="flex items-center justify-between mt-4">
                <div className="flex items-center gap-2">
                    <User size={16} className="text-gray-400" />
                    <span className="text-sm text-gray-600">
                        {config.description}
                    </span>
                </div>
                {status === 'waiting' && estimatedWaitTime > 0 && (
                    <div className="flex items-center gap-2">
                        <Clock size={16} className="text-gray-400" />
                        <span className="text-sm text-gray-600">
                            ~{estimatedWaitTime} мин
                        </span>
                    </div>
                )}
            </div>

            {status === 'called' && (
                <div className="mt-4 p-3 bg-green-50 rounded-lg border border-green-100 animate-pulse">
                    <p className="text-center text-green-700 font-bold mb-2">
                        Пожалуйста, пройдите в кабинет №{cabinet}
                    </p>
                    <p className="text-center text-xs text-green-600">
                        Вас ожидает врач
                    </p>
                </div>
            )}
        </Card>
    );
};

export default QueuePositionCard;
