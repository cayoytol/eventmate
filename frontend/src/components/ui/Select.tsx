import React, { forwardRef } from 'react';

interface SelectProps extends React.SelectHTMLAttributes<HTMLSelectElement> {
    label?: string;
    error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
    ({ children, label, error, className = '', ...props }, ref) => {
        return (
            <div className="w-full space-y-1">
                {label && (
                    <label className="block text-sm font-semibold text-neutral-700">
                        {label}
                    </label>
                )}
                <div className="relative">
                    <select
                        ref={ref}
                        className={`w-full px-4 py-2.5 bg-white text-slate-900 border rounded-xl text-sm transition-all focus:outline-none focus:ring-2 focus:ring-violet-200 focus:border-violet-600 appearance-none cursor-pointer [&>option]:text-slate-900 [&>option]:bg-white ${
                            error ? 'border-red-500 focus:ring-red-200 focus:border-red-500' : 'border-neutral-200 hover:border-neutral-300'
                        } ${className}`}
                        {...props}
                    >
                        {children}
                    </select>
                    <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-neutral-500">
                        <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">
                            <path d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                        </svg>
                    </div>
                </div>
                {error && (
                    <p className="text-xs text-red-500 font-medium">{error}</p>
                )}
            </div>
        );
    }
);

Select.displayName = 'Select';

