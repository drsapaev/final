/**
 * EMRHelpDialog - Справка и безопасность
 */const EMRHelpDialog = ({ isOpen, onClose }) => {
    if (!isOpen) return null;
    const handleActivationKeyDown = (event, action) => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            action();
        }
    };

    return (
        <div
            className="emr-v2-modal-overlay"
            role="button"
            tabIndex={0}
            onClick={onClose}
            onKeyDown={(event) => handleActivationKeyDown(event, onClose)}>
            <div className="emr-v2-modal-content theme-soft-surface" onClickCapture={e => e.stopPropagation()} style={{ maxWidth: '600px', borderRadius: '12px' }}>
                <header className="emr-v2-modal-header" style={{ borderBottom: '1px solid var(--mac-border)', paddingBottom: '16px', marginBottom: '16px' }}>
                    <h3 style={{ margin: 0, fontSize: '1.25rem', color: 'var(--mac-accent)' }}>
                        🛡️ AI-ассистент: Важная информация
                    </h3>
                    <button className="emr-v2-btn-close" onClick={onClose}>✕</button>
                </header>

                <div className="emr-v2-modal-body" style={{ lineHeight: 1.6, color: 'var(--mac-text-primary)' }}>
                    <div style={{ marginBottom: '20px', padding: '12px', background: 'var(--mac-accent-bg)', borderRadius: '8px', borderLeft: '4px solid var(--mac-accent)' }}>
                        <strong>Главный принцип:</strong> Искусственный интеллект — это помощник, а не врач.
                        Врач всегда принимает окончательное решение.
                    </div>

                    <ul style={{ paddingLeft: '20px', space: 'y-4' }}>
                        <li style={{ marginBottom: '12px' }}>
                            <strong>🤖 ИИ не пишет в карту сам</strong>
                            <br />
                            Любой текст, который появляется в карте, добавляется только после вашего явного действия (клик, нажатие Enter/Tab).
                            Автоматического заполнения без вашего контроля не происходит.
                        </li>

                        <li style={{ marginBottom: '12px' }}>
                            <strong>✅ Осознанное принятие</strong>
                            <br />
                            Принимая подсказку (AI или из вашей истории), вы подтверждаете, что прочитали её и согласны с содержимым.
                            После сохранения это становится частью юридически значимого документа.
                        </li>

                        <li style={{ marginBottom: '12px' }}>
                            <strong>📜 Ваша история приоритетна</strong>
                            <br />
                            Система обучается на ваших собственных формулировках.
                            Ваши проверенные фразы всегда будут предлагаться раньше, чем общие шаблоны AI.
                        </li>
                    </ul>

                    <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--mac-border)', fontSize: '0.9rem', color: 'var(--mac-text-secondary)' }}>
                        <em>
                            Для включения экспериментального режима «Ghost Mode» (ввод серым текстом)
                            нажмите кнопку 👻 в панели инструментов. Этот режим работает только в неподписанных картах.
                        </em>
                    </div>
                </div>

                <div className="emr-v2-modal-footer" style={{ marginTop: '24px', display: 'flex', justifyContent: 'flex-end' }}>
                    <button className="emr-v2-btn emr-v2-btn--primary" onClick={onClose}>
                        Всё понятно
                    </button>
                </div>
            </div>
        </div>
    );
};

export default EMRHelpDialog;
