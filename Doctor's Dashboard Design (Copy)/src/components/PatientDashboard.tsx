import { useState } from 'react';
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

// Mock patient data
const patientData: Record<string, any> = {
  'P-2847': {
    id: 'P-2847',
    name: 'Sarah Johnson',
    age: 62,
    sex: 'Female',
    tel: '+1 (555) 123-4567',
    condition: 'Hypertension',
  },
  'P-3921': {
    id: 'P-3921',
    name: 'Michael Chen',
    age: 29,
    sex: 'Male',
    tel: '+1 (555) 987-6543',
    condition: 'Heart Condition',
  },
  'P-1523': {
    id: 'P-1523',
    name: 'Emily Davis',
    age: 45,
    sex: 'Female',
    tel: '+1 (555) 456-7890',
    condition: 'Diabetes',
  },
};

export function PatientDashboard({ patientId, onBack, onLogout }: PatientDashboardProps) {
  const patient = patientData[patientId] || {
    id: patientId,
    name: 'Unknown Patient',
    age: 0,
    sex: 'N/A',
    tel: 'N/A',
    condition: 'N/A',
  };

  const handleGotoChatbox = () => {
    alert('Navigating to chatbox...');
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
              <LatestVitals />
            </div>
            <div className="lg:col-span-2">
              <DeviceStatus />
            </div>
          </div>

          {/* Charts and Right Sidebar */}
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-7 gap-3 overflow-hidden min-h-0">
            <div className="lg:col-span-5 overflow-hidden min-h-0">
              <VitalSignsCharts />
            </div>
            <div className="lg:col-span-2 flex flex-col gap-3 overflow-hidden min-h-0" style={{ marginTop: '-0.3cm' }}>
              <div className="h-1/2 overflow-hidden min-h-0">
                <DoctorAdvices patientId={patientId} />
              </div>
              <div className="h-1/2 overflow-hidden min-h-0">
                <ActivityMonitor />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}