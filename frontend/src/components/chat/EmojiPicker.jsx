import React, { useState, useRef, useEffect } from 'react';
import Picker from '@emoji-mart/react';
import data from '@emoji-mart/data';
import { Smile } from 'lucide-react';

const EmojiPicker = ({ onEmojiSelect, disabled = false }) => {
    const [showPicker, setShowPicker] = useState(false);
    const pickerRef = useRef(null);
    const buttonRef = useRef(null);

    // Close picker when clicking outside
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (
                pickerRef.current &&
                !pickerRef.current.contains(event.target) &&
                buttonRef.current &&
                !buttonRef.current.contains(event.target)
            ) {
                setShowPicker(false);
            }
        };

        if (showPicker) {
            document.addEventListener('mousedown', handleClickOutside);
            return () => document.removeEventListener('mousedown', handleClickOutside);
        }
    }, [showPicker]);

    const handleEmojiSelect = (emoji) => {
        onEmojiSelect(emoji.native);
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

export default EmojiPicker;
