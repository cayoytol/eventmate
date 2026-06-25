import React from 'react';
import { Card } from './Card';

interface StatCardProps {
    title: string;
    value: string | number;
    description?: string;
    icon?: React.ReactNode;
    trend?: {
        value: string | number;
        direction: 'up' | 'down';
    };
    className?: string;
}

export const StatCard: React.FC<StatCardProps> = ({
    title,
    value,
    description,
    icon,
    trend,
    className = '',
}) => {
    return (
        <Card className={`relative overflow-hidden ${className}`}>
            <div className="flex justify-between items-start">
                <div className="space-y-2">
                    <p className="text-xs font-bold uppercase tracking-wider text-neutral-400">
                        {title}
                    </p>
                    <h4 className="text-3xl font-black tracking-tight text-neutral-900">
                        {value}
                    </h4>
                </div>
                {icon && (
                    <div className="p-3 bg-violet-50 text-violet-600 rounded-xl">
                        {icon}
                    </div>
                )}
            </div>

            {(description || trend) && (
                <div className="mt-4 flex items-center gap-2 text-sm text-neutral-500">
                    {trend && (
                        <span className={`inline-flex items-center font-bold ${
                            trend.direction === 'up' ? 'text-emerald-600' : 'text-rose-600'
                        }`}>
                            {trend.direction === 'up' ? '↑' : '↓'} {trend.value}
                        </span>
                    )}
                    {description && <span>{description}</span>}
                </div>
            )}
        </Card>
    );
};
