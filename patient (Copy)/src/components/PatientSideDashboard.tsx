import { useEffect, useMemo, useState } from 'react';
import { User, Phone, Wifi, Activity, MessageSquare, LogOut } from 'lucide-react';
import { DeviceStatus } from './DeviceStatus';
import { VitalSignsCharts } from './VitalSignsCharts';
import { DoctorAdvicesReadOnly } from './DoctorAdvicesReadOnly';
import { LatestVitals } from './LatestVitals';
import { ActivityMonitor } from './ActivityMonitor';

interface PatientSideDashboardProps {
  patientId: string;
  onLogout: () => void;
}

export function PatientSideDashboard({ patientId, onLogout }: PatientSideDashboardProps) {
  const [deviceStatus, setDeviceStatus] = useState<any>(null);

  const patient = useMemo(() => {
    const record = (window as any)?.REMONI_PATIENT || {};
    return {
      id: record.id || patientId,
      name: record.name || 'Tammy Hale',
      age: record.age || 0,
      sex: record.sex || 'N/A',
      phone: record.tel || record.phone || 'N/A',
    };
  }, [patientId]);

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/device_status?patient_id=${patientId}`);
        if (!res.ok) return;
        const data = await res.json();
        setDeviceStatus(data);
      } catch (e) {
        console.error('Failed to load device status', e);
      }
    };
    fetchStatus();
    const interval = setInterval(fetchStatus, 10000);
    return () => clearInterval(interval);
  }, [patientId]);

  const handleLogoutClick = () => {
    if (window.handleLogout) {
      window.handleLogout();
    } else {
      onLogout();
    }
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* Purple Header */}
      <header className="bg-[#581B98] text-white shadow-lg">
        <div className="max-w-full mx-auto px-6 py-3">
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div className="flex items-center gap-6 flex-wrap">
              <div className="flex items-center gap-2">
                <User className="w-4 h-4" />
                <span className="text-sm font-medium">ID: {patient.id}</span>
              </div>
              <div className="text-sm font-medium">
                Name: {patient.name}
              </div>
              <div className="text-sm font-medium">
                Age: {patient.age}
              </div>
              <div className="text-sm font-medium">
                Sex: {patient.sex}
              </div>
              <div className="flex items-center gap-2">
                <Phone className="w-4 h-4" />
                <span className="text-sm font-medium">{patient.phone}</span>
              </div>
              <div className="flex items-center gap-2">
                <Activity className="w-4 h-4" />
                <span className="text-sm font-medium">
                  IP: {deviceStatus?.wifi?.ip_address || 'N/A'}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <Wifi className="w-4 h-4" />
                <span className="text-sm font-medium">
                  WiFi: {deviceStatus?.wifi?.ssid || 'N/A'}
                </span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => {
                  window.location.href = '/patient/chats?chat=remoni';
                }}
                className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg transition-colors"
              >
                <MessageSquare className="w-4 h-4" />
                <span>Chatbox</span>
              </button>
              <button
                onClick={handleLogoutClick}
                className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg transition-colors"
              >
                <LogOut className="w-4 h-4" />
                <span>Logout</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <div className="max-w-full mx-auto px-4 py-4 h-full">
          <div className="grid grid-cols-1 lg:grid-cols-[1fr_400px] gap-3 h-full">
            {/* Left Column: Latest Vitals + Charts in ONE white box */}
            <div className="bg-white rounded-lg shadow-md p-3 flex flex-col gap-3 min-h-0">
              {/* Latest Vitals - No background, just content */}
              <div>
                <LatestVitals patientId={patientId} showLastReading />
              </div>
              
              {/* Vital Signs Charts - No background, just content */}
              <div className="flex-1 min-h-0">
                <VitalSignsCharts patientId={patientId} />
              </div>
            </div>

            {/* Right Column: Device Status + Doctor's Advices + Activity Monitor */}
            <div className="flex flex-col gap-3 min-h-0">
              <DeviceStatus patientId={patientId} />
              <DoctorAdvicesReadOnly />
              <ActivityMonitor patientId={patientId} />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
