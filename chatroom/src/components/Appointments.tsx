import { Calendar, ChevronLeft, ChevronRight, CalendarCheck } from 'lucide-react';
import { useRef, useState } from 'react';

type Appointment = {
  id: number;
  time: string;
  patientName: string;
  patientId: string;
  type: string;
  status: string;
};

const appointmentsData: Record<string, Appointment[]> = {
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
  const today = '2026-01-22'; // Today's date

  const appointments = appointmentsData[selectedDate] || [];

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
    if (dateStr === today) {
      return 'Today';
    }
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', { 
      weekday: 'short', 
      month: 'short', 
      day: 'numeric',
      year: 'numeric'
    });
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <CalendarCheck className="w-5 h-5 text-[#9C1DE7]" />
          <h2 className="font-bold text-gray-900">Upcoming Appointments - {formatDate(selectedDate)}</h2>
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
              className="min-w-[260px] p-3 bg-gray-100 border border-gray-300 rounded-xl flex-shrink-0"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="bg-gray-600 text-white px-4 py-1.5 rounded-md text-sm font-bold uppercase tracking-wide whitespace-nowrap">
                  {appointment.time}
                </div>
                <div className="bg-gray-300 text-gray-800 text-sm px-3 py-1 rounded-md">
                  Finished
                </div>
              </div>
              <p className="font-extrabold text-gray-900 text-base">
                {appointment.patientName}
                <span className="ml-3 text-gray-400 tracking-widest">..............</span>
              </p>
            </div>
          ) : (
            <div
              key={appointment.id}
              className="min-w-[160px] py-2 px-3 bg-gradient-to-br from-purple-50 to-white border border-purple-200 rounded-lg hover:shadow-md transition-shadow flex-shrink-0"
            >
              <div className="flex items-center gap-2">
                <div className="bg-[#581B98] text-white px-2 py-0.5 rounded text-xs font-bold whitespace-nowrap">
                  {appointment.time}
                </div>
                <span
                  className={`text-xs px-2 py-0.5 rounded-full font-medium whitespace-nowrap ${
                    appointment.status === 'Confirmed'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-yellow-100 text-yellow-700'
                  }`}
                >
                  {appointment.status}
                </span>
              </div>
              <div className="mt-1.5 flex items-center gap-2">
                <p className="font-bold text-gray-900 text-sm whitespace-nowrap">
                  {appointment.patientName}
                </p>
                <p className="text-xs text-black whitespace-nowrap">{appointment.patientId}</p>
                <p className="text-xs text-black whitespace-nowrap">{appointment.type}</p>
              </div>
            </div>
          )
        ))}
      </div>
    </div>
  );
}
