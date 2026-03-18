import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { useRef, useState } from 'react';

const appointmentsData = {
  '2026-01-22': [
    {
      id: 1,
      time: '10:00 AM',
      patientName: 'Emily Davis',
      patientId: 'P-1523',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 2,
      time: '11:30 AM',
      patientName: 'Robert Wilson',
      patientId: 'P-2891',
      type: 'Consultation',
      status: 'Confirmed',
    },
    {
      id: 3,
      time: '2:00 PM',
      patientName: 'Lisa Anderson',
      patientId: 'P-3147',
      type: 'Checkup',
      status: 'Pending',
    },
    {
      id: 4,
      time: '3:30 PM',
      patientName: 'James Martinez',
      patientId: 'P-4562',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 5,
      time: '4:15 PM',
      patientName: 'Sarah Johnson',
      patientId: 'P-2847',
      type: 'Emergency Review',
      status: 'Confirmed',
    },
    {
      id: 6,
      time: '5:00 PM',
      patientName: 'Michael Chen',
      patientId: 'P-3921',
      type: 'Follow-up',
      status: 'Pending',
    },
  ],
  '2026-01-23': [
    {
      id: 7,
      time: '9:00 AM',
      patientName: 'David Brown',
      patientId: 'P-5123',
      type: 'Checkup',
      status: 'Confirmed',
    },
    {
      id: 8,
      time: '1:00 PM',
      patientName: 'Anna Taylor',
      patientId: 'P-6234',
      type: 'Follow-up',
      status: 'Pending',
    },
    {
      id: 9,
      time: '3:00 PM',
      patientName: 'John Smith',
      patientId: 'P-7345',
      type: 'Consultation',
      status: 'Confirmed',
    },
  ],
  '2026-01-24': [
    {
      id: 10,
      time: '10:30 AM',
      patientName: 'Maria Garcia',
      patientId: 'P-8456',
      type: 'Emergency Review',
      status: 'Confirmed',
    },
    {
      id: 11,
      time: '2:30 PM',
      patientName: 'Kevin Lee',
      patientId: 'P-9567',
      type: 'Follow-up',
      status: 'Confirmed',
    },
  ],
};

export function Appointments() {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [selectedDate, setSelectedDate] = useState('2026-01-22');

  const appointments = appointmentsData[selectedDate as keyof typeof appointmentsData] || [];

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = 300;
      scrollContainerRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      weekday: 'short', 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <h2 className="font-bold text-gray-900">Upcoming Appointments</h2>
          <span className="bg-[#9C1DE7] text-white text-xs px-2 py-1 rounded-full">
            {appointments.length}
          </span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 bg-gradient-to-r from-[#581B98] to-[#9C1DE7] text-white px-3 py-2 rounded-lg">
            <Calendar className="w-4 h-4" />
            <input
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="bg-transparent text-white text-sm font-medium outline-none cursor-pointer"
              style={{
                colorScheme: 'dark',
              }}
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => scroll('left')}
              className="bg-gray-100 hover:bg-gray-200 p-2 rounded-lg transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => scroll('right')}
              className="bg-gray-100 hover:bg-gray-200 p-2 rounded-lg transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div
        ref={scrollContainerRef}
        className="flex gap-4 overflow-x-auto scrollbar-hide scroll-smooth"
        style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
      >
        {appointments.map((appointment) => (
          appointment.status === 'Finished' ? (
            <div
              key={appointment.id}
              className="min-w-[280px] p-4 bg-gray-200 border border-gray-300 rounded-xl flex-shrink-0 opacity-95"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="bg-[#9e9e9e] text-white px-3 py-1.5 rounded-md text-sm font-bold whitespace-nowrap">
                  {appointment.time}
                </div>
                <div className="bg-[#9e9e9e] text-white text-sm px-3 py-1 rounded-md font-semibold">
                  Finished
                </div>
              </div>
              <div>
                <p className="font-extrabold text-gray-800 text-lg">{appointment.patientName}</p>
                <div className="mt-2">
                  <span className="text-xs text-gray-600 mr-3">{appointment.patientId}</span>
                  <span className="text-xs text-gray-600">{appointment.type}</span>
                </div>
              </div>
            </div>
          ) : (
            <div
              key={appointment.id}
              className="min-w-[260px] p-4 bg-white border border-[#9C1DE7] rounded-xl hover:shadow-lg transition-shadow flex-shrink-0"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="bg-[#9C1DE7] text-white px-3 py-1.5 rounded-md text-sm font-bold">
                  {appointment.time}
                </div>
                <div
                  className={`text-sm px-3 py-1.5 rounded-full font-semibold whitespace-nowrap ${
                    appointment.status === 'Confirmed'
                      ? 'bg-green-500 text-white'
                      : 'bg-yellow-400 text-white'
                  }`}
                >
                  {appointment.status}
                </div>
              </div>
              <div>
                <p className="font-extrabold text-gray-900 text-lg">{appointment.patientName}</p>
                <div className="flex items-center justify-between mt-2">
                  <p className="text-xs text-gray-500">{appointment.patientId}</p>
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-[#9C1DE7]"></div>
                    <p className="text-xs text-gray-500">{appointment.type}</p>
                  </div>
                </div>
              </div>
            </div>
          )
        ))}
      </div>
    </div>
  );
}
