import React, { forwardRef } from 'react';

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    label?: string;
    error?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
    ({ label, error, className = '', ...props }, ref) => {
        return (
            <div className="w-full space-y-1">
                {label && (
                    <label className="block text-sm font-semibold text-neutral-700">
                        {label}
                    </label>
                )}
                <textarea
                    ref={ref}
                    className={`w-full px-4 py-2.5 bg-white border rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-600 placeholder:text-neutral-400 resize-y ${
                        error ? 'border-red-500 focus:ring-red-200 focus:border-red-500' : 'border-neutral-200 hover:border-neutral-300'
                    } ${className}`}
                    {...props}
                />
                {error && (
                    <p className="text-xs text-red-500 font-medium">{error}</p>
                )}
            </div>
        );
    }
);

Textarea.displayName = 'Textarea';
