import { AlertTriangle, ArrowRight, MessageCircle } from 'lucide-react';

const emergencyAlerts = [
  {
    id: 1,
    severity: 'CRITICAL',
    patientName: 'Sarah Johnson',
    patientId: 'P-2867',
    reason: 'High Oxygen Level',
    value: '99%',
    detectedTime: '2 PM',
    timeAgo: '10 min ago',
  },
  {
    id: 2,
    severity: 'URGENT',
    patientName: 'Michael Chen',
    patientId: 'P-3921',
    reason: 'Low Heart Rate',
    value: '45 BPM',
    detectedTime: '1:45 PM',
    timeAgo: '25 min ago',
  },
  {
    id: 3,
    severity: 'CRITICAL',
    patientName: 'Emma Wilson',
    patientId: 'P-4521',
    reason: 'High Blood Pressure',
    value: '180/120',
    detectedTime: '1:30 PM',
    timeAgo: '40 min ago',
  },
  {
    id: 4,
    severity: 'URGENT',
    patientName: 'David Brown',
    patientId: 'P-5632',
    reason: 'Low Blood Sugar',
    value: '55 mg/dL',
    detectedTime: '1:15 PM',
    timeAgo: '55 min ago',
  },
];

interface EmergencyAlertsProps {
  onViewPatient: (patientId: string) => void;
}

export function EmergencyAlerts({ onViewPatient }: EmergencyAlertsProps) {
  const handleAskPatient = (patientName: string, patientId: string) => {
    alert(`Message sent to ${patientName} (${patientId})'s chatbox: "Are you okay? Please respond."`);
  };

  const AlertCard = ({ alert }: { alert: typeof emergencyAlerts[0] }) => (
    <div className={`rounded-lg py-1.5 px-3 shadow-sm border-l-4 ${
      alert.severity === 'CRITICAL' 
        ? 'bg-red-50 border-red-600' 
        : 'bg-orange-50 border-orange-500'
    }`}>
      <div className="flex items-center gap-3">
        <span className={`px-2 py-0.5 rounded text-xs font-bold whitespace-nowrap w-[75px] text-center ${
          alert.severity === 'CRITICAL' 
            ? 'bg-red-600 text-white' 
            : 'bg-orange-500 text-white'
        }`}>
          {alert.severity}
        </span>
        
        <span className="font-semibold text-sm whitespace-nowrap w-[130px]">{alert.patientName}</span>
        <span className="text-sm text-gray-600 whitespace-nowrap w-[65px]">{alert.patientId}</span>
        <span className="font-medium text-sm whitespace-nowrap w-[150px]">{alert.reason}</span>
        <span className={`text-sm font-semibold whitespace-nowrap w-[75px] ${
          alert.severity === 'CRITICAL' ? 'text-red-600' : 'text-orange-600'
        }`}>{alert.value}</span>
        <span className="text-sm text-gray-700 whitespace-nowrap w-[140px]">{alert.detectedTime} ({alert.timeAgo})</span>
        
        <div className="flex items-center gap-2 ml-auto">
          <button
            onClick={() => handleAskPatient(alert.patientName, alert.patientId)}
            className="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-xs flex items-center gap-1 transition-colors whitespace-nowrap"
            title="Ask patient if they're okay"
          >
            <MessageCircle className="w-3 h-3" />
            <span>Ask</span>
          </button>
          <button
            onClick={() => onViewPatient(alert.patientId)}
            className="bg-[#581B98] hover:bg-[#9C1DE7] text-white px-3 py-1 rounded text-xs flex items-center gap-1 transition-colors whitespace-nowrap"
          >
            <span>Go</span>
            <ArrowRight className="w-3 h-3" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-3">
      <div className="flex items-center gap-2 mb-2">
        <AlertTriangle className="w-5 h-5 text-red-600" />
        <h2 className="font-bold text-gray-900">Emergency Alerts</h2>
        <span className="bg-red-600 text-white text-xs px-2 py-1 rounded-full">
          {emergencyAlerts.length}
        </span>
      </div>
      
      <div className="space-y-1.5">
        {emergencyAlerts.map((alert) => (
          <AlertCard key={alert.id} alert={alert} />
        ))}
      </div>
    </div>
  );
}