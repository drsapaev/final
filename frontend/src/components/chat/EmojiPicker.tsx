import { useState, useRef, useEffect } from 'react';
import Picker from '@emoji-mart/react';
import data from '@emoji-mart/data';
import { Smile } from 'lucide-react';
import { useTranslation } from '../../i18n/useTranslation';

interface EmojiPickerProps {
  onEmojiSelect: (emoji: string) => void;
  disabled?: boolean;
}

interface EmojiData {
  native?: string;
  [key: string]: unknown;
}

const EmojiPicker = ({ onEmojiSelect, disabled = false }: EmojiPickerProps) => {
  const { t } = useTranslation();
    const [showPicker, setShowPicker] = useState(false);
    const pickerRef = useRef<HTMLDivElement | null>(null);
    const buttonRef = useRef<HTMLButtonElement | null>(null);

    // Close picker when clicking outside
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (
                pickerRef.current &&
                !pickerRef.current.contains(event.target as Node) &&
                buttonRef.current &&
                !buttonRef.current.contains(event.target as Node)
            ) {
                setShowPicker(false);
            }
        };

        if (showPicker) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showPicker]);

    const handleEmojiSelect = (emoji: unknown) => {
        const emojiData = emoji as EmojiData;
        onEmojiSelect(emojiData.native || '');
        setShowPicker(false);
    };

    return (
        <div className="emoji-picker-container">
            <button
                ref={buttonRef}
                type="button"
                onClick={() => setShowPicker(!showPicker)}
                className="emoji-trigger-btn"
                disabled={disabled}
                title="Добавить эмодзи"
                aria-label="Добавить эмодзи"
            >
                <Smile size={18} />
            </button>

            {showPicker && (
                <div ref={pickerRef} className="emoji-picker-dropdown">
                    <Picker
                        data={data}
                        onEmojiSelect={handleEmojiSelect}
                        theme="auto"
                        locale="ru"
                        previewPosition="none"
                        skinTonePosition="search"
                        perLine={8}
                        emojiSize={24}
                        emojiButtonSize={32}
                        maxFrequentRows={2}
                    />
                </div>
            )}
        </div>
    );
};


// audit/strict: removed self-referencing propTypes spread

export default EmojiPicker;
