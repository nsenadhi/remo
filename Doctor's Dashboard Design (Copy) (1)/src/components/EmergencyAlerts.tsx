import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowRight, MessageCircle, Trash2 } from 'lucide-react';

interface EmergencyAlert {
  id?: string | number;
  alert_id?: string | number;
  severity?: string;
  patient_id?: string;
  patient_name?: string;
  reason?: string;
  value?: string;
  confidence?: number;
  datetime?: string;
  detected_time?: string;
  time_ago?: string;
  type?: string;
}

interface EmergencyAlertsProps {
  onViewPatient: (patientId: string) => void;
}

export function EmergencyAlerts({ onViewPatient }: EmergencyAlertsProps) {
  const preloadAlerts = (window as any)?.REMONI_PRELOAD?.emergencyAlerts ?? [];
  const [alerts, setAlerts] = useState<EmergencyAlert[]>(preloadAlerts);

  const getAlertTimestamp = (alert: EmergencyAlert) => {
    const raw = alert.detected_time || alert.datetime || '';
    const parsed = raw ? new Date(raw).getTime() : NaN;
    if (!Number.isNaN(parsed)) return parsed;
    const fallback = alert.alert_id || alert.id;
    const num = typeof fallback === 'string' ? Number(fallback) : Number(fallback);
    return Number.isFinite(num) ? num : 0;
  };

  const fetchAlerts = async () => {
    try {
      const res = await fetch('/api/emergency_alerts');
      if (!res.ok) return;
      const data = await res.json();
      const items = Array.isArray(data?.alerts) ? data.alerts : [];
      const sorted = [...items].sort((a, b) => getAlertTimestamp(b) - getAlertTimestamp(a));
      setAlerts(sorted);
    } catch (e) {
      console.error('Failed to load emergency alerts', e);
    }
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 3000);
    return () => clearInterval(interval);
  }, []);

  const formatTime = (dtStr?: string) => {
    if (!dtStr) return '';
    const dt = new Date(dtStr);
    if (Number.isNaN(dt.getTime())) return dtStr;
    return dt.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
  };

  const formatAgo = (dtStr?: string) => {
    if (!dtStr) return '';
    const dt = new Date(dtStr);
    if (Number.isNaN(dt.getTime())) return '';
    const diffMs = Date.now() - dt.getTime();
    const mins = Math.max(0, Math.round(diffMs / 60000));
    if (mins < 60) return `${mins} min ago`;
    const hours = Math.floor(mins / 60);
    return `${hours} hr ago`;
  };

  const handleAskPatient = async (patientName: string, patientId: string) => {
    try {
      await fetch('/api/doctor_requests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          patient_id: patientId,
          message: 'Are you okay? Please respond.'
        })
      });
      try {
        const key = `chat_prefill_${patientId}`;
        localStorage.setItem(key, 'Are you okay? Please respond.');
      } catch {
        // ignore storage failures
      }
      const returnPath = encodeURIComponent('/doctor');
      window.location.href = `/doctor/chats?chat=direct-${encodeURIComponent(patientId)}&return=${returnPath}&patient_name=${encodeURIComponent(patientName)}`;
    } catch (e) {
      console.error('Failed to send request', e);
    }
  };

  const handleDeleteAlert = async (alert: EmergencyAlert) => {
    try {
      await fetch('/api/emergency_alerts/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          alert_id: alert.alert_id || alert.id,
          patient_id: alert.patient_id,
          datetime: alert.datetime,
          type: alert.type
        })
      });
      fetchAlerts();
    } catch (e) {
      console.error('Failed to delete alert', e);
    }
  };

  const AlertCard = ({ alert }: { alert: EmergencyAlert }) => {
    const severity = (alert.severity || 'URGENT').toUpperCase();
    const patientName = alert.patient_name || 'Patient';
    const patientId = alert.patient_id || '00001';
    const alertType = String(alert.type || '').toLowerCase();
    const inferStatus = () => {
      if (alertType.includes('high')) return 'high';
      if (alertType.includes('low')) return 'low';
      return '';
    };
    const inferredStatus = inferStatus();
    const prettyReason = () => {
      if (alertType.includes('fall')) return 'Fall Detected';
      if (alertType.includes('heart_rate') || alertType.includes('heartrate')) {
        return `Heart Rate is ${inferredStatus || 'abnormal'}`;
      }
      if (alertType.includes('blood_pressure') || alertType.includes('bp')) {
        return `Blood Pressure is ${inferredStatus || 'abnormal'}`;
      }
      if (alertType.includes('glucose')) {
        return `Blood Glucose is ${inferredStatus || 'abnormal'}`;
      }
      if (alertType.includes('temperature')) {
        return `Body Temperature is ${inferredStatus || 'abnormal'}`;
      }
      if (alertType.includes('spo2') || alertType.includes('oxygen')) {
        return `Oxygen Saturation is ${inferredStatus || 'abnormal'}`;
      }
      if (alertType.includes('respiratory')) {
        return `Respiratory Rate is ${inferredStatus || 'abnormal'}`;
      }
      return 'Emergency Alert';
    };
    const reason = alert.reason || alert.alert_title || prettyReason();
    const unitForValue = () => {
      if (alertType.includes('heart_rate') || alertType.includes('heartrate')) return 'BPM';
      if (alertType.includes('spo2') || alertType.includes('oxygen')) return '%';
      if (alertType.includes('blood_pressure') || alertType.includes('bp')) return 'mmHg';
      if (alertType.includes('glucose')) return 'mg/dL';
      if (alertType.includes('temperature')) return '°C';
      if (alertType.includes('respiratory')) return 'br/min';
      return '';
    };
    const rawValue = alert.value || (alert.confidence != null ? `${alert.confidence}` : '--');
    const unit = unitForValue();
    const value = rawValue === '--' || !unit ? rawValue : `${rawValue} ${unit}`;
    const detectedTime = alert.detected_time || alert.datetime || '';
    const timeAgo = alert.time_ago || formatAgo(alert.datetime || alert.detected_time);

    return (
      <div className={`rounded-lg py-1.5 px-3 shadow-sm border-l-4 ${
        severity === 'CRITICAL'
          ? 'bg-red-50 border-red-600'
          : 'bg-orange-50 border-orange-500'
      }`}>
        <div className="flex items-center gap-3">
          <span className={`px-2 py-0.5 rounded text-xs font-bold whitespace-nowrap w-[75px] text-center ${
            severity === 'CRITICAL'
              ? 'bg-red-600 text-white'
              : 'bg-orange-500 text-white'
          }`}>
            {severity}
          </span>

          <span className="font-semibold text-sm whitespace-nowrap w-[130px]">{patientName}</span>
          <span className="text-sm text-gray-600 whitespace-nowrap w-[65px]">{patientId}</span>
          <span className="font-medium text-sm whitespace-nowrap w-[180px]">{reason}</span>

          <div className="flex-1"></div>

          <span className={`text-sm font-semibold whitespace-nowrap w-[90px] text-right ${
            severity === 'CRITICAL' ? 'text-red-600' : 'text-orange-600'
          }`}>{value}</span>
          <span className="text-sm text-gray-700 whitespace-nowrap w-[160px] text-right">
            {formatTime(detectedTime)}{timeAgo ? ` (${timeAgo})` : ''}
          </span>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleAskPatient(patientName, patientId)}
              className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-xs flex items-center gap-1 transition-colors whitespace-nowrap"
              title="Ask patient if they're okay"
            >
              <MessageCircle className="w-3 h-3" />
              <span>Ask</span>
            </button>
            <button
              onClick={() => onViewPatient(patientId)}
              className="bg-[#581B98] hover:bg-[#9C1DE7] text-white px-3 py-1 rounded text-xs flex items-center gap-1 transition-colors whitespace-nowrap"
            >
              <span>Go</span>
              <ArrowRight className="w-3 h-3" />
            </button>
            <button
              onClick={() => handleDeleteAlert(alert)}
              className="text-red-600 hover:text-red-700 p-1 rounded transition-colors"
              title="Delete alert"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-5 h-5 text-red-600" />
        <h2 className="font-bold text-gray-900">Emergency Alerts</h2>
        <span className="bg-red-600 text-white text-xs px-2 py-1 rounded-full">
          {alerts.length}
        </span>
      </div>

      <div className="space-y-1.5">
        {alerts.map((alert, index) => (
          <AlertCard key={String(alert.alert_id || alert.id || index)} alert={alert} />
        ))}
      </div>
    </div>
  );
}
