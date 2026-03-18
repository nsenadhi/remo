import { useEffect, useState } from 'react';
import { ArrowLeft, LogOut, FileText, Upload, Trash2, Activity, Pill, AlertTriangle, MessageSquare, Brain, PlusCircle, Calendar, Send, Mail } from 'lucide-react';
import { VitalSignsCharts } from './VitalSignsCharts';
import { toast } from 'sonner';

interface WeeklyAnalysisProps {
  patientId: string;
  patientName: string;
  onBack: () => void;
  onLogout: () => void;
}

interface Report {
  id: string;
  name: string;
  uploadDate: string;
  size: string;
  category: 'lab' | 'ecg' | 'prescription' | 'other';
  url?: string;
}

interface EmergencyEvent {
  id: string;
  patientName: string;
  patientId: string;
  date: string;
  time: string;
  severity: 'CRITICAL' | 'URGENT';
  reason: string;
  value: string;
}

interface ActionPlan {
  id: string;
  version: number;
  createdDate: string;
  content: string;
}

interface DoctorReview {
  id: string;
  date: string;
  content: string;
}

export function WeeklyAnalysis({ patientId, patientName, onBack, onLogout }: WeeklyAnalysisProps) {
  const [reports, setReports] = useState<Report[]>([]);
  const [emergencyEvents, setEmergencyEvents] = useState<EmergencyEvent[]>([]);
  const [activeTab, setActiveTab] = useState<'lab' | 'ecg' | 'prescription' | 'other'>('lab');
  const [actionPlans, setActionPlans] = useState<ActionPlan[]>([]);
  const [newPlanContent, setNewPlanContent] = useState('');
  const [doctorReviews, setDoctorReviews] = useState<DoctorReview[]>([]);
  const [newReviewContent, setNewReviewContent] = useState('');
  const [isSendingReport, setIsSendingReport] = useState(false);
  const [isSendingEmail, setIsSendingEmail] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const weekRangeLabel = (() => {
    const now = new Date();
    const day = now.getDay();
    const diffToMonday = (day + 6) % 7;
    const start = new Date(now);
    start.setDate(now.getDate() - diffToMonday);
    start.setHours(0, 0, 0, 0);
    const end = new Date(start);
    end.setDate(start.getDate() + 6);

    const formatShort = (d: Date) =>
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    const formatLong = (d: Date) =>
      d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

    return `${formatShort(start)}-${formatLong(end)}`;
  })();

  const loadWeeklyData = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`/api/weekly-analysis?patient_id=${encodeURIComponent(patientId)}`);
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Failed to load weekly analysis data');
      }
      setReports(data.reports || []);
      setEmergencyEvents(data.emergency_events || []);
      setActionPlans(data.action_plans || []);
      setDoctorReviews(data.doctor_reviews || []);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to load weekly analysis data');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadWeeklyData();
  }, [patientId]);

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    const formData = new FormData();
    formData.append('patient_id', patientId);
    formData.append('category', activeTab);
    formData.append('file', file);

    toast.loading('Uploading report...', { id: 'upload-report' });
    try {
      const response = await fetch('/api/weekly-analysis/reports', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Failed to upload report');
      }
      setReports((prev) => [data.report, ...prev]);
      toast.success('Report uploaded.', { id: 'upload-report' });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to upload report.', { id: 'upload-report' });
    } finally {
      event.target.value = '';
    }
  };

  const handleDeleteReport = async (reportId: string) => {
    if (!confirm('Are you sure you want to delete this report?')) return;
    const response = await fetch(`/api/weekly-analysis/reports/${reportId}?patient_id=${encodeURIComponent(patientId)}`, {
      method: 'DELETE',
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      toast.error(data.message || 'Failed to delete report');
      return;
    }
    setReports((prev) => prev.filter((r) => r.id !== reportId));
    toast.success('Report deleted.');
  };

  const handleAddActionPlan = async () => {
    if (!newPlanContent.trim()) return;
    const response = await fetch('/api/weekly-analysis/action-plans', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: patientId, content: newPlanContent }),
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      toast.error(data.message || 'Failed to add action plan');
      return;
    }
    setActionPlans((prev) => [data.action_plan, ...prev]);
    setNewPlanContent('');
  };

  const handleDeleteActionPlan = async (planId: string) => {
    if (!confirm('Are you sure you want to delete this version?')) return;
    const response = await fetch(`/api/weekly-analysis/action-plans/${planId}?patient_id=${encodeURIComponent(patientId)}`, {
      method: 'DELETE',
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      toast.error(data.message || 'Failed to delete action plan');
      return;
    }
    setActionPlans((prev) => prev.filter((p) => p.id !== planId));
  };

  const handleAddReview = async () => {
    if (!newReviewContent.trim()) return;
    const response = await fetch('/api/weekly-analysis/reviews', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ patient_id: patientId, content: newReviewContent }),
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      toast.error(data.message || 'Failed to add review');
      return;
    }
    setDoctorReviews((prev) => [data.doctor_review, ...prev]);
    setNewReviewContent('');
  };

  const handleDeleteReview = async (reviewId: string) => {
    if (!confirm('Are you sure you want to delete this review?')) return;
    const response = await fetch(`/api/weekly-analysis/reviews/${reviewId}?patient_id=${encodeURIComponent(patientId)}`, {
      method: 'DELETE',
    });
    const data = await response.json();
    if (!response.ok || !data.success) {
      toast.error(data.message || 'Failed to delete review');
      return;
    }
    setDoctorReviews((prev) => prev.filter((r) => r.id !== reviewId));
  };

  const filteredReports = reports.filter((r) => r.category === activeTab);

  const categoryConfig = {
    lab: { label: 'Lab Reports', icon: FileText },
    ecg: { label: 'ECG', icon: Activity },
    prescription: { label: 'Prescriptions', icon: Pill },
    other: { label: 'Other', icon: FileText },
  };

  const handleSendReportToWhatsApp = async () => {
    setIsSendingReport(true);
    toast.loading('Preparing weekly report...', { id: 'whatsapp-report' });
    await new Promise((resolve) => setTimeout(resolve, 1500));
    setIsSendingReport(false);
    toast.success('WhatsApp flow is still placeholder. Email delivery is now active.', {
      id: 'whatsapp-report',
      duration: 4000,
    });
  };

  const handleSendReportViaEmail = async () => {
    setIsSendingEmail(true);
    toast.loading('Generating PDF report with medical reports...', { id: 'email-report' });
    try {
      const response = await fetch('/api/weekly-analysis/send-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_id: patientId, patient_name: patientName }),
      });
      const data = await response.json();
      if (!response.ok || !data.success) {
        throw new Error(data.message || 'Failed to send email report');
      }
      toast.success('Weekly analysis report sent to doctor\'s email successfully!', {
        id: 'email-report',
        duration: 4000,
      });
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'Failed to send email report.', {
        id: 'email-report',
        duration: 5000,
      });
    } finally {
      setIsSendingEmail(false);
    }
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      <header className="bg-[#581B98] text-white shadow-lg">
        <div className="max-w-full mx-auto px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={onBack}
                className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-3 py-2 rounded-lg transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Back</span>
              </button>
              <div className="border-l border-white/30 pl-4">
                <h1 className="font-bold text-lg">Weekly Analysis - {patientName}</h1>
                <p className="text-purple-200 text-sm">Patient ID: {patientId}</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="hidden md:flex items-center gap-2 bg-white/10 px-3 py-2 rounded-lg">
                <Calendar className="w-4 h-4 text-purple-100" />
                <span className="text-sm font-semibold text-purple-100">{weekRangeLabel}</span>
              </div>
              <button
                onClick={handleSendReportToWhatsApp}
                disabled={isSendingReport}
                className="flex items-center gap-2 bg-green-500 hover:bg-green-600 px-4 py-2 rounded-lg transition-colors font-bold disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                <Send className="w-4 h-4" />
                <span>{isSendingReport ? 'Sending...' : 'Send to WhatsApp'}</span>
              </button>
              <button
                onClick={handleSendReportViaEmail}
                disabled={isSendingEmail}
                className="flex items-center gap-2 bg-blue-500 hover:bg-blue-600 px-4 py-2 rounded-lg transition-colors font-bold disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                <Mail className="w-4 h-4" />
                <span>{isSendingEmail ? 'Sending...' : 'Send via Email'}</span>
              </button>
              <button
                onClick={onLogout}
                className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg transition-colors font-bold"
              >
                <LogOut className="w-4 h-4" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="flex-1 px-4 py-3 overflow-hidden">
        <div className="h-full flex gap-3">
          <div className="flex flex-col gap-3" style={{ width: '65%' }}>
            <div className="bg-white rounded-lg shadow-md p-3 overflow-hidden" style={{ height: '45%' }}>
              <h2 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                <Activity className="w-4 h-4 text-[#9C1DE7]" />
                Weekly Vital Signs Monitoring
              </h2>
              <div className="h-[calc(100%-28px)]">
                <VitalSignsCharts patientId={patientId} defaultTimeRange="weekly" hideTimeRangeSelector={true} />
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-3 overflow-hidden" style={{ height: '20%' }}>
              <h2 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-red-600" />
                Emergency Events This Week
                <span className="bg-red-100 text-red-600 text-xs px-2 py-0.5 rounded-full font-semibold">
                  {emergencyEvents.length}
                </span>
              </h2>
              <div className="h-[calc(100%-32px)] overflow-y-auto space-y-1.5">
                {emergencyEvents.length === 0 ? (
                  <div className="text-center py-4 text-gray-400 text-xs">No emergency alerts for this week</div>
                ) : emergencyEvents.map((event) => (
                  <div
                    key={event.id}
                    className={`rounded py-1.5 px-3 border-l-4 ${
                      event.severity === 'CRITICAL'
                        ? 'bg-red-50 border-red-600'
                        : 'bg-orange-50 border-orange-500'
                    }`}
                    style={{ display: 'grid', gridTemplateColumns: 'auto 110px 70px 1fr auto auto', gap: '16px', alignItems: 'center' }}
                  >
                    <span
                      className={`px-2 py-0.5 rounded text-xs font-bold ${
                        event.severity === 'CRITICAL'
                          ? 'bg-red-600 text-white'
                          : 'bg-orange-500 text-white'
                      }`}
                    >
                      {event.severity}
                    </span>
                    <span className="text-xs font-semibold text-gray-900">{event.patientName}</span>
                    <span className="text-xs text-gray-600">P-{event.patientId}</span>
                    <span className="text-xs font-medium text-gray-900">{event.reason}</span>
                    <span
                      className={`text-xs font-bold text-right ${
                        event.severity === 'CRITICAL' ? 'text-red-600' : 'text-orange-600'
                      }`}
                    >
                      {event.value}
                    </span>
                    <span className="text-xs text-gray-600 text-right">{event.time}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-3 overflow-hidden flex flex-col" style={{ height: '35%' }}>
              <h2 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-[#9C1DE7]" />
                Doctor Review
                {doctorReviews.length > 0 && (
                  <span className="bg-purple-100 text-[#581B98] text-xs px-2 py-0.5 rounded-full font-semibold">
                    {doctorReviews.length} {doctorReviews.length === 1 ? 'review' : 'reviews'}
                  </span>
                )}
              </h2>

              <div className="mb-2">
                <textarea
                  value={newReviewContent}
                  onChange={(e) => setNewReviewContent(e.target.value)}
                  placeholder="Add doctor's review, observations, recommendations..."
                  className="w-full text-xs border border-gray-300 rounded p-2 resize-none focus:outline-none focus:ring-2 focus:ring-[#9C1DE7] focus:border-transparent"
                  rows={3}
                />
                <button
                  onClick={handleAddReview}
                  disabled={!newReviewContent.trim()}
                  className="mt-1 flex items-center gap-1 bg-[#581B98] text-white px-2 py-1 rounded text-xs hover:bg-[#9C1DE7] transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  <PlusCircle className="w-3 h-3" />
                  <span>Add Review</span>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2">
                {doctorReviews.length === 0 ? (
                  <div className="text-center py-4 text-gray-400 text-xs">
                    <MessageSquare className="w-6 h-6 mx-auto mb-1 opacity-50" />
                    <p>No doctor reviews yet</p>
                  </div>
                ) : (
                  doctorReviews.map((review) => (
                    <div
                      key={review.id}
                      className="border border-purple-200 rounded-lg p-3 bg-gradient-to-r from-purple-50 to-purple-100 hover:from-purple-100 hover:to-purple-150 transition-colors relative group"
                    >
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-xs text-[#581B98] font-bold">
                          {new Date(review.date).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            year: 'numeric',
                          })}
                        </span>
                        <button
                          onClick={() => handleDeleteReview(review.id)}
                          className="p-1 text-red-600 hover:bg-red-100 rounded transition-colors opacity-0 group-hover:opacity-100"
                          title="Delete Review"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="text-xs text-gray-800 leading-relaxed whitespace-pre-line">
                        {review.content}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          <div className="flex flex-col gap-3" style={{ width: '35%' }}>
            <div className="bg-white rounded-lg shadow-md p-3 overflow-hidden" style={{ height: '30%' }}>
              <h2 className="text-sm font-bold text-gray-900 mb-2 flex items-center gap-2">
                <Brain className="w-4 h-4 text-[#9C1DE7]" />
                REMONI's Analysis During the Week
              </h2>
              <div className="h-[calc(100%-28px)] overflow-y-auto">
                <div className="bg-gradient-to-r from-purple-50 to-purple-100 border border-purple-200 rounded-lg p-3">
                  {isLoading ? (
                    <p className="text-xs text-gray-800 leading-relaxed">Loading weekly analysis...</p>
                  ) : (
                    <>
                      <p className="text-xs text-gray-800 leading-relaxed">
                        <span className="font-bold text-[#581B98]">Weekly Summary:</span> This week recorded <span className="font-semibold text-red-600">{emergencyEvents.length} emergency alert{emergencyEvents.length === 1 ? '' : 's'}</span>, {doctorReviews.length} doctor review{doctorReviews.length === 1 ? '' : 's'}, {actionPlans.length} action plan version{actionPlans.length === 1 ? '' : 's'}, and {reports.length} uploaded report{reports.length === 1 ? '' : 's'}.
                      </p>
                      <div className="mt-2 pt-2 border-t border-purple-200">
                        <p className="text-xs text-gray-800 leading-relaxed">
                          <span className="font-bold text-[#581B98]">Key Findings:</span> Use the weekly charts, emergency list, notes, and uploaded PDFs to review this patient's last 7 days. The email export includes the same weekly summary plus attached report PDFs when available.
                        </p>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-3 overflow-hidden flex flex-col" style={{ height: '40%' }}>
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                  <Calendar className="w-4 h-4 text-[#9C1DE7]" />
                  Action Plan for Next Week
                  {actionPlans.length > 0 && (
                    <span className="bg-purple-100 text-[#581B98] text-xs px-2 py-0.5 rounded-full font-semibold">
                      {actionPlans.length} {actionPlans.length === 1 ? 'version' : 'versions'}
                    </span>
                  )}
                </h2>
              </div>

              <div className="mb-2">
                <textarea
                  value={newPlanContent}
                  onChange={(e) => setNewPlanContent(e.target.value)}
                  placeholder="Add new action plan for next week..."
                  className="w-full text-xs border border-gray-300 rounded p-2 resize-none focus:outline-none focus:ring-2 focus:ring-[#9C1DE7] focus:border-transparent"
                  rows={3}
                />
                <button
                  onClick={handleAddActionPlan}
                  disabled={!newPlanContent.trim()}
                  className="mt-1 flex items-center gap-1 bg-[#581B98] text-white px-2 py-1 rounded text-xs hover:bg-[#9C1DE7] transition-colors disabled:bg-gray-300 disabled:cursor-not-allowed"
                >
                  <PlusCircle className="w-3 h-3" />
                  <span>Add New Version</span>
                </button>
              </div>

              <div className="flex-1 overflow-y-auto space-y-2">
                {actionPlans.length === 0 ? (
                  <div className="text-center py-4 text-gray-400 text-xs">
                    <Calendar className="w-6 h-6 mx-auto mb-1 opacity-50" />
                    <p>No action plans yet</p>
                  </div>
                ) : (
                  actionPlans.map((plan) => (
                    <div
                      key={plan.id}
                      className="border border-purple-200 rounded-lg p-2 bg-purple-50 hover:bg-purple-100 transition-colors"
                    >
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <span className="bg-[#581B98] text-white text-xs px-2 py-0.5 rounded font-bold">
                            V{plan.version}
                          </span>
                          <span className="text-xs text-gray-600">
                            {new Date(plan.createdDate).toLocaleDateString('en-US', {
                              month: 'short',
                              day: 'numeric',
                              year: 'numeric',
                            })}
                          </span>
                        </div>
                        <button
                          onClick={() => handleDeleteActionPlan(plan.id)}
                          className="p-1 text-red-600 hover:bg-red-100 rounded transition-colors"
                          title="Delete Version"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="text-xs text-gray-800 whitespace-pre-line leading-relaxed">
                        {plan.content}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            <div className="bg-white rounded-lg shadow-md p-3 overflow-hidden flex flex-col" style={{ height: '30%' }}>
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                  <FileText className="w-4 h-4 text-[#9C1DE7]" />
                  Medical Reports
                </h2>
                <label className="flex items-center gap-1 bg-[#581B98] text-white px-2 py-1 rounded text-xs cursor-pointer hover:bg-[#9C1DE7] transition-colors">
                  <Upload className="w-3 h-3" />
                  <span>Upload</span>
                  <input
                    type="file"
                    accept=".pdf"
                    onChange={handleFileUpload}
                    className="hidden"
                  />
                </label>
              </div>

              <div className="flex gap-1 mb-2 border-b border-gray-200">
                {(Object.keys(categoryConfig) as Array<keyof typeof categoryConfig>).map((cat) => {
                  const config = categoryConfig[cat];
                  const Icon = config.icon;
                  const isActive = activeTab === cat;
                  const count = reports.filter((r) => r.category === cat).length;
                  return (
                    <button
                      key={cat}
                      onClick={() => setActiveTab(cat)}
                      className={`flex items-center gap-1 px-2 py-1 text-xs font-semibold transition-colors border-b-2 ${
                        isActive
                          ? 'border-[#9C1DE7] text-[#9C1DE7]'
                          : 'border-transparent text-gray-500 hover:text-gray-700'
                      }`}
                    >
                      <Icon className="w-3 h-3" />
                      <span className="hidden xl:inline">{config.label}</span>
                      {count > 0 && (
                        <span
                          className={`text-xs px-1 rounded-full ${
                            isActive ? 'bg-[#9C1DE7] text-white' : 'bg-gray-200 text-gray-600'
                          }`}
                        >
                          {count}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>

              <div className="flex-1 overflow-y-auto space-y-1.5">
                {filteredReports.length === 0 ? (
                  <div className="text-center py-4 text-gray-400 text-xs">
                    <FileText className="w-6 h-6 mx-auto mb-1 opacity-50" />
                    <p>No reports</p>
                  </div>
                ) : (
                  filteredReports.map((report) => (
                    <div
                      key={report.id}
                      className="flex items-center justify-between p-2 border border-gray-200 rounded hover:bg-gray-50 transition-colors"
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <div className="bg-red-100 p-1 rounded">
                          <FileText className="w-3 h-3 text-red-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-semibold text-gray-900 truncate text-xs">{report.name}</p>
                          <p className="text-xs text-gray-500">
                            {new Date(report.uploadDate).toLocaleDateString()} • {report.size}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => report.url ? window.open(report.url, '_blank', 'noopener,noreferrer') : null}
                          className="px-2 py-1 bg-[#581B98] text-white rounded hover:bg-[#9C1DE7] transition-colors text-xs"
                        >
                          View
                        </button>
                        <button
                          onClick={() => handleDeleteReport(report.id)}
                          className="p-1 text-red-600 hover:bg-red-50 rounded transition-colors"
                          title="Delete"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
