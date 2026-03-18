import { useEffect, useState } from 'react';
import { DashboardHeader } from './components/DashboardHeader';
import { EmergencyAlerts } from './components/EmergencyAlerts';
import { Appointments } from './components/Appointments';
import { PatientsList } from './components/PatientsList';
import { PatientDashboard } from './components/PatientDashboard';

export default function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [currentView, setCurrentView] = useState<'main' | 'patient'>('main');
  const [selectedPatient, setSelectedPatient] = useState<string | null>(null);

  useEffect(() => {
    const syncFromPath = () => {
      const match = window.location.pathname.match(/^\/doctor\/patient\/([^/]+)$/);
      if (match) {
        setSelectedPatient(match[1]);
        setCurrentView('patient');
        return;
      }
      setCurrentView('main');
      setSelectedPatient(null);
    };

    syncFromPath();
    const onPopState = () => syncFromPath();
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const handleLogout = () => {
    if (typeof (window as any).handleLogout === 'function') {
      (window as any).handleLogout();
      return;
    }
    window.location.href = '/logout';
  };

  const handleViewPatient = (patientId: string) => {
    const normalized = patientId && patientId.trim() ? patientId.trim() : '00001';
    setSelectedPatient(normalized);
    setCurrentView('patient');
    try {
      window.history.pushState({}, '', `/doctor/patient/${encodeURIComponent(normalized)}`);
    } catch {
      // ignore history failures
    }
  };

  const handleBackToMain = () => {
    setCurrentView('main');
    setSelectedPatient(null);
    try {
      window.history.pushState({}, '', '/doctor');
    } catch {
      // ignore history failures
    }
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

  return (
    <div className="min-h-screen bg-gray-50">
      <DashboardHeader onLogout={handleLogout} />
      
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
