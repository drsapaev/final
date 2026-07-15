/**
 * Компонент воспроизведения голосового сообщения
 */

import { useState, useRef, useEffect } from 'react';
import { Play, Pause } from 'lucide-react';
import auth from '../../stores/auth';
import logger from '../../utils/logger';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/adapter';

const VoiceMessage = ({ message, fileUrl }) => {
  const { t } = useTranslation();
    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(0);
    const [duration, setDuration] = useState(message.voice_duration || 0);
    const [isLoading, setIsLoading] = useState(false);
    const [audioSrc, setAudioSrc] = useState(null);
    const [audioUnavailable, setAudioUnavailable] = useState(false);

    const audioRef = useRef(null);
    const objectUrlRef = useRef(null);

    const loadAudio = async () => {
        if (!fileUrl || audioSrc || isLoading || audioUnavailable) {
            return audioSrc;
        }

        setIsLoading(true);

        try {
            const token = auth.getState().token;
            const response = await fetch(fileUrl, {
                headers: {
                    'Authorization': `Bearer ${token}`
                }
            });

            if (!response.ok) {
                if (response.status === 404 || response.status === 400) {
                    logger.info('[FIX:VOICE] Audio stream unavailable', {
                        messageId: message?.id,
                        status: response.status,
                    });
                    setAudioUnavailable(true);
                    return null;
                }

                throw new Error(`HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const objectUrl = URL.createObjectURL(blob);

            if (objectUrlRef.current) {
                URL.revokeObjectURL(objectUrlRef.current);
            }

            objectUrlRef.current = objectUrl;
            if (audioRef.current) {
                audioRef.current.src = objectUrl;
            }
            setAudioSrc(objectUrl);
            setAudioUnavailable(false);
            return objectUrl;
        } catch (error) {
            logger.error('Failed to load audio:', error);
            setAudioUnavailable(true);
            return null;
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        setAudioSrc(null);
        setAudioUnavailable(false);
        setIsPlaying(false);
        setCurrentTime(0);
        setDuration(message.voice_duration || 0);

        if (objectUrlRef.current) {
            URL.revokeObjectURL(objectUrlRef.current);
            objectUrlRef.current = null;
        }

        return () => {
            if (objectUrlRef.current) {
                URL.revokeObjectURL(objectUrlRef.current);
                objectUrlRef.current = null;
            }
        };
    }, [fileUrl, message.voice_duration]);

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
            logger.warn('[FIX:VOICE] Audio playback failed', {
                messageId: message?.id,
                src: audio.src,
                code: audio.error?.code,
                message: audio.error?.message,
            });
            setAudioUnavailable(true);
            setIsPlaying(false);
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
        if (!audio || audioUnavailable) return;

        try {
            if (isPlaying) {
                audio.pause();
                setIsPlaying(false);
            } else {
                const src = audioSrc || await loadAudio();
                if (!src) {
                    return;
                }
                await audio.play();
                setIsPlaying(true);
            }
        } catch (error) {
            logger.warn('[FIX:VOICE] Playback error', {
                messageId: message?.id,
                error: error?.message || String(error),
            });
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
    const handleSeekKeyDown = (e) => {
        const audio = audioRef.current;
        if (!audio || !duration) return;

        const step = Math.max(duration * 0.05, 1);
        let nextTime = audio.currentTime;

        if (e.key === 'ArrowLeft') {
            e.preventDefault();
            nextTime = Math.max(0, audio.currentTime - step);
        } else if (e.key === 'ArrowRight') {
            e.preventDefault();
            nextTime = Math.min(duration, audio.currentTime + step);
        } else if (e.key === 'Home') {
            e.preventDefault();
            nextTime = 0;
        } else if (e.key === 'End') {
            e.preventDefault();
            nextTime = duration;
        } else {
            return;
        }

        audio.currentTime = nextTime;
        setCurrentTime(nextTime);
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
            <audio
                ref={audioRef}
                src={audioSrc || undefined}
                aria-label="Голосовое сообщение"
                preload="none"
            />

            <button
                onClick={togglePlay}
                className="play-button"
                disabled={isLoading || audioUnavailable || !fileUrl}
                title={audioUnavailable ? 'Аудио недоступно' : (isPlaying ? 'Пауза' : 'Воспроизвести')}
                aria-label={audioUnavailable ? 'Аудио недоступно' : (isPlaying ? 'Поставить голосовое сообщение на паузу' : 'Воспроизвести голосовое сообщение')}
            >
                {isPlaying ? <Pause size={20} /> : <Play size={20} />}
            </button>

            <div className="waveform-container">
                {/* Fake Waveform */}
                <div
                    className="fake-waveform"
                    onClick={handleSeek}
                    role="slider"
                    tabIndex={0}
                    aria-label="Прогресс воспроизведения"
                    aria-valuemin={0}
                    aria-valuemax={Math.round(duration || 0)}
                    aria-valuenow={Math.round(currentTime || 0)}
                    onKeyDown={handleSeekKeyDown}
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


VoiceMessage.propTypes = {
  ...(VoiceMessage.propTypes || {}),
  fileUrl: PropTypes.any,
  message: PropTypes.any,
  voice_duration: PropTypes.any,
};

export default VoiceMessage;
