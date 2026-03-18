import { MessageSquare } from 'lucide-react';

interface Advice {
  id: string;
  text: string;
  date: string;
  time: string;
}

interface PatientAdvicesViewProps {
  patientId: string;
}

export function PatientAdvicesView({ patientId }: PatientAdvicesViewProps) {
  // Mock advices data
  const advices: Advice[] = [
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
      text: 'Try to get at least 30 minutes of light exercise daily.',
      date: '2025-01-18',
      time: '9:00 AM',
    },
  ];

  return (
    <div className="bg-white rounded-lg shadow-md p-3 h-full flex flex-col overflow-hidden">
      <div className="flex items-center gap-2 mb-2">
        <MessageSquare className="w-4 h-4 text-[#9C1DE7]" />
        <h3 className="font-bold text-gray-900 text-sm">Doctor's Advices</h3>
      </div>

      {/* Advices List */}
      <div className="flex-1 overflow-y-auto space-y-2">
        {advices.length === 0 ? (
          <p className="text-gray-500 text-center py-4 text-xs">No advices from your doctor yet.</p>
        ) : (
          advices.map((advice) => (
            <div
              key={advice.id}
              className="p-2 bg-purple-50 border border-purple-200 rounded-lg"
            >
              <p className="text-gray-900 text-xs">{advice.text}</p>
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
