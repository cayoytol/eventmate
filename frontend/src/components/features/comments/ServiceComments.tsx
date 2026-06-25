'use client';

import { useState, useEffect } from 'react';
import { useTranslations, useLocale } from 'next-intl';
import Link from 'next/link';
import { api } from '@/lib/api';
import { serviceCommentsUrl, commentUrl } from '@/lib/api/endpoints';
import { useAuthStore } from '@/store/useAuthStore';
import { ServiceComment } from '@/types/comments';
import { PaginatedResponse } from '@/types/catalog';
import ReportButton from '@/components/features/reports/ReportButton';

function formatSafeDate(value?: string | null) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString();
}

interface ServiceCommentsProps {
  serviceId: number;
  providerId?: number;
}

export default function ServiceComments({ serviceId, providerId }: ServiceCommentsProps) {
  const t = useTranslations('comments');
  const locale = useLocale();
  const { isAuthenticated, user } = useAuthStore();

  const [comments, setComments] = useState<ServiceComment[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isError, setIsError] = useState(false);

  // Form states
  const [newCommentText, setNewCommentText] = useState('');
  const [replyingCommentId, setReplyingCommentId] = useState<number | null>(null);
  const [replyText, setReplyText] = useState('');
  const [editingCommentId, setEditingCommentId] = useState<number | null>(null);
  const [editText, setEditText] = useState('');
  
  const [isSubmitting, setIsSubmitting] = useState(false);

  const fetchComments = async () => {
    setIsLoading(true);
    setIsError(false);
    try {
      const res = await api.get<PaginatedResponse<ServiceComment> | ServiceComment[]>(
        serviceCommentsUrl(serviceId)
      );
      const data = Array.isArray(res.data) ? res.data : res.data.results || [];
      setComments(data);
    } catch (err) {
      console.error('[ServiceComments] Failed to fetch comments:', err);
      setIsError(true);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    if (serviceId) {
      fetchComments();
    }
  }, [serviceId]);

  const handlePostComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newCommentText.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const { data } = await api.post<ServiceComment>(serviceCommentsUrl(serviceId), {
        text: newCommentText.trim(),
      });
      setComments((prev) => [...prev, { ...data, replies: [] }]);
      setNewCommentText('');
    } catch (err) {
      console.error('[ServiceComments] Failed to post comment:', err);
      alert(t('error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handlePostReply = async (e: React.FormEvent, parentId: number) => {
    e.preventDefault();
    if (!replyText.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const { data } = await api.post<ServiceComment>(serviceCommentsUrl(serviceId), {
        text: replyText.trim(),
        parent: parentId,
      });

      setComments((prev) =>
        prev.map((c) => {
          if (c.id === parentId) {
            return {
              ...c,
              replies: [...(c.replies || []), data],
            };
          }
          return c;
        })
      );
      setReplyText('');
      setReplyingCommentId(null);
    } catch (err) {
      console.error('[ServiceComments] Failed to post reply:', err);
      alert(t('error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEditComment = async (e: React.FormEvent, commentId: number, isReply: boolean, parentId?: number) => {
    e.preventDefault();
    if (!editText.trim() || isSubmitting) return;

    setIsSubmitting(true);
    try {
      const { data } = await api.patch<ServiceComment>(commentUrl(commentId), {
        text: editText.trim(),
      });

      if (isReply && parentId) {
        setComments((prev) =>
          prev.map((c) => {
            if (c.id === parentId) {
              return {
                ...c,
                replies: (c.replies || []).map((r) => (r.id === commentId ? { ...r, text: data.text, updated_at: data.updated_at } : r)),
              };
            }
            return c;
          })
        );
      } else {
        setComments((prev) =>
          prev.map((c) => (c.id === commentId ? { ...c, text: data.text, updated_at: data.updated_at } : c))
        );
      }

      setEditingCommentId(null);
      setEditText('');
    } catch (err) {
      console.error('[ServiceComments] Failed to edit comment:', err);
      alert(t('error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteComment = async (commentId: number, isReply: boolean, parentId?: number) => {
    if (isSubmitting) return;

    setIsSubmitting(true);
    try {
      await api.delete(commentUrl(commentId));

      // Soft delete updates on frontend state
      if (isReply && parentId) {
        setComments((prev) =>
          prev.map((c) => {
            if (c.id === parentId) {
              return {
                ...c,
                replies: (c.replies || []).map((r) => (r.id === commentId ? { ...r, is_deleted: true, text: '[deleted]' } : r)),
              };
            }
            return c;
          })
        );
      } else {
        setComments((prev) =>
          prev.map((c) => (c.id === commentId ? { ...c, is_deleted: true, text: '[deleted]' } : c))
        );
      }
    } catch (err) {
      console.error('[ServiceComments] Failed to delete comment:', err);
      alert(t('error'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const startEditing = (commentId: number, currentText: string) => {
    setEditingCommentId(commentId);
    setEditText(currentText);
    setReplyingCommentId(null);
  };

  const startReplying = (commentId: number) => {
    setReplyingCommentId(commentId);
    setReplyText('');
    setEditingCommentId(null);
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-10">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-violet-600 mb-2"></div>
        <p className="text-sm text-gray-500">{t('loading')}</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="text-center py-10 bg-red-50 rounded-2xl border border-red-200">
        <p className="text-red-800 font-medium">{t('error')}</p>
        <button
          onClick={fetchComments}
          className="mt-4 px-4 py-2 bg-red-600 text-white rounded-xl text-sm font-semibold hover:bg-red-700 transition"
        >
          {t('submit')}
        </button>
      </div>
    );
  }

  const isProviderOwner = isAuthenticated && user?.provider_profile_id === providerId;

  return (
    <div className="bg-white rounded-2xl border p-6 shadow-xs mt-8">
      <h2 className="text-2xl font-black text-gray-900 mb-6">{t('title')}</h2>

      {/* List of comments */}
      {comments.length === 0 ? (
        <div className="text-center py-8 bg-neutral-50 rounded-xl border border-dashed text-gray-500 text-sm mb-6">
          {t('empty')}
        </div>
      ) : (
        <div className="space-y-6 mb-8">
          {comments.map((comment) => {
            const commentReplies = comment.replies || [];
            const isEditing = editingCommentId === comment.id;
            const isReplying = replyingCommentId === comment.id;

            return (
              <div key={comment.id} className="border-b border-neutral-100 pb-6 last:border-0 last:pb-0">
                {/* Parent comment */}
                <div className="flex items-start gap-3">
                  <div className="h-10 w-10 rounded-full bg-neutral-100 flex items-center justify-center text-neutral-600 font-bold shrink-0">
                    {comment.username?.[0]?.toUpperCase() || 'U'}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <span className="font-bold text-gray-900 text-sm truncate">{comment.username}</span>
                      <span className="text-2xs text-gray-400">
                        {formatSafeDate(comment.created_at)}
                      </span>
                    </div>

                    {isEditing ? (
                      <form onSubmit={(e) => handleEditComment(e, comment.id, false)} className="mt-2">
                        <textarea
                          value={editText}
                          onChange={(e) => setEditText(e.target.value)}
                          className="w-full rounded-xl border p-3 text-sm focus:ring-2 focus:ring-violet-500 focus:outline-none"
                          rows={3}
                          required
                        />
                        <div className="flex gap-2 justify-end mt-2">
                          <button
                            type="button"
                            onClick={() => setEditingCommentId(null)}
                            className="px-3 py-1.5 border rounded-lg text-xs font-semibold text-gray-600 hover:bg-neutral-50 transition"
                          >
                            {t('cancel')}
                          </button>
                          <button
                            type="submit"
                            disabled={isSubmitting}
                            className="px-3 py-1.5 bg-violet-600 text-white rounded-lg text-xs font-semibold hover:bg-violet-700 transition"
                          >
                            {t('save')}
                          </button>
                        </div>
                      </form>
                    ) : (
                      <>
                        <p className={`text-sm text-gray-700 leading-relaxed ${comment.is_deleted ? 'italic text-gray-400' : ''}`}>
                          {comment.text}
                        </p>

                        {/* Actions */}
                        <div className="flex items-center gap-4 mt-2">
                          {/* Reply trigger (only for root and provider owner) */}
                          {comment.can_reply && (
                            <button
                              onClick={() => startReplying(comment.id)}
                              className="text-xs font-semibold text-violet-600 hover:text-violet-800"
                            >
                              {t('reply')}
                            </button>
                          )}

                          {/* Edit / Delete triggers */}
                          {comment.can_edit && (
                            <>
                              <button
                                onClick={() => startEditing(comment.id, comment.text)}
                                className="text-xs font-semibold text-neutral-500 hover:text-neutral-700"
                              >
                                {t('edit')}
                              </button>
                              <button
                                onClick={() => handleDeleteComment(comment.id, false)}
                                className="text-xs font-semibold text-red-500 hover:text-red-700"
                              >
                                {t('delete')}
                              </button>
                            </>
                          )}

                          {/* Report trigger */}
                          {!comment.is_deleted && (!isAuthenticated || (user && comment.user !== user.id)) && (
                            <ReportButton
                              contentType="comment"
                              objectId={comment.id}
                              variant="text"
                              className="text-neutral-400 hover:text-rose-600"
                            />
                          )}
                        </div>
                      </>
                    )}

                    {/* Nested replies */}
                    {commentReplies.length > 0 && (
                      <div className="mt-4 ml-6 pl-4 border-l-2 border-neutral-100 space-y-4">
                        {commentReplies.map((reply) => {
                          const isReplyEditing = editingCommentId === reply.id;
                          return (
                            <div key={reply.id} className="flex items-start gap-2.5">
                              <div className="h-8 w-8 rounded-full bg-violet-50 flex items-center justify-center text-violet-600 font-bold shrink-0 text-xs">
                                {reply.username?.[0]?.toUpperCase() || 'P'}
                              </div>

                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between gap-2 mb-1">
                                  <span className="font-bold text-gray-900 text-xs truncate">
                                    {reply.username}
                                    <span className="ml-1.5 inline-block px-1.5 py-0.5 text-3xs font-extrabold uppercase bg-violet-50 text-violet-700 rounded-full tracking-wider">
                                      {t('reply')}
                                    </span>
                                  </span>
                                  <span className="text-3xs text-gray-400">
                                    {formatSafeDate(reply.created_at)}
                                  </span>
                                </div>

                                {isReplyEditing ? (
                                  <form onSubmit={(e) => handleEditComment(e, reply.id, true, comment.id)} className="mt-2">
                                    <textarea
                                      value={editText}
                                      onChange={(e) => setEditText(e.target.value)}
                                      className="w-full rounded-xl border p-3 text-sm focus:ring-2 focus:ring-violet-500 focus:outline-none"
                                      rows={2}
                                      required
                                    />
                                    <div className="flex gap-2 justify-end mt-2">
                                      <button
                                        type="button"
                                        onClick={() => setEditingCommentId(null)}
                                        className="px-3 py-1.5 border rounded-lg text-xs font-semibold text-gray-600 hover:bg-neutral-50 transition"
                                      >
                                        {t('cancel')}
                                      </button>
                                      <button
                                        type="submit"
                                        disabled={isSubmitting}
                                        className="px-3 py-1.5 bg-violet-600 text-white rounded-lg text-xs font-semibold hover:bg-violet-700 transition"
                                      >
                                        {t('save')}
                                      </button>
                                    </div>
                                  </form>
                                ) : (
                                  <>
                                    <p className={`text-xs text-gray-600 leading-relaxed ${reply.is_deleted ? 'italic text-gray-400' : ''}`}>
                                      {reply.text}
                                    </p>

                                    {(reply.can_edit || (!reply.is_deleted && (!isAuthenticated || (user && reply.user !== user.id)))) && (
                                      <div className="flex items-center gap-3 mt-1">
                                        {reply.can_edit && (
                                          <>
                                            <button
                                              onClick={() => startEditing(reply.id, reply.text)}
                                              className="text-3xs font-bold text-neutral-500 hover:text-neutral-700"
                                            >
                                              {t('edit')}
                                            </button>
                                            <button
                                              onClick={() => handleDeleteComment(reply.id, true, comment.id)}
                                              className="text-3xs font-bold text-red-500 hover:text-red-700"
                                            >
                                              {t('delete')}
                                            </button>
                                          </>
                                        )}

                                        {!reply.is_deleted && (!isAuthenticated || (user && reply.user !== user.id)) && (
                                          <ReportButton
                                            contentType="comment"
                                            objectId={reply.id}
                                            variant="text"
                                            className="text-neutral-400 hover:text-rose-600 text-3xs font-bold"
                                          />
                                        )}
                                      </div>
                                    )}
                                  </>
                                )}
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}

                    {/* Reply input form */}
                    {isReplying && (
                      <form onSubmit={(e) => handlePostReply(e, comment.id)} className="mt-4 ml-6 pl-4 border-l-2 border-violet-100">
                        <div className="flex gap-2 items-start">
                          <textarea
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            placeholder={t('replyPlaceholder')}
                            className="flex-1 rounded-xl border p-3 text-xs focus:ring-2 focus:ring-violet-500 focus:outline-none"
                            rows={2}
                            required
                          />
                          <div className="flex flex-col gap-1.5 justify-end">
                            <button
                              type="submit"
                              disabled={isSubmitting || !replyText.trim()}
                              className="px-3 py-1.5 bg-violet-600 text-white rounded-lg text-2xs font-semibold hover:bg-violet-700 disabled:opacity-50 transition"
                            >
                              {t('submit')}
                            </button>
                            <button
                              type="button"
                              onClick={() => setReplyingCommentId(null)}
                              className="px-3 py-1.5 border rounded-lg text-2xs font-semibold text-gray-600 hover:bg-neutral-50 transition"
                            >
                              {t('cancel')}
                            </button>
                          </div>
                        </div>
                      </form>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Input form at bottom for new questions */}
      {isAuthenticated ? (
        // Only clients/others can ask a question (provider owners reply to existing questions)
        !isProviderOwner ? (
          <form onSubmit={handlePostComment} className="border-t border-neutral-100 pt-6">
            <h3 className="text-sm font-bold text-gray-900 mb-3">{t('askQuestion')}</h3>
            <div className="flex flex-col gap-3">
              <textarea
                value={newCommentText}
                onChange={(e) => setNewCommentText(e.target.value)}
                placeholder={t('textPlaceholder')}
                className="w-full rounded-xl border p-4 text-sm focus:ring-2 focus:ring-violet-500 focus:outline-none"
                rows={3}
                required
              />
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isSubmitting || !newCommentText.trim()}
                  className="px-6 py-2.5 bg-violet-600 text-white rounded-xl text-sm font-bold hover:bg-violet-700 disabled:opacity-50 transition-colors"
                >
                  {t('submit')}
                </button>
              </div>
            </div>
          </form>
        ) : (
          <div className="border-t border-neutral-100 pt-6 text-xs italic text-gray-400">
            {t('notAllowed')}
          </div>
        )
      ) : (
        <div className="border-t border-neutral-100 pt-6 text-center">
          <Link
            href={`/${locale}/login/?next=${encodeURIComponent(window.location.pathname + window.location.search)}`}
            className="inline-flex items-center justify-center px-6 py-3 border border-violet-200 text-violet-600 font-bold rounded-xl text-sm hover:bg-violet-50 transition"
          >
            {t('loginToComment')}
          </Link>
        </div>
      )}
    </div>
  );
}
