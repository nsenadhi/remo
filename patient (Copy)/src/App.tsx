import { useState } from 'react';
import { DashboardHeader } from './components/DashboardHeader';
import { EmergencyAlerts } from './components/EmergencyAlerts';
import { Appointments } from './components/Appointments';
import { PatientsList } from './components/PatientsList';
import { PatientDashboard } from './components/PatientDashboard';
import { PatientSideDashboard } from './components/PatientSideDashboard';
import { Chatbox } from './components/Chatbox';

export default function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentView, setCurrentView] = useState<'main' | 'patient' | 'patientSide'>('patientSide');
  const [selectedPatient, setSelectedPatient] = useState<string | null>(null);
  const [isChatboxOpen, setIsChatboxOpen] = useState(false);

  const handleLogout = () => {
    if (window.handleLogout) {
      window.handleLogout();
    }
  };

  const handleViewPatient = (patientId: string) => {
    setSelectedPatient(patientId);
    setCurrentView('patient');
  };

  const handleBackToMain = () => {
    setCurrentView('main');
    setSelectedPatient(null);
  };

  // Patient Side Dashboard View
  const resolvedPatientId = (window as any)?.REMONI_PATIENT?.id || '00001';

  if (currentView === 'patientSide') {
    return (
      <PatientSideDashboard
        patientId={resolvedPatientId}
        onLogout={handleLogout}
      />
    );
  }

  if (currentView === 'patient' && selectedPatient) {
    return (
      <PatientDashboard
        patientId={selectedPatient}
        onBack={handleBackToMain}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardHeader onLogout={handleLogout} onOpenChatbox={() => setIsChatboxOpen(true)} />
      
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Emergency Alerts */}
        <div className="mb-4">
          <EmergencyAlerts onViewPatient={handleViewPatient} />
        </div>

        {/* Today's Appointments and Assigned Patients - No spacing */}
        <div className="space-y-0">
          <Appointments />
          <PatientsList
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onViewPatient={handleViewPatient}
          />
        </div>
      </main>

      <Chatbox 
        isOpen={isChatboxOpen} 
        onClose={() => setIsChatboxOpen(false)}
        userRole="patient"
        userName={window.REMONI_USER?.name || 'Patient'}
      />
    </div>
  );
}
