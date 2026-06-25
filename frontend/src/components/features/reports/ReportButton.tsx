'use client';

import { useState } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { ENDPOINTS } from '@/lib/api/endpoints';
import { useAuthStore } from '@/store/useAuthStore';
import { ReportContentType, ReportReason } from '@/types/reports';

interface ReportButtonProps {
  contentType: ReportContentType;
  objectId: number;
  variant?: "icon" | "text" | "button";
  disabled?: boolean;
  className?: string;
}

export default function ReportButton({
  contentType,
  objectId,
  variant = "button",
  disabled = false,
  className = "",
}: ReportButtonProps) {
  const t = useTranslations('reports');
  const locale = useLocale();
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const [isOpen, setIsOpen] = useState(false);
  const [reason, setReason] = useState<ReportReason>('spam');
  const [message, setMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const handleOpenModal = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (disabled) return;

    if (!isAuthenticated) {
      const currentUrl = typeof window !== 'undefined' ? window.location.pathname + window.location.search : '';
      router.push(`/${locale}/login/?next=${encodeURIComponent(currentUrl)}`);
      return;
    }

    setIsOpen(true);
    setError(null);
    setSuccess(false);
    setReason('spam');
    setMessage('');
  };

  const handleCloseModal = (e?: React.MouseEvent) => {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    setIsOpen(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    e.stopPropagation();

    if (isSubmitting) return;

    try {
      setIsSubmitting(true);
      setError(null);

      await api.post(ENDPOINTS.REPORTS, {
        content_type: contentType,
        object_id: objectId,
        reason: reason,
        message: message.trim(),
      });

      setSuccess(true);
      setTimeout(() => {
        setIsOpen(false);
        setSuccess(false);
      }, 2000);
    } catch (err: any) {
      console.error('[ReportButton] Submission failed:', err);
      if (err.response?.data) {
        // DRF validation errors can be nested or generic
        const data = err.response.data;
        if (Array.isArray(data)) {
          setError(data[0]);
        } else if (typeof data === 'object') {
          const values = Object.values(data);
          if (values.length > 0) {
            const firstVal: any = values[0];
            if (Array.isArray(firstVal)) {
              setError(firstVal[0]);
            } else if (typeof firstVal === 'string') {
              setError(firstVal);
            } else {
              setError(t('error'));
            }
          } else {
            setError(t('error'));
          }
        } else if (typeof data === 'string') {
          setError(data);
        } else {
          setError(t('error'));
        }
      } else {
        setError(t('error'));
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Flag icon SVG
  const FlagIcon = () => (
    <svg 
      xmlns="http://www.w3.org/2000/svg" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      strokeWidth="2" 
      strokeLinecap="round" 
      strokeLinejoin="round" 
      className="w-4 h-4"
    >
      <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
      <line x1="4" y1="22" x2="4" y2="15" />
    </svg>
  );

  return (
    <>
      {/* Trigger element */}
      {variant === "icon" && (
        <button
          onClick={handleOpenModal}
          disabled={disabled}
          title={t('report')}
          className={`p-1.5 rounded-lg text-neutral-400 hover:text-rose-600 hover:bg-rose-50 transition-all focus:outline-none focus:ring-2 focus:ring-rose-500/20 disabled:opacity-50 ${className}`}
        >
          <FlagIcon />
        </button>
      )}

      {variant === "text" && (
        <button
          onClick={handleOpenModal}
          disabled={disabled}
          className={`inline-flex items-center gap-1 text-xs font-semibold text-neutral-500 hover:text-rose-600 transition-colors disabled:opacity-50 focus:outline-none ${className}`}
        >
          <FlagIcon />
          <span>{t('report')}</span>
        </button>
      )}

      {variant === "button" && (
        <button
          onClick={handleOpenModal}
          disabled={disabled}
          className={`inline-flex items-center justify-center gap-2 px-3 py-1.5 text-xs font-bold border border-neutral-200 rounded-xl text-neutral-600 bg-white hover:text-rose-600 hover:border-rose-200 hover:bg-rose-50 transition-all focus:outline-none focus:ring-2 focus:ring-rose-500/20 disabled:opacity-50 shadow-2xs ${className}`}
        >
          <FlagIcon />
          <span>{t('report')}</span>
        </button>
      )}

      {/* Modal */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-neutral-900/60 backdrop-blur-xs transition-opacity duration-300"
          onClick={() => handleCloseModal()}
        >
          <div
            className="w-full max-w-md bg-white rounded-3xl border border-neutral-100 shadow-2xl p-6 relative overflow-hidden transition-all transform scale-100"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between pb-4 border-b border-neutral-100 mb-5">
              <h3 className="text-lg font-black text-gray-900 flex items-center gap-2">
                <span className="p-1.5 rounded-lg bg-rose-50 text-rose-600">
                  <FlagIcon />
                </span>
                {t('title')}
              </h3>
              <button
                onClick={(e) => handleCloseModal(e)}
                className="p-1 rounded-lg text-neutral-400 hover:bg-neutral-50 hover:text-neutral-600 transition-colors"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Success state */}
            {success ? (
              <div className="py-8 flex flex-col items-center justify-center text-center">
                <div className="w-12 h-12 rounded-full bg-emerald-50 text-emerald-600 flex items-center justify-center mb-4 animate-bounce">
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M5 13l4 4L19 7" />
                  </svg>
                </div>
                <p className="text-emerald-800 font-bold text-sm px-4">
                  {t('success')}
                </p>
              </div>
            ) : (
              /* Report form */
              <form onSubmit={handleSubmit} className="space-y-4">
                {error && (
                  <div className="p-3.5 bg-rose-50 border border-rose-100 rounded-2xl text-xs font-medium text-rose-700 leading-relaxed flex items-start gap-2 animate-shake">
                    <svg className="w-4 h-4 shrink-0 text-rose-500 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <span>{error}</span>
                  </div>
                )}

                <div>
                  <label htmlFor="report-reason" className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                    {t('reasonLabel')}
                  </label>
                  <select
                    id="report-reason"
                    value={reason}
                    onChange={(e) => setReason(e.target.value as ReportReason)}
                    className="w-full rounded-xl border border-neutral-200 bg-neutral-50 px-4 py-3 text-sm focus:bg-white focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 focus:outline-none transition"
                  >
                    <option value="spam">{t('reason.spam')}</option>
                    <option value="fraud">{t('reason.fraud')}</option>
                    <option value="abuse">{t('reason.abuse')}</option>
                    <option value="inappropriate">{t('reason.inappropriate')}</option>
                    <option value="other">{t('reason.other')}</option>
                  </select>
                </div>

                <div>
                  <label htmlFor="report-message" className="block text-xs font-bold text-gray-700 uppercase tracking-wider mb-2">
                    {t('description')}
                  </label>
                  <textarea
                    id="report-message"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    placeholder={t('description')}
                    rows={4}
                    maxLength={1000}
                    className="w-full rounded-xl border border-neutral-200 bg-neutral-50 p-4 text-sm focus:bg-white focus:ring-2 focus:ring-rose-500/20 focus:border-rose-500 focus:outline-none transition resize-none"
                  />
                </div>

                <div className="flex items-center justify-end gap-2.5 pt-4 border-t border-neutral-100">
                  <button
                    type="button"
                    onClick={(e) => handleCloseModal(e)}
                    className="px-4 py-2.5 border border-neutral-200 rounded-xl text-sm font-bold text-neutral-600 hover:bg-neutral-50 transition focus:outline-none"
                  >
                    {t('cancel')}
                  </button>
                  <button
                    type="submit"
                    disabled={isSubmitting}
                    className="inline-flex items-center justify-center min-w-32 px-5 py-2.5 bg-rose-600 text-white rounded-xl text-sm font-bold hover:bg-rose-700 transition disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-rose-500 focus:ring-offset-2"
                  >
                    {isSubmitting ? (
                      <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    ) : (
                      t('submit')
                    )}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
