
import React from 'react';
import './Avatar.css';

const roleGradients = {
    admin: 'linear-gradient(135deg, #667eea, #764ba2)',
    doctor: 'linear-gradient(135deg, #11998e, #38ef7d)',
    registrar: 'linear-gradient(135deg, #fc4a1a, #f7b733)',
    patient: 'linear-gradient(135deg, #00c6ff, #0072ff)',
    nurse: 'linear-gradient(135deg, #ff9a9e, #fecfef)',
    default: 'linear-gradient(135deg, #a8c0ff, #3f2b96)'
};

const Avatar = ({ user, size = 40, showStatus = false, isOnline = false, className = '' }) => {
    const role = user?.role?.toLowerCase() || 'default';
    const background = roleGradients[role] || roleGradients.default;
    const name = user?.name || user?.full_name || user?.user_name || '?';
    const initials = (name[0] || '?').toUpperCase();

    return (
        <div className={`avatar-wrapper ${className}`} style={{ width: size, height: size }}>
            <div
                className="avatar-circle"
                style={{
                    background,
                    width: size,
                    height: size,
                    fontSize: Math.max(10, size * 0.4)
                }}
            >
                {initials}
            </div>
            {showStatus && (
                <span className={`avatar-status ${isOnline ? 'online' : 'offline'}`} />
            )}
        </div>
    );
};

export default Avatar;
