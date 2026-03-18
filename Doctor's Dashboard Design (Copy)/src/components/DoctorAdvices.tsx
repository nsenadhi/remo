import { useState } from 'react';
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
  const [advices, setAdvices] = useState<Advice[]>([
    {
      id: '1',
      text: 'Please take your medication twice daily with meals.',
      date: '2025-01-20',
      time: '10:30 AM',
    },
    {
      id: '2',
      text: 'Monitor blood glucose levels before and after meals.',
      date: '2025-01-19',
      time: '2:15 PM',
    },
    {
      id: '3',
      text: "Your heart rate patterns suggest good cardiovascular health. Keep up the regular exercise routine.",
      date: '2025-01-18',
      time: '9:00 AM',
      isRemoni: true,
    },
    {
      id: '4',
      text: "Blood glucose levels are well controlled. Continue current diet plan.",
      date: '2025-01-17',
      time: '3:30 PM',
      isRemoni: true,
    },
  ]);
  const [newAdvice, setNewAdvice] = useState('');

  const handleAddAdvice = () => {
    if (newAdvice.trim()) {
      const now = new Date();
      const advice: Advice = {
        id: Date.now().toString(),
        text: newAdvice,
        date: now.toISOString().split('T')[0],
        time: now.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
      };
      setAdvices([advice, ...advices]);
      setNewAdvice('');
    }
  };

  const handleDeleteAdvice = (id: string) => {
    setAdvices(advices.filter((advice) => advice.id !== id));
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
        {advices.length === 0 ? (
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
                {advice.isRemoni && (
                  <span className="text-xs font-extrabold text-blue-600 mr-1">[Remoni's Advice]</span>
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