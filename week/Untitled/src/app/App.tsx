import { useState } from 'react';
import { WeeklyAnalysis } from './components/WeeklyAnalysis';
import { Toaster } from 'sonner';

export default function App() {
  const [showWeeklyAnalysis, setShowWeeklyAnalysis] = useState(true);
  const params = new URLSearchParams(window.location.search);
  const patientId = params.get('patient_id') || '00001';
  const patientName = params.get('patient_name') || 'Patient';

  const handleBack = () => {
    if (window.history.length > 1) {
      window.history.back();
    } else {
      window.location.href = '/doctor';
    }
  };

  const handleLogout = () => {
    window.location.href = '/logout';
  };

  return (
    <>
      <Toaster position="top-right" richColors />
      {showWeeklyAnalysis && (
        <WeeklyAnalysis
          patientId={patientId}
          patientName={patientName}
          onBack={handleBack}
          onLogout={handleLogout}
        />
      )}
    </>
  );
}
