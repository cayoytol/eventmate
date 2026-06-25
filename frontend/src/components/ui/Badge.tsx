import React from 'react';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
    variant?: 'default' | 'success' | 'warning' | 'error' | 'info' | 'violet';
}

export const Badge: React.FC<BadgeProps> = ({
    children,
    variant = 'default',
    className = '',
    ...props
}) => {
    const baseStyle = 'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border transition-colors';

    const variants = {
        default: 'bg-neutral-100 text-neutral-800 border-neutral-200',
        success: 'bg-emerald-50 text-emerald-700 border-emerald-200',
        warning: 'bg-amber-50 text-amber-700 border-amber-200',
        error: 'bg-rose-50 text-rose-700 border-rose-200',
        info: 'bg-sky-50 text-sky-700 border-sky-200',
        violet: 'bg-violet-50 text-violet-700 border-violet-200',
    };

    return (
        <span
            className={`${baseStyle} ${variants[variant]} ${className}`}
            {...props}
        >
            {children}
        </span>
    );
};
