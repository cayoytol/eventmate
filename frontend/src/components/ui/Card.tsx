import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
    hoverable?: boolean;
}

export const Card: React.FC<CardProps> = ({
    children,
    className = '',
    hoverable = false,
    ...props
}) => {
    return (
        <div
            className={`bg-white border border-neutral-200/80 rounded-2xl p-6 shadow-sm transition-all duration-300 ${
                hoverable ? 'hover:shadow-md hover:border-neutral-300/80 hover:-translate-y-0.5' : ''
            } ${className}`}
            {...props}
        >
            {children}
        </div>
    );
};
