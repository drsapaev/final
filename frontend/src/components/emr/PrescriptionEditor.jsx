/**
 * PrescriptionEditor - Виджет назначений
 * 
 * Позволяет врачу:
 * 1. Добавлять препараты из списка (или драфт)
 * 2. Указывать дозировку, кратность, длительность
 * 3. Просматривать список назначений
 * 4. Удалять/Редактировать
 */

import React, { useState, useEffect, useRef } from 'react';
import { Plus, Trash2, Pill, Search, Clock, FileText, ChevronRight } from 'lucide-react';
import './PrescriptionEditor.css';

// Mock DB препаратов
const MOCK_DRUGS = [
    { name: 'Амоксициллин', defaultDose: '500 мг', defaultFreq: '3 раза в день' },
    { name: 'Ибупрофен', defaultDose: '400 мг', defaultFreq: 'по требованию' },
    { name: 'Бисопролол', defaultDose: '5 мг', defaultFreq: 'утром' },
    { name: 'Лизиноприл', defaultDose: '10 мг', defaultFreq: 'утром' },
    { name: 'Аторвастатин', defaultDose: '20 мг', defaultFreq: 'вечером' },
    { name: 'Омепразол', defaultDose: '20 мг', defaultFreq: 'за 30 мин до еды' },
    { name: 'Парацетамол', defaultDose: '500 мг', defaultFreq: 'при температуре >38' }
];

const PrescriptionEditor = ({
    prescriptions = [],
    onChange,
    isEditable = true,
    onFieldTouch
}) => {
    const [isAdding, setIsAdding] = useState(false);
    const [newItem, setNewItem] = useState({
        name: '',
        dose: '',
        frequency: '',
        duration: '',
        note: ''
    });
    const [suggestions, setSuggestions] = useState([]);

    // Handlers
    const handleInputChange = (field, value) => {
        setNewItem(prev => ({ ...prev, [field]: value }));

        // Search drugs
        if (field === 'name') {
            if (value.length > 1) {
                const matches = MOCK_DRUGS.filter(d =>
                    d.name.toLowerCase().includes(value.toLowerCase())
                );
                setSuggestions(matches);
            } else {
                setSuggestions([]);
            }
        }
    };

    const handleSelectDrug = (drug) => {
        setNewItem(prev => ({
            ...prev,
            name: drug.name,
            dose: drug.defaultDose,
            frequency: drug.defaultFreq
        }));
        setSuggestions([]);
    };

    const handleAdd = () => {
        if (!newItem.name) return;

        const updated = [...prescriptions, { ...newItem, id: Date.now() }];
        onChange?.(updated);
        onFieldTouch?.('prescriptions');

        // Reset
        setNewItem({ name: '', dose: '', frequency: '', duration: '', note: '' });
        setIsAdding(false);
    };

    const handleDelete = (id) => {
        const updated = prescriptions.filter(p => p.id !== id);
        onChange?.(updated);
        onFieldTouch?.('prescriptions');
    };

    return (
        <div className={`prescription-editor ${!isEditable ? 'prescription-editor--readonly' : ''}`}>
            {/* LIST */}
            {prescriptions.length > 0 && (
                <div className="prescription-list">
                    {prescriptions.map((p, idx) => (
                        <div key={p.id || idx} className="prescription-item">
                            <Pill size={16} className="prescription-item__icon" />
                            <div className="prescription-item__content">
                                <span className="prescription-item__name">{p.name}</span>
                                <span className="prescription-item__details">
                                    {p.dose && `${p.dose} `}
                                    {p.frequency && `• ${p.frequency} `}
                                    {p.duration && `• ${p.duration}`}
                                </span>
                            </div>
                            {isEditable && (
                                <div className="prescription-item__actions">
                                    <button
                                        className="prescription-action-btn prescription-action-btn--delete"
                                        onClick={() => handleDelete(p.id)}
                                        title="Удалить"
                                    >
                                        <Trash2 size={14} />
                                    </button>
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* ADD FORM */}
            {isEditable && (
                <>
                    {!isAdding ? (
                        <button
                            className="prescription-toggle-btn"
                            onClick={() => setIsAdding(true)}
                        >
                            <Plus size={14} />
                            Добавить назначение
                        </button>
                    ) : (
                        <div className="prescription-form">
                            <div className="prescription-form__row" style={{ position: 'relative' }}>
                                <div className="prescription-input-group">
                                    <label className="prescription-label">Препарат</label>
                                    <input
                                        className="prescription-input"
                                        value={newItem.name}
                                        onChange={(e) => handleInputChange('name', e.target.value)}
                                        placeholder="Название..."
                                        autoFocus
                                    />
                                    {suggestions.length > 0 && (
                                        <div className="prescription-suggestions">
                                            {suggestions.map((s, i) => (
                                                <div
                                                    key={i}
                                                    className="prescription-suggestion-item"
                                                    onClick={() => handleSelectDrug(s)}
                                                >
                                                    {s.name}
                                                </div>
                                            ))}
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="prescription-form__row">
                                <div className="prescription-input-group prescription-input-group--small">
                                    <label className="prescription-label">Доза</label>
                                    <input
                                        className="prescription-input"
                                        value={newItem.dose}
                                        onChange={(e) => handleInputChange('dose', e.target.value)}
                                        placeholder="500 мг"
                                    />
                                </div>
                                <div className="prescription-input-group">
                                    <label className="prescription-label">Кратность</label>
                                    <input
                                        className="prescription-input"
                                        value={newItem.frequency}
                                        onChange={(e) => handleInputChange('frequency', e.target.value)}
                                        placeholder="3 р/д"
                                    />
                                </div>
                                <div className="prescription-input-group prescription-input-group--small">
                                    <label className="prescription-label">Длит.</label>
                                    <input
                                        className="prescription-input"
                                        value={newItem.duration}
                                        onChange={(e) => handleInputChange('duration', e.target.value)}
                                        placeholder="7 дней"
                                    />
                                </div>
                            </div>

                            <button className="prescription-add-btn" onClick={handleAdd}>
                                Добавить
                            </button>
                            <button className="prescription-cancel-btn" onClick={() => setIsAdding(false)}>
                                Отмена
                            </button>
                        </div>
                    )}
                </>
            )}
        </div>
    );
};

export default PrescriptionEditor;
