'use client';

import { useState, useEffect } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api';
import { ENDPOINTS, providerBlockUrl, providerUnblockUrl, reportStatusUrl } from '@/lib/api/endpoints';
import { useAuthStore } from '@/store/useAuthStore';
import { Report, ReportStatus, ReportReason } from '@/types/reports';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { StatCard } from '@/components/ui/StatCard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { EmptyState } from '@/components/ui/EmptyState';

export default function AdminReportsPage() {
  const t = useTranslations('admin.reports');
  const tReports = useTranslations('reports');
  const locale = useLocale();
  const router = useRouter();
  const { isAuthenticated, user, isReady } = useAuthStore();

  const [reports, setReports] = useState<Report[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [statusFilter, setStatusFilter] = useState<ReportStatus | 'all'>('all');
  const [reasonFilter, setReasonFilter] = useState<ReportReason | 'all'>('all');

  // Action states
  const [resolutionNotes, setResolutionNotes] = useState<Record<number, string>>({});
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const fetchReports = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.get<any>(ENDPOINTS.REPORTS);
      const responseData = res.data;
      const data = Array.isArray(responseData) ? responseData : (responseData?.results ?? []);
      setReports(data);
    } catch (err: any) {
      console.error('[AdminReports] Failed to fetch reports:', err);
      setError(t('error'));
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (isReady) {
      if (!isAuthenticated) {
        const currentUrl = `/${locale}/admin/reports/`;
        router.push(`/${locale}/login/?next=${encodeURIComponent(currentUrl)}`);
        return;
      }
      if (user?.is_staff !== true && user?.is_superuser !== true) {
        return; // Render forbidden state
      }
      fetchReports();
    }
  }, [isReady, isAuthenticated, user, locale, router]);

  // Auth/Loading states
  const hasAccess = user?.is_staff === true || user?.is_superuser === true;
  if (!isReady || !isAuthenticated || (hasAccess && isLoading && reports.length === 0)) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] py-12">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-violet-600 mb-4"></div>
        <p className="text-slate-500 font-medium">{t('loading')}</p>
      </div>
    );
  }

  if (!hasAccess) {
    return (
      <div className="max-w-xl mx-auto text-center py-16 px-4">
        <div className="h-16 w-16 bg-rose-50 rounded-full flex items-center justify-center mx-auto text-rose-500 mb-4 border border-rose-100">
          <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
        </div>
        <h2 className="text-2xl font-black text-slate-900 mb-2">{t('forbidden')}</h2>
      </div>
    );
  }

  // Handle report actions
  const handleUpdateStatus = async (reportId: number, newStatus: ReportStatus) => {
    if (submittingId) return;
    setSubmittingId(reportId);
    setActionSuccess(null);
    setActionError(null);

    const note = resolutionNotes[reportId] || '';

    try {
      await api.patch(reportStatusUrl(reportId), {
        status: newStatus,
        resolution_note: note,
      });

      // Update reports state locally
      setReports((prev) =>
        prev.map((r) =>
          r.id === reportId
            ? { ...r, status: newStatus, resolution_note: note }
            : r
        )
      );

      // Clear note
      setResolutionNotes((prev) => ({ ...prev, [reportId]: '' }));
      setActionSuccess(t('success'));
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      console.error('[AdminReports] Status update failed:', err);
      setActionError(t('error'));
      setTimeout(() => setActionError(null), 3000);
    } finally {
      setSubmittingId(null);
    }
  };

  const handleProviderBlockAction = async (providerId: number, block: boolean) => {
    if (submittingId) return;
    setSubmittingId(providerId);
    setActionSuccess(null);
    setActionError(null);

    try {
      const url = block ? providerBlockUrl(providerId) : providerUnblockUrl(providerId);
      await api.post(url);
      
      setActionSuccess(t('success'));
      await fetchReports();
      setTimeout(() => setActionSuccess(null), 3000);
    } catch (err: any) {
      console.error('[AdminReports] Provider block/unblock action failed:', err);
      setActionError(t('error'));
      setTimeout(() => setActionError(null), 3000);
    } finally {
      setSubmittingId(null);
    }
  };

  // Stats
  const totalCount = reports.length;
  const openCount = reports.filter((r) => r.status === 'open').length;
  const inReviewCount = reports.filter((r) => r.status === 'in_review').length;
  const resolvedCount = reports.filter((r) => r.status === 'resolved').length;
  const rejectedCount = reports.filter((r) => r.status === 'rejected').length;
  const processedCount = resolvedCount + rejectedCount;

  // Filtering logic
  const filteredReports = reports.filter((r) => {
    const matchesStatus = statusFilter === 'all' || r.status === statusFilter;
    const matchesReason = reasonFilter === 'all' || r.reason === reasonFilter;
    return matchesStatus && matchesReason;
  });

  const getStatusLabel = (status: ReportStatus) => {
    switch (status) {
      case 'open':
        return locale === 'en' ? 'Open' : locale === 'kz' ? 'Ашық' : 'Открыто';
      case 'in_review':
        return locale === 'en' ? 'In Review' : locale === 'kz' ? 'Зерттелуде' : 'В расследовании';
      case 'resolved':
        return locale === 'en' ? 'Resolved' : locale === 'kz' ? 'Қабылданды' : 'Решено';
      case 'rejected':
        return locale === 'en' ? 'Rejected' : locale === 'kz' ? 'Қабылданбады' : 'Отклонено';
      default:
        return status;
    }
  };

  return (
    <div className="space-y-8 max-w-6xl mx-auto">
      {/* Toast Messages */}
      {actionSuccess && (
        <div className="fixed bottom-5 right-5 z-50 p-4 bg-emerald-50 border border-emerald-100 rounded-2xl text-xs font-bold text-emerald-800 shadow-xl flex items-center gap-2 animate-bounce">
          <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
          </svg>
          <span>{actionSuccess}</span>
        </div>
      )}

      {actionError && (
        <div className="fixed bottom-5 right-5 z-50 p-4 bg-rose-50 border border-rose-100 rounded-2xl text-xs font-bold text-rose-800 shadow-xl flex items-center gap-2 animate-shake">
          <svg className="w-4 h-4 text-rose-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>{actionError}</span>
        </div>
      )}

      {/* PageHeader section */}
      <div className="bg-white p-6 sm:p-8 border border-slate-200 rounded-2xl shadow-xs space-y-4">
        <div className="flex items-center gap-3">
          <span className="p-2.5 rounded-2xl bg-violet-50 text-violet-600 border border-violet-100">
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </span>
          <div className="space-y-0.5">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-900 tracking-tight leading-tight">
              {t('title')}
            </h1>
            <p className="text-sm text-slate-500">
              {t('subtitle')}
            </p>
          </div>
        </div>
        <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-xs text-slate-600 leading-relaxed font-semibold">
          {t('workflow')}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title={t('totalQueue') || 'Total Reports'}
          value={totalCount}
          description="total incoming reports"
          icon={
            <svg className="w-6 h-6 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2" />
            </svg>
          }
        />
        <StatCard
          title={t('openQueue') || 'Open Reports'}
          value={openCount}
          description="awaiting initial review"
          icon={
            <svg className="w-6 h-6 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
        <StatCard
          title={t('inReviewQueue') || 'In Review'}
          value={inReviewCount}
          description="currently under review"
          icon={
            <svg className="w-6 h-6 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M8 12h.01M12 12h.01M16 12h.01" />
            </svg>
          }
        />
        <StatCard
          title={t('processedQueue') || 'Processed'}
          value={processedCount}
          description="resolved & rejected total"
          icon={
            <svg className="w-6 h-6 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          }
        />
      </div>

      {/* Toolbar & Filters */}
      <div className="bg-white p-5 border border-slate-200 rounded-2xl shadow-xs space-y-4">
        {/* Status Tabs */}
        <div className="flex flex-wrap gap-2 border-b border-slate-100 pb-4">
          {(['all', 'open', 'in_review', 'resolved', 'rejected'] as const).map((status) => {
            const isActive = statusFilter === status;
            const count = status === 'all' ? totalCount :
                          status === 'open' ? openCount :
                          status === 'in_review' ? inReviewCount :
                          status === 'resolved' ? resolvedCount : rejectedCount;

            const label = status === 'all' ? t('all') : getStatusLabel(status);

            return (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-4 py-2 text-xs font-bold rounded-xl border transition flex items-center gap-2 ${
                  isActive
                    ? 'bg-violet-50 text-violet-700 border-violet-200'
                    : 'bg-white text-slate-600 border-slate-200 hover:bg-slate-50'
                }`}
              >
                <span>{label}</span>
                <span className={`text-[10px] font-black px-1.5 py-0.5 rounded-md ${isActive ? 'bg-violet-200 text-violet-900' : 'bg-slate-100 text-slate-500'}`}>
                  {count}
                </span>
              </button>
            );
          })}
        </div>

        {/* Reason Filter & Info */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">{t('reasonFilter')}:</span>
            <select
              value={reasonFilter}
              onChange={(e) => setReasonFilter(e.target.value as any)}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold focus:outline-none focus:ring-2 focus:ring-violet-500/20"
            >
              <option value="all">{t('all')}</option>
              <option value="spam">{tReports('reason.spam')}</option>
              <option value="fraud">{tReports('reason.fraud')}</option>
              <option value="abuse">{tReports('reason.abuse')}</option>
              <option value="inappropriate">{tReports('reason.inappropriate')}</option>
              <option value="other">{tReports('reason.other')}</option>
            </select>
          </div>
          <span className="text-xs text-slate-500 font-semibold">
            {locale === 'en' ? 'Showing' : locale === 'kz' ? 'Көрсетілуде' : 'Показано'}: <span className="font-extrabold text-slate-900">{filteredReports.length}</span>
          </span>
        </div>
      </div>

      {/* Reports List */}
      {filteredReports.length === 0 ? (
        <EmptyState
          title={t('emptyTitle') || 'Clean Queue'}
          description={t('emptyDescription') || 'No complaints found matching selected filters.'}
        />
      ) : (
        <div className="grid grid-cols-1 gap-6">
          {filteredReports.map((report) => {
            const isPending = submittingId === report.id;
            const isBlockedTarget = report.content_type === 'provider';

            const getStatusLabelText = (status: ReportStatus) => {
              return getStatusLabel(status);
            };

            return (
              <Card
                key={report.id}
                className="p-6 sm:p-8 border border-slate-200 rounded-2xl bg-white hover:shadow-md transition duration-200 relative overflow-hidden"
              >
                {/* Status indicator line */}
                <div className={`absolute top-0 left-0 w-1.5 h-full ${
                  report.status === 'open' ? 'bg-sky-500' :
                  report.status === 'in_review' ? 'bg-amber-500' :
                  report.status === 'resolved' ? 'bg-emerald-500' : 'bg-slate-300'
                }`} />

                {/* Top header line */}
                <div className="flex flex-wrap items-center justify-between gap-3 mb-5 border-b border-slate-100 pb-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs font-extrabold text-slate-400">Report #{report.id}</span>
                    <StatusBadge
                      status={report.status}
                      label={getStatusLabelText(report.status)}
                    />
                    <StatusBadge
                      status={report.reason === 'fraud' || report.reason === 'abuse' ? 'disputed' : 'cancelled'}
                      label={tReports(`reason.${report.reason}`)}
                    />
                  </div>
                  <span className="text-xs font-semibold text-slate-500">
                    {new Date(report.created_at).toLocaleString(locale)}
                  </span>
                </div>

                {/* Grid details */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
                  {/* Left Column: Core Fields */}
                  <div className="space-y-4">
                    <div>
                      <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">{t('reporter')}</span>
                      <span className="text-xs font-extrabold text-slate-900 truncate block" title={report.reporter_email}>
                        {report.reporter_email}
                      </span>
                    </div>
                    <div>
                      <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">{t('object')}</span>
                      <span className="text-xs font-bold text-slate-800 uppercase bg-slate-50 border border-slate-100 px-2 py-0.5 rounded-md">
                        {report.content_type} (ID: {report.object_id})
                      </span>
                    </div>
                  </div>

                  {/* Middle Column: Summary & Info */}
                  <div className="space-y-4">
                    <div>
                      <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">{t('objectSummary')}</span>
                      <span className="text-xs font-semibold text-slate-700 leading-relaxed block">
                        {report.object_summary || '—'}
                      </span>
                    </div>
                    <div>
                      <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">{t('objectMissing')}</span>
                      <span className={`inline-flex items-center px-2 py-0.5 rounded-lg text-2xs font-extrabold ${
                        report.object_missing ? 'bg-rose-50 text-rose-700 border border-rose-100' : 'bg-slate-50 text-slate-600 border border-slate-200'
                      }`}>
                        {report.object_missing ? t('yes') : t('no')}
                      </span>
                    </div>
                  </div>

                  {/* Right Column: Complaint Message */}
                  <div>
                    <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-1">{t('message')}</span>
                    <blockquote className="bg-slate-50 border-l-4 border-violet-500 p-4 rounded-r-xl font-medium text-xs text-slate-600 italic whitespace-pre-wrap leading-relaxed">
                      {report.message || <span className="italic text-slate-500">No message provided</span>}
                    </blockquote>
                  </div>
                </div>

                {/* Resolution note display / input */}
                <div className="border-t border-slate-100 pt-5 flex flex-col md:flex-row md:items-end justify-between gap-5">
                  <div className="flex-1 max-w-xl">
                    {report.status === 'resolved' || report.status === 'rejected' ? (
                      <div className="space-y-1.5">
                        <span className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">Resolution Note</span>
                        <p className="text-xs italic text-slate-600 bg-slate-50/50 border border-slate-200 p-4 rounded-xl font-medium">
                          {report.resolution_note || 'No resolution note provided'}
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        <label htmlFor={`res-note-${report.id}`} className="block text-[10px] font-bold uppercase tracking-wider text-slate-400">
                          {t('resolutionNote')}
                        </label>
                        <textarea
                          id={`res-note-${report.id}`}
                          value={resolutionNotes[report.id] || ''}
                          onChange={(e) => setResolutionNotes((prev) => ({ ...prev, [report.id]: e.target.value }))}
                          placeholder={t('resolutionNotePlaceholder')}
                          rows={2}
                          className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3.5 text-xs font-semibold focus:bg-white focus:ring-2 focus:ring-violet-500/20 focus:border-violet-500 focus:outline-none transition resize-none"
                        />
                      </div>
                    )}
                  </div>

                  {/* Actions buttons panel */}
                  <div className="flex flex-wrap items-center gap-2 shrink-0">
                    {/* Status Mod Buttons */}
                    {report.status === 'open' && (
                      <Button
                        onClick={() => handleUpdateStatus(report.id, 'in_review')}
                        disabled={isPending}
                        className="bg-amber-500 hover:bg-amber-600 text-white font-extrabold text-xs py-2.5 px-4 rounded-xl focus:ring-2 focus:ring-amber-500 focus:ring-offset-2"
                      >
                        {t('markInReview')}
                      </Button>
                    )}

                    {(report.status === 'open' || report.status === 'in_review') && (
                      <>
                        <Button
                          onClick={() => handleUpdateStatus(report.id, 'resolved')}
                          disabled={isPending}
                          className="bg-emerald-600 hover:bg-emerald-700 text-white font-extrabold text-xs py-2.5 px-4 rounded-xl focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2"
                        >
                          {t('resolve')}
                        </Button>
                        <Button
                          onClick={() => handleUpdateStatus(report.id, 'rejected')}
                          disabled={isPending}
                          className="bg-rose-600 hover:bg-rose-700 text-white font-extrabold text-xs py-2.5 px-4 rounded-xl focus:ring-2 focus:ring-rose-500 focus:ring-offset-2"
                        >
                          {t('reject')}
                        </Button>
                      </>
                    )}

                    {/* Block Provider action */}
                    {isBlockedTarget && (
                      <div className="bg-rose-50 border border-rose-100 p-4 rounded-xl space-y-2 flex flex-col">
                        <span className="block text-[10px] font-bold uppercase tracking-wider text-rose-800">
                          {t('criticalAction') || 'Critical Moderation Action'}
                        </span>
                        <div className="flex gap-2">
                          <Button
                            onClick={() => handleProviderBlockAction(report.object_id, true)}
                            disabled={isPending}
                            className="bg-rose-600 hover:bg-rose-700 text-white font-bold rounded-xl text-xs py-2 px-3.5 focus:ring-2 focus:ring-rose-500 focus:ring-offset-2"
                          >
                            {t('providerBlock')}
                          </Button>
                          <Button
                            onClick={() => handleProviderBlockAction(report.object_id, false)}
                            disabled={isPending}
                            className="border border-rose-200 text-rose-700 bg-white hover:bg-rose-50 font-bold rounded-xl text-xs py-2 px-3.5 focus:ring-2 focus:ring-rose-500 focus:ring-offset-2"
                          >
                            {t('providerUnblock')}
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
