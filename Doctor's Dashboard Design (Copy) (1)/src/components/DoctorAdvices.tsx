import { useEffect, useMemo, useState } from 'react';
import { Plus, Trash2, MessageSquare } from 'lucide-react';

interface Advice {
  id: string;
  text: string;
  date: string;
  time: string;
  isRemoni?: boolean; // Flag to identify REMONI's advice
}

interface DoctorAdvicesProps {
  patientId: string;
}

export function DoctorAdvices({ patientId }: DoctorAdvicesProps) {
  const [advices, setAdvices] = useState<Advice[]>([]);
  const [newAdvice, setNewAdvice] = useState('');
  const [loading, setLoading] = useState(false);

  const resolvedPatientId = useMemo(() => patientId || '00001', [patientId]);

  const fallbackAdvices = useMemo<Advice[]>(() => {
    if (resolvedPatientId === '00001') return [];
    return [
      {
        id: `${resolvedPatientId}-fallback-1`,
        text: 'Maintain hydration and take short walks as tolerated.',
        date: '2026-02-02',
        time: '09:20 AM',
      },
      {
        id: `${resolvedPatientId}-fallback-2`,
        text: 'Log any symptoms like dizziness, fatigue, or shortness of breath.',
        date: '2026-02-01',
        time: '03:45 PM',
      },
    ];
  }, [resolvedPatientId]);

  useEffect(() => {
    const fetchAdvices = async () => {
      setLoading(true);
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
          isRemoni: String(item.source || '').toLowerCase() === 'remoni',
        }));
        setAdvices(mapped.length ? mapped : fallbackAdvices);
      } catch (e) {
        console.error('Failed to load advices', e);
        if (fallbackAdvices.length) {
          setAdvices(fallbackAdvices);
        }
      } finally {
        setLoading(false);
      }
    };
    fetchAdvices();
  }, [resolvedPatientId]);

  const handleAddAdvice = async () => {
    const text = newAdvice.trim();
    if (!text) return;
    try {
      const res = await fetch('/api/advice', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_id: resolvedPatientId, text }),
      });
      if (!res.ok) return;
      const data = await res.json();
      const advice = data?.advice;
      if (advice) {
        setAdvices((prev) => [
          {
            id: String(advice.id || ''),
            text: advice.text || text,
            date: advice.date || '',
            time: advice.time || '',
            isRemoni: String(advice.source || '').toLowerCase() === 'remoni',
          },
          ...prev,
        ]);
        setNewAdvice('');
      }
    } catch (e) {
      console.error('Failed to add advice', e);
    }
  };

  const handleDeleteAdvice = async (id: string) => {
    try {
      const res = await fetch('/api/advice', {
        method: 'DELETE',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ patient_id: resolvedPatientId, advice_id: id }),
      });
      if (!res.ok) return;
      setAdvices((prev) => prev.filter((advice) => advice.id !== id));
    } catch (e) {
      console.error('Failed to delete advice', e);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-3 h-full flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 mb-2">
        <MessageSquare className="w-4 h-4 text-[#9C1DE7]" />
        <h3 className="font-bold text-gray-900 text-sm">Doctor's Advices</h3>
      </div>

      {/* Add New Advice */}
      <div className="mb-3">
        <div className="flex gap-2">
          <textarea
            value={newAdvice}
            onChange={(e) => setNewAdvice(e.target.value)}
            placeholder="Type advice for patient..."
            className="flex-1 px-2 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9C1DE7] focus:border-transparent resize-none text-sm"
            rows={2}
          />
          <button
            onClick={handleAddAdvice}
            className="bg-[#581B98] hover:bg-[#9C1DE7] text-white px-3 py-1 rounded-lg flex items-center gap-1 transition-colors h-fit text-sm"
          >
            <Plus className="w-3 h-3" />
            <span>Add</span>
          </button>
        </div>
      </div>

      {/* Advices List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {loading ? (
          <p className="text-gray-500 text-center py-4 text-xs">Loading advices...</p>
        ) : advices.length === 0 ? (
          <p className="text-gray-500 text-center py-4 text-xs">No advices added yet.</p>
        ) : (
          advices.map((advice) => (
            <div
              key={advice.id}
              className={`p-2 rounded-lg flex items-start justify-between gap-2 ${
                advice.isRemoni
                  ? 'bg-blue-50 border border-blue-200'
                  : 'bg-purple-50 border border-purple-200'
              }`}
            >
              <div className="flex-1">
                {advice.isRemoni ? (
                  <span className="text-xs font-extrabold text-blue-600 mr-1">[Remoni&apos;s Advice]</span>
                ) : (
                  <span className="text-xs font-extrabold text-[#581B98] mr-1">[Doctor&apos;s Advice]</span>
                )}
                <span className="text-gray-900 text-sm">{advice.text}</span>
                <div className="flex gap-2 mt-1">
                  <span className="text-sm text-gray-600">
                    {advice.date}
                  </span>
                  <span className="text-sm text-gray-600">
                    {advice.time}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleDeleteAdvice(advice.id)}
                className="text-red-600 hover:text-red-700 transition-colors"
                title="Delete advice"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
