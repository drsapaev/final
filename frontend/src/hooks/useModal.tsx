/**
 * Хук-система управления модальными окнами для медицинских интерфейсов.
 *
 * v2.9 follow-up track 2 (Plan-SSOT §4.1.20): мёртвые экспорты этого файла
 * удалены (0 импортёров, machine-verified). Канонический declarative-модал —
 * src/components/ui/macos/Modal.tsx.
 */

import { useState, useCallback } from 'react';

// Хук для управления модальными окнами
export const useModal = (initialOpen = false) => {
  const [isOpen, setIsOpen] = useState(initialOpen);
  const [isAnimating, setIsAnimating] = useState(false);
  const [selectedItem, setSelectedItem] = useState(null);
  const [loading, setLoading] = useState(false);

  const openModal = useCallback((item = null) => {
    setSelectedItem(item);
    setIsOpen(true);
    setIsAnimating(true);
  }, []);

  const closeModal = useCallback(() => {
    setIsAnimating(false);
    setLoading(false);
    setTimeout(() => {
      setIsOpen(false);
      setSelectedItem(null);
    }, 300);
  }, []);

  const toggleModal = useCallback((item = null) => {
    if (isOpen) {
      closeModal();
    } else {
      openModal(item);
    }
  }, [isOpen, openModal, closeModal]);

  const setModalLoading = useCallback((isLoading: boolean) => {
    setLoading(isLoading);
  }, []);

  return {
    isOpen,
    isAnimating,
    selectedItem,
    loading,
    openModal,
    closeModal,
    toggleModal,
    setModalLoading
  };
};

export default useModal;
