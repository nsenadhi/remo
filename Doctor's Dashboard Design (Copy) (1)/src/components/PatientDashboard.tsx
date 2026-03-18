import { useMemo } from 'react';
import { ArrowLeft, MessageSquare, LogOut, User, Phone } from 'lucide-react';
import { DeviceStatus } from './DeviceStatus';
import { VitalSignsCharts } from './VitalSignsCharts';
import { DoctorAdvices } from './DoctorAdvices';
import { LatestVitals } from './LatestVitals';
import { ActivityMonitor } from './ActivityMonitor';

interface PatientDashboardProps {
  patientId: string;
  onBack: () => void;
  onLogout: () => void;
}

export function PatientDashboard({ patientId, onBack, onLogout }: PatientDashboardProps) {
  const patient = useMemo(() => {
    const details = (window as any)?.REMONI_PATIENT_DETAILS || {};
    const key = details[patientId] ? patientId : (details['00001'] ? '00001' : patientId);
    const record = details[key];
    if (record) {
      return {
        id: String(record.id || key),
        name: record.name || 'Tammy Hale',
        age: Number(record.age) || 0,
        sex: record.sex || 'N/A',
        tel: record.tel || 'N/A',
        condition: record.condition || 'Hypertension',
      };
    }
    return {
      id: patientId,
      name: `Patient ${patientId}`,
      age: 0,
      sex: 'N/A',
      tel: 'N/A',
      condition: 'N/A',
    };
  }, [patientId]);

  const handleGotoChatbox = () => {
    const returnUrl = window.location.href;
    try {
      sessionStorage.setItem('chat_return', returnUrl);
    } catch {
      // ignore storage failures
    }
    const returnPath = encodeURIComponent(returnUrl);
    window.location.href = `/doctor/chats?chat=direct-${patientId}&return=${returnPath}&patient_name=${encodeURIComponent(patient.name)}`;
  };

  return (
    <div className="h-screen bg-gray-50 flex flex-col overflow-hidden">
      {/* Header */}
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
              <div className="flex items-center gap-6">
                <div className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5 text-[#9C1DE7]" />
                  <div className="border-l border-white/30 pl-4">
                    <div className="flex items-center gap-6 text-sm">
                      <div>
                        <span className="text-purple-200">ID:</span>
                        <span className="font-bold ml-2">{patient.id}</span>
                      </div>
                      <div>
                        <span className="text-purple-200">Name:</span>
                        <span className="font-bold ml-2">{patient.name}</span>
                      </div>
                      <div>
                        <span className="text-purple-200">Age:</span>
                        <span className="font-bold ml-2">{patient.age}</span>
                      </div>
                      <div>
                        <span className="text-purple-200">Sex:</span>
                        <span className="font-bold ml-2">{patient.sex}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <Phone className="w-3 h-3" />
                        <span className="font-bold">{patient.tel}</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <button
                onClick={handleGotoChatbox}
                className="flex items-center gap-2 bg-white/10 hover:bg-white/20 px-4 py-2 rounded-lg transition-colors font-bold"
              >
                <MessageSquare className="w-4 h-4" />
                <span>Chatbox</span>
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
        <div className="h-full flex flex-col gap-2">
          {/* Latest Vitals and Device Status */}
          <div className="grid grid-cols-1 lg:grid-cols-7 gap-3" style={{ height: '100px' }}>
            <div className="lg:col-span-5">
              <LatestVitals patientId={patientId} showLastReading={true} useMockData={patientId !== '00001'} />
            </div>
            <div className="lg:col-span-2">
              <DeviceStatus patientId={patientId} useMockData={patientId !== '00001'} />
            </div>
          </div>

          {/* Charts and Right Sidebar */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-7 gap-3 overflow-hidden min-h-0">
            <div className="lg:col-span-5 overflow-hidden min-h-0">
              <VitalSignsCharts patientId={patientId} useMockData={patientId !== '00001'} />
            </div>
            <div className="lg:col-span-2 flex flex-col gap-3 overflow-hidden min-h-0" style={{ marginTop: '0.2cm' }}>
              <div className="h-1/2 overflow-hidden min-h-0">
                <DoctorAdvices patientId={patientId} />
              </div>
              <div className="h-1/2 overflow-hidden min-h-0">
                <ActivityMonitor patientId={patientId} useMockData={patientId !== '00001'} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
