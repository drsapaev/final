/**
 * Компонент записи голосовых сообщений
 */

import React, { useState, useRef, useEffect } from 'react';
import { Mic, Square, Send, Trash2 } from 'lucide-react';

const VoiceRecorder = ({ onSend, onCancel }) => {
    const [isRecording, setIsRecording] = useState(false);
    const [audioBlob, setAudioBlob] = useState(null);
    const [duration, setDuration] = useState(0);
    const [audioURL, setAudioURL] = useState(null);

    const mediaRecorderRef = useRef(null);
    const chunksRef = useRef([]);
    const timerRef = useRef(null);
    const streamRef = useRef(null);

    // Начать запись
    const startRecording = async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    echoCancellation: true,
                    noiseSuppression: true,
                    autoGainControl: true
                }
            });

            streamRef.current = stream;

            // Определяем поддерживаемый MIME type
            const mimeType = getSupportedMimeType();

            const mediaRecorder = new MediaRecorder(stream, { mimeType });

            mediaRecorderRef.current = mediaRecorder;
            chunksRef.current = [];

            mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) {
                    chunksRef.current.push(e.data);
                }
            };

            mediaRecorder.onstop = () => {
                const blob = new Blob(chunksRef.current, { type: mimeType });
                setAudioBlob(blob);
                setAudioURL(URL.createObjectURL(blob));

                // Остановить поток
                if (streamRef.current) {
                    streamRef.current.getTracks().forEach(track => track.stop());
                    streamRef.current = null;
                }
            };

            mediaRecorder.start();
            setIsRecording(true);

            // Таймер
            timerRef.current = setInterval(() => {
                setDuration(prev => {
                    if (prev >= 300) {  // Макс 5 минут
                        stopRecording();
                        return 300;
                    }
                    return prev + 1;
                });
            }, 1000);

        } catch (error) {
            console.error('Microphone access denied:', error);
            alert('Разрешите доступ к микрофону в настройках браузера');
        }
    };

    // Остановить запись
    const stopRecording = () => {
        if (mediaRecorderRef.current && isRecording) {
            mediaRecorderRef.current.stop();
            setIsRecording(false);
            clearInterval(timerRef.current);
        }
    };

    // Отправить
    const handleSend = () => {
        if (audioBlob) {
            onSend(audioBlob, duration);
            reset();
        }
    };

    // Отменить
    const handleCancel = () => {
        reset();
        onCancel();
    };

    // Сброс
    const reset = () => {
        if (audioURL) {
            URL.revokeObjectURL(audioURL);
        }
        setAudioBlob(null);
        setAudioURL(null);
        setDuration(0);
        setIsRecording(false);
        clearInterval(timerRef.current);

        // Остановить поток если активен
        if (streamRef.current) {
            streamRef.current.getTracks().forEach(track => track.stop());
            streamRef.current = null;
        }
    };

    // Cleanup on unmount
    useEffect(() => {
        return () => {
            reset();
        };
    }, []);

    // Форматирование времени
    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = seconds % 60;
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    // Определить поддерживаемый MIME type
    const getSupportedMimeType = () => {
        const types = [
            'audio/webm;codecs=opus',
            'audio/ogg;codecs=opus',
            'audio/webm',
            'audio/ogg',
            'audio/mp4'
        ];

        for (const type of types) {
            if (MediaRecorder.isTypeSupported(type)) {
                return type;
            }
        }

        return 'audio/webm';  // Fallback
    };

    return (
        <div className="voice-recorder">
            {!audioBlob ? (
                // Режим записи
                <div className="recording-controls">
                    {!isRecording ? (
                        <button
                            onClick={startRecording}
                            className="btn-record"
                            title="Записать голосовое сообщение"
                        >
                            <Mic size={20} />
                            <span>Записать голосовое</span>
                        </button>
                    ) : (
                        <div className="recording-active">
                            <div className="recording-indicator">
                                <div className="pulse-dot" />
                                <span className="recording-time">{formatTime(duration)}</span>
                            </div>
                            <button onClick={stopRecording} className="btn-stop">
                                <Square size={18} />
                                <span>Остановить</span>
                            </button>
                        </div>
                    )}
                </div>
            ) : (
                // Режим предпросмотра
                <div className="recording-preview">
                    <audio src={audioURL} controls className="audio-preview" />
                    <span className="duration-label">{formatTime(duration)}</span>

                    <div className="preview-actions">
                        <button onClick={handleCancel} className="btn-cancel" title="Отменить">
                            <Trash2 size={18} />
                        </button>
                        <button onClick={handleSend} className="btn-send" title="Отправить">
                            <Send size={18} />
                            <span>Отправить</span>
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default VoiceRecorder;
