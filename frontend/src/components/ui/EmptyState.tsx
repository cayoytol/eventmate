import React from 'react';

interface EmptyStateProps {
    title: string;
    description?: string;
    icon?: React.ReactNode;
    action?: React.ReactNode;
    className?: string;
}

export const EmptyState: React.FC<EmptyStateProps> = ({
    title,
    description,
    icon,
    action,
    className = '',
}) => {
    return (
        <div className={`flex flex-col items-center justify-center text-center p-8 border border-neutral-150 border-dashed rounded-3xl bg-neutral-50/50 ${className}`}>
            {icon ? (
                <div className="text-neutral-400 mb-4">{icon}</div>
            ) : (
                <div className="w-16 h-16 bg-neutral-50 rounded-full flex items-center justify-center border border-neutral-100 text-neutral-400 mb-4">
                    <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0a2 2 0 01-2 2H6a2 2 0 01-2-2m16 0V9a2 2 0 00-2-2M4 13v6a2 2 0 002 2h12a2 2 0 002-2v-6" />
                    </svg>
                </div>
            )}
            <h3 className="text-lg font-bold text-neutral-900 mb-1">{title}</h3>
            {description && (
                <p className="text-sm text-neutral-500 max-w-sm mb-6 leading-relaxed">
                    {description}
                </p>
            )}
            {action && <div>{action}</div>}
        </div>
    );
};
