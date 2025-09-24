import { useState, useCallback } from 'react';

/**
 * Универсальный хук для управления модальными окнами
 * Устраняет дублирование состояний модальных окон в AdminPanel
 */
export const useModal = (initialState = {}) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(initialState);

  const openModal = useCallback((item = null, additionalData = {}) => {
    setSelectedItem(item);
    setData({ ...initialState, ...additionalData });
    setIsOpen(true);
  }, [initialState]);

  const closeModal = useCallback(() => {
    setIsOpen(false);
    setSelectedItem(null);
    setLoading(false);
    setData(initialState);
  }, [initialState]);

  const setModalLoading = useCallback((loadingState) => {
    setLoading(loadingState);
  }, []);

  const updateData = useCallback((newData) => {
    setData(prev => ({ ...prev, ...newData }));
  }, []);

  return {
    isOpen,
    selectedItem,
    loading,
    data,
    openModal,
    closeModal,
    setModalLoading,
    updateData
  };
};

export default useModal;

