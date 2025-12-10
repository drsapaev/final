/**
 * Компонент воспроизведения голосового сообщения
 */

import React, { useState, useRef, useEffect } from 'react';
import { Play, Pause } from 'lucide-react';
import auth from '../../stores/auth';

const VoiceMessage = ({ message, fileUrl }) => {
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(message.voice_duration || 0);
    const [isLoading, setIsLoading] = useState(true);
    const [audioSrc, setAudioSrc] = useState(null);

    const audioRef = useRef(null);

    // Загружаем аудио с авторизацией
    useEffect(() => {
        const loadAudio = async () => {
            if (!fileUrl) return;

            try {
                const token = auth.getState().token;
                const response = await fetch(fileUrl, {
                    headers: {
                        'Authorization': `Bearer ${token}`
                    }
                });

                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}`);
                }

                const blob = await response.blob();
                const url = URL.createObjectURL(blob);
                setAudioSrc(url);
            } catch (error) {
                console.error('Failed to load audio:', error);
                setIsLoading(false);
            }
        };

        loadAudio();

        // Cleanup
        return () => {
            if (audioSrc) {
                URL.revokeObjectURL(audioSrc);
            }
        };
    }, [fileUrl]);

    useEffect(() => {
        const audio = audioRef.current;
        if (!audio) return;

        const updateTime = () => setCurrentTime(audio.currentTime);
        const handleEnded = () => setIsPlaying(false);
        const handleLoadedMetadata = () => {
            setDuration(audio.duration);
            setIsLoading(false);
        };
        const handleCanPlay = () => setIsLoading(false);
        const handleError = (e) => {
            console.error('Audio playback error:', e);
            console.error('Audio src:', audio.src);
            console.error('Audio error code:', audio.error?.code);
            console.error('Audio error message:', audio.error?.message);
            setIsLoading(false);
        };

        audio.addEventListener('timeupdate', updateTime);
        audio.addEventListener('ended', handleEnded);
        audio.addEventListener('loadedmetadata', handleLoadedMetadata);
        audio.addEventListener('canplay', handleCanPlay);
        audio.addEventListener('error', handleError);

        return () => {
            audio.removeEventListener('timeupdate', updateTime);
            audio.removeEventListener('ended', handleEnded);
            audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
            audio.removeEventListener('canplay', handleCanPlay);
            audio.removeEventListener('error', handleError);
        };
    }, [audioSrc]);

    const togglePlay = async () => {
        const audio = audioRef.current;
        if (!audio || !audioSrc) return;

        try {
            if (isPlaying) {
                audio.pause();
                setIsPlaying(false);
            } else {
                await audio.play();
                setIsPlaying(true);
            }
        } catch (error) {
            console.error('Playback error:', error);
            alert('Ошибка воспроизведения: ' + error.message);
            setIsPlaying(false);
        }
    };

    const handleSeek = (e) => {
        const audio = audioRef.current;
        if (!audio || !duration) return;

        const rect = e.currentTarget.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const percentage = x / rect.width;
        const newTime = percentage * duration;

        audio.currentTime = newTime;
        setCurrentTime(newTime);
    };

    const formatTime = (seconds) => {
        if (!seconds || isNaN(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    };

    const progress = duration > 0 ? (currentTime / duration) * 100 : 0;

    return (
        <div className="voice-message">
            {audioSrc && (
                <audio
                    ref={audioRef}
                    src={audioSrc}
                    preload="metadata"
                />
            )}

            <button
                onClick={togglePlay}
                className="play-button"
                disabled={isLoading || !audioSrc}
                title={isPlaying ? 'Пауза' : 'Воспроизвести'}
            >
                {isPlaying ? <Pause size={20} /> : <Play size={20} />}
            </button>

            <div className="waveform-container">
                {/* Fake Waveform */}
                <div
                    className="fake-waveform"
                    onClick={handleSeek}
                    role="slider"
                    aria-label="Прогресс воспроизведения"
                >
                    {[30, 50, 35, 70, 50, 80, 60, 40, 70, 45, 80, 55, 30, 60, 40, 70, 50, 30, 60, 40, 50, 70, 45, 30, 60, 80, 40, 20, 50, 35].map((height, i, arr) => {
                        const barProgress = (i / arr.length) * 100;
                        const isFilled = barProgress < progress;
                        return (
                            <div
                                key={i}
                                className={`wave-bar ${isFilled ? 'filled' : ''}`}
                                style={{ height: `${height}%` }}
                            />
                        );
                    })}
                </div>
                <div className="time-display">
                    <span className="current-time">{formatTime(currentTime)}</span>
                    <span className="separator">/</span>
                    <span className="total-time">{formatTime(duration)}</span>
                </div>
            </div>
        </div>
    );
};

export default VoiceMessage;
