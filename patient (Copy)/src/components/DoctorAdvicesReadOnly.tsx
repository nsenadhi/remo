import { useEffect, useMemo, useState } from 'react';
import { Bell } from 'lucide-react';

interface Advice {
  id: string;
  text: string;
  date: string;
  time: string;
  source: 'Doctor' | 'Remoni';
}

export function DoctorAdvicesReadOnly() {
  const [advices, setAdvices] = useState<Advice[]>([]);
  const resolvedPatientId = useMemo(() => (window as any)?.REMONI_PATIENT?.id || '00001', []);

  useEffect(() => {
    const fetchAdvices = async () => {
      try {
        const res = await fetch(`/api/advice?patient_id=${resolvedPatientId}`);
        if (!res.ok) return;
        const data = await res.json();
        const items = Array.isArray(data?.advices) ? data.advices : [];
        const mapped = items.map((item: any) => ({
          id: String(item.id || ''),
          text: item.text || '',
          date: item.date || '',
          time: item.time || '',
          source: (String(item.source || '').toLowerCase() === 'remoni' ? 'Remoni' : 'Doctor') as Advice['source']
        }));
        setAdvices(mapped);
      } catch (e) {
        console.error('Failed to load advices', e);
      }
    };
    fetchAdvices();
  }, [resolvedPatientId]);

  return (
    <div className="bg-white rounded-lg shadow-md p-3 flex flex-col h-[320px]">
      <div className="flex items-center gap-2 mb-3">
        <Bell className="w-4 h-4 text-[#9C1DE7]" />
        <h3 className="font-bold text-gray-900 text-sm">Notifications</h3>
      </div>

      {/* Notifications List with Scroll */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {advices.length === 0 ? (
          <p className="text-gray-500 text-center py-4 text-xs">No notifications yet.</p>
        ) : (
          advices.map((advice) => (
            <div
              key={advice.id}
              className="p-2 bg-purple-50 border border-purple-200 rounded-lg"
            >
              <p className="text-gray-900 text-xs">
                <span className="font-bold text-[#581B98]">
                  [{advice.source === 'Doctor' ? "Doctor's Advice" : "Remoni's Advice"}]
                </span>{' '}
                {advice.text}
              </p>
              <div className="flex gap-2 mt-1">
                <span className="text-xs text-gray-600">
                  {advice.date}
                </span>
                <span className="text-xs text-gray-600">
                  {advice.time}
                </span>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
