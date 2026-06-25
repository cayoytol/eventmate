import React from 'react';
import { Badge } from './Badge';

type StatusType = 'open' | 'offers' | 'confirmed' | 'in_progress' | 'completed' | 'cancelled' | 'disputed' | string;

interface StatusBadgeProps {
    status: StatusType;
    label: string;
    className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({
    status,
    label,
    className = '',
}) => {
    const getVariant = (statusVal: StatusType): 'default' | 'success' | 'warning' | 'error' | 'info' | 'violet' => {
        const normalized = statusVal.toLowerCase();
        switch (normalized) {
            case 'open':
                return 'info';
            case 'offers':
            case 'in_progress':
                return 'warning';
            case 'confirmed':
            case 'completed':
                return 'success';
            case 'cancelled':
                return 'default';
            case 'disputed':
                return 'error';
            default:
                return 'default';
        }
    };

    return (
        <Badge
            variant={getVariant(status)}
            className={className}
        >
            {label}
        </Badge>
    );
};
