import { useState } from 'react';
import { DashboardHeader } from './components/DashboardHeader';
import { EmergencyAlerts } from './components/EmergencyAlerts';
import { Appointments } from './components/Appointments';
import { PatientsList } from './components/PatientsList';
import { PatientDashboard } from './components/PatientDashboard';
import { Chatroom } from './components/Chatroom';

export default function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentView, setCurrentView] = useState<'main' | 'patient' | 'chatroom'>('chatroom');
  const [selectedPatient, setSelectedPatient] = useState<string | null>(null);

  const handleLogout = () => {
    alert('Logging out...');
  };

  const handleViewPatient = (patientId: string) => {
    setSelectedPatient(patientId);
    setCurrentView('patient');
  };

  const handleBackToMain = () => {
    setCurrentView('main');
    setSelectedPatient(null);
  };

  const handleGoToChatroom = () => {
    setCurrentView('chatroom');
  };

  if (currentView === 'patient' && selectedPatient) {
    return (
      <PatientDashboard
        patientId={selectedPatient}
        onBack={handleBackToMain}
        onLogout={handleLogout}
      />
    );
  }

  if (currentView === 'chatroom') {
    return (
      <Chatroom
        onBack={handleBackToMain}
        onLogout={handleLogout}
      />
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardHeader onLogout={handleLogout} onChatbox={handleGoToChatroom} />
      
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Emergency Alerts */}
        <div className="mb-4">
          <EmergencyAlerts onViewPatient={handleViewPatient} />
        </div>

        {/* Today's Appointments and Assigned Patients - No spacing */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-4">
          <Appointments />
        </div>

        <div className="bg-white rounded-lg shadow-md p-6">
          <PatientsList
            searchQuery={searchQuery}
            onSearchChange={setSearchQuery}
            onViewPatient={handleViewPatient}
          />
        </div>
      </main>
    </div>
  );
}