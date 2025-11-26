/**
 * DepartmentManagement Component
 * Manages departments/specialties in the system
 */

import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Save, X } from 'lucide-react';
import { Card, Button, Badge, Input } from '../ui/macos';
import { toast } from 'react-toastify';

const API_BASE = import.meta?.env?.VITE_API_BASE_URL || 'http://localhost:8000';

const DepartmentManagement = () => {
    const [departments, setDepartments] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingId, setEditingId] = useState(null);
    const [showAddForm, setShowAddForm] = useState(false);
    const [formData, setFormData] = useState({
        name_ru: '',
        name_uz: '',
        key: '',
        description: '',
        color: '#0066cc',
        icon: '🏥',
        display_order: 999,
        active: true
    });

    useEffect(() => {
        loadDepartments();
    }, []);

    const loadDepartments = async () => {
        setLoading(true);
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const result = await response.json();
                // Backend returns {success: true, data: [...], count: N}
                setDepartments(result.data || []);
            } else {
                toast.error('Не удалось загрузить отделения');
            }
        } catch (error) {
            console.error('Error loading departments:', error);
            toast.error('Ошибка загрузки отделений');
        } finally {
            setLoading(false);
        }
    };

    const handleAdd = async () => {
        if (!formData.name_ru || !formData.key) {
            toast.error('Заполните обязательные поля');
            return;
        }

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                toast.success('Отделение добавлено');
                setShowAddForm(false);
                setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                loadDepartments();
            } else {
                toast.error('Ошибка при добавлении отделения');
            }
        } catch (error) {
            console.error('Error adding department:', error);
            toast.error('Ошибка при добавлении отделения');
        }
    };

    const handleEdit = (dept) => {
        setEditingId(dept.id);
        setFormData({
            name_ru: dept.name_ru || dept.name,
            name_uz: dept.name_uz || '',
            key: dept.key || dept.code,
            description: dept.description || '',
            color: dept.color || '#0066cc',
            icon: dept.icon || '🏥',
            display_order: dept.display_order || 999,
            active: dept.active !== undefined ? dept.active : true
        });
    };

    const handleUpdate = async (id) => {
        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments/${id}`, {
                method: 'PUT',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });

            if (response.ok) {
                toast.success('Отделение обновлено');
                setEditingId(null);
                setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                loadDepartments();
            } else {
                toast.error('Ошибка при обновлении отделения');
            }
        } catch (error) {
            console.error('Error updating department:', error);
            toast.error('Ошибка при обновлении отделения');
        }
    };

    const handleDelete = async (id) => {
        if (!confirm('Вы уверены, что хотите удалить это отделение?')) {
            return;
        }

        try {
            const token = localStorage.getItem('auth_token');
            const response = await fetch(`${API_BASE}/api/v1/admin/departments/${id}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (response.ok) {
                toast.success('Отделение удалено');
                loadDepartments();
            } else {
                toast.error('Ошибка при удалении отделения');
            }
        } catch (error) {
            console.error('Error deleting department:', error);
            toast.error('Ошибка при удалении отделения');
        }
    };

    if (loading) {
        return (
            <Card>
                <div style={{ padding: '40px', textAlign: 'center' }}>
                    <div className="spinner" style={{ margin: '0 auto 16px' }}></div>
                    <p style={{ color: 'var(--mac-text-secondary)' }}>Загрузка отделений...</p>
                </div>
            </Card>
        );
    }

    return (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <Card>
                <div style={{ padding: '24px' }}>
                    <div style={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        marginBottom: '24px'
                    }}>
                        <h2 style={{
                            fontSize: '20px',
                            fontWeight: '600',
                            color: 'var(--mac-text-primary)',
                            margin: 0
                        }}>
                            Управление отделениями
                        </h2>
                        <Button
                            variant="primary"
                            size="default"
                            onClick={() => setShowAddForm(!showAddForm)}
                        >
                            <Plus size={16} style={{ marginRight: '8px' }} />
                            Добавить отделение
                        </Button>
                    </div>

                    {showAddForm && (
                        <div style={{
                            padding: '20px',
                            background: 'var(--mac-bg-tertiary)',
                            borderRadius: 'var(--mac-radius-md)',
                            marginBottom: '24px'
                        }}>
                            <h3 style={{
                                fontSize: '16px',
                                fontWeight: '600',
                                marginBottom: '16px',
                                color: 'var(--mac-text-primary)'
                            }}>
                                Новое отделение
                            </h3>
                            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                                <Input
                                    placeholder="Название (русский)"
                                    value={formData.name_ru}
                                    onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
                                />
                                <Input
                                    placeholder="Название (узбекский)"
                                    value={formData.name_uz}
                                    onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
                                />
                                <Input
                                    placeholder="Ключ (например, cardio)"
                                    value={formData.key}
                                    onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                                    style={{ gridColumn: '1' }}
                                />
                                <Input
                                    type="number"
                                    placeholder="Порядок отображения"
                                    value={formData.display_order}
                                    onChange={(e) => setFormData({ ...formData, display_order: parseInt(e.target.value) })}
                                    style={{ gridColumn: '2' }}
                                />
                                <Input
                                    placeholder="Иконка (emoji)"
                                    value={formData.icon}
                                    onChange={(e) => setFormData({ ...formData, icon: e.target.value })}
                                    style={{ gridColumn: '1' }}
                                />
                                <Input
                                    type="color"
                                    value={formData.color}
                                    onChange={(e) => setFormData({ ...formData, color: e.target.value })}
                                    style={{ gridColumn: '2' }}
                                />
                            </div>
                            <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                                <Button variant="primary" onClick={handleAdd}>
                                    <Save size={16} style={{ marginRight: '8px' }} />
                                    Сохранить
                                </Button>
                                <Button variant="secondary" onClick={() => {
                                    setShowAddForm(false);
                                    setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                                }}>
                                    <X size={16} style={{ marginRight: '8px' }} />
                                    Отмена
                                </Button>
                            </div>
                        </div>
                    )}

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                        {departments.map((dept) => (
                            <div
                                key={dept.id}
                                style={{
                                    padding: '16px',
                                    background: 'var(--mac-bg-secondary)',
                                    border: '1px solid var(--mac-border)',
                                    borderRadius: 'var(--mac-radius-md)',
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'space-between'
                                }}
                            >
                                {editingId === dept.id ? (
                                    <div style={{ flex: 1, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px' }}>
                                        <Input
                                            placeholder="Название (RU)"
                                            value={formData.name_ru}
                                            onChange={(e) => setFormData({ ...formData, name_ru: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Название (UZ)"
                                            value={formData.name_uz}
                                            onChange={(e) => setFormData({ ...formData, name_uz: e.target.value })}
                                        />
                                        <Input
                                            placeholder="Ключ"
                                            value={formData.key}
                                            onChange={(e) => setFormData({ ...formData, key: e.target.value })}
                                        />
                                    </div>
                                ) : (
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1 }}>
                                        <div
                                            style={{
                                                width: '48px',
                                                height: '48px',
                                                borderRadius: 'var(--mac-radius-md)',
                                                background: dept.color || '#0066cc',
                                                display: 'flex',
                                                alignItems: 'center',
                                                justifyContent: 'center',
                                                fontSize: '24px'
                                            }}
                                        >
                                            {dept.icon || '🏥'}
                                        </div>
                                        <div>
                                            <h4 style={{
                                                fontSize: '16px',
                                                fontWeight: '600',
                                                margin: '0 0 4px 0',
                                                color: 'var(--mac-text-primary)'
                                            }}>
                                                {dept.name_ru || dept.name}
                                            </h4>
                                            <Badge variant="secondary">{dept.key || dept.code}</Badge>
                                            {dept.active === false && <Badge variant="danger" style={{ marginLeft: '8px' }}>Неактивно</Badge>}
                                        </div>
                                    </div>
                                )}

                                <div style={{ display: 'flex', gap: '8px' }}>
                                    {editingId === dept.id ? (
                                        <>
                                            <Button
                                                size="sm"
                                                variant="primary"
                                                onClick={() => handleUpdate(dept.id)}
                                            >
                                                <Save size={16} />
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="secondary"
                                                onClick={() => {
                                                    setEditingId(null);
                                                    setFormData({ name_ru: '', name_uz: '', key: '', description: '', color: '#0066cc', icon: '🏥', display_order: 999, active: true });
                                                }}
                                            >
                                                <X size={16} />
                                            </Button>
                                        </>
                                    ) : (
                                        <>
                                            <Button
                                                size="sm"
                                                variant="secondary"
                                                onClick={() => handleEdit(dept)}
                                            >
                                                <Edit2 size={16} />
                                            </Button>
                                            <Button
                                                size="sm"
                                                variant="danger"
                                                onClick={() => handleDelete(dept.id)}
                                            >
                                                <Trash2 size={16} />
                                            </Button>
                                        </>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>

                    {departments.length === 0 && (
                        <div style={{
                            padding: '40px',
                            textAlign: 'center',
                            color: 'var(--mac-text-secondary)'
                        }}>
                            <p>Нет отделений. Добавьте первое отделение.</p>
                        </div>
                    )}
                </div>
            </Card>
        </div>
    );
};

export default DepartmentManagement;
