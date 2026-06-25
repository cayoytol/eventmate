import React from 'react';

interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
    variant?: 'text' | 'circular' | 'rectangular';
}

export const Skeleton: React.FC<SkeletonProps> = ({
    variant = 'rectangular',
    className = '',
    ...props
}) => {
    const baseClass = 'animate-pulse bg-neutral-200';
    
    const variants = {
        text: 'h-4 w-full rounded',
        circular: 'rounded-full',
        rectangular: 'rounded-2xl',
    };

    return (
        <div
            className={`${baseClass} ${variants[variant]} ${className}`}
            {...props}
        />
    );
};
