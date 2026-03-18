import { Calendar, ChevronLeft, ChevronRight, CalendarCheck } from 'lucide-react';
import { useRef, useState } from 'react';

const appointmentsData = {
  '2026-02-02': [
    {
      id: 1,
      time: '8:00 AM',
      patientName: 'Emily Davis',
      patientId: 'P-1523',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 2,
      time: '9:30 AM',
      patientName: 'Robert Wilson',
      patientId: 'P-2891',
      type: 'Consultation',
      status: 'Confirmed',
    },
    {
      id: 3,
      time: '10:45 AM',
      patientName: 'Lisa Anderson',
      patientId: 'P-3147',
      type: 'Checkup',
      status: 'Confirmed',
    },
    {
      id: 4,
      time: '12:00 PM',
      patientName: 'James Martinez',
      patientId: 'P-4562',
      type: 'Follow-up',
      status: 'Pending',
    },
    {
      id: 5,
      time: '1:30 PM',
      patientName: 'Sarah Johnson',
      patientId: 'P-2847',
      type: 'Emergency Review',
      status: 'Confirmed',
    },
    {
      id: 6,
      time: '2:45 PM',
      patientName: 'Michael Chen',
      patientId: 'P-3921',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 7,
      time: '3:30 PM',
      patientName: 'Anna Taylor',
      patientId: 'P-6234',
      type: 'Consultation',
      status: 'Pending',
    },
    {
      id: 8,
      time: '4:15 PM',
      patientName: 'David Brown',
      patientId: 'P-5123',
      type: 'Checkup',
      status: 'Confirmed',
    },
    {
      id: 9,
      time: '5:00 PM',
      patientName: 'Jennifer White',
      patientId: 'P-7845',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 10,
      time: '6:00 PM',
      patientName: 'Kevin Lee',
      patientId: 'P-9567',
      type: 'Consultation',
      status: 'Pending',
    },
    {
      id: 100,
      time: '7:00 AM',
      patientName: 'Thomas Clark',
      patientId: 'P-4521',
      type: 'Follow-up',
      status: 'Finished',
    },
    {
      id: 101,
      time: '7:30 AM',
      patientName: 'Maria Garcia',
      patientId: 'P-8456',
      type: 'Checkup',
      status: 'Finished',
    },
  ],
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
    {
      id: 100,
      time: '1:00 PM',
      patientName: 'Sarah Johnson',
      patientId: 'P-2847',
      type: 'Follow-up',
      status: 'Finished',
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
  const dateInputRef = useRef<HTMLInputElement>(null);
  const [selectedDate, setSelectedDate] = useState('2026-02-02');
  const today = '2026-02-02'; // Today's date

  const rawAppointments = appointmentsData[selectedDate as keyof typeof appointmentsData] || [];
  
  // Sort appointments: upcoming ones by time first, then finished ones at the end
  const appointments = [...rawAppointments].sort((a, b) => {
    // If one is finished and the other isn't, finished goes to the end
    if (a.status === 'Finished' && b.status !== 'Finished') return 1;
    if (a.status !== 'Finished' && b.status === 'Finished') return -1;
    
    // Otherwise sort by time
    const timeA = new Date(`2026-01-22 ${a.time}`).getTime();
    const timeB = new Date(`2026-01-22 ${b.time}`).getTime();
    return timeA - timeB;
  });

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

  const formatDateForDisplay = (dateStr: string) => {
    const date = new Date(dateStr);
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    const year = date.getFullYear();
    return `${month}/${day}/${year}`;
  };

  const handleDateButtonClick = () => {
    dateInputRef.current?.click();
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
          <button
            onClick={handleDateButtonClick}
            className="flex items-center gap-2 bg-gradient-to-r from-[#581B98] to-[#9C1DE7] text-white px-4 py-2 rounded-lg cursor-pointer hover:opacity-90 transition-opacity"
          >
            <Calendar className="w-4 h-4" />
            <span className="text-sm font-medium">{formatDateForDisplay(selectedDate)}</span>
            <input
              ref={dateInputRef}
              type="date"
              value={selectedDate}
              onChange={(e) => setSelectedDate(e.target.value)}
              className="absolute opacity-0 w-0 h-0 pointer-events-none"
            />
          </button>
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
        {appointments.map((appointment) => {
          const isFinished = appointment.status === 'Finished';
          
          return (
            <div
              key={appointment.id}
              className={`min-w-[220px] py-2 px-3 rounded-xl hover:shadow-md transition-shadow flex-shrink-0 ${
                isFinished 
                  ? 'bg-gray-200 border border-gray-300' 
                  : 'bg-gradient-to-br from-purple-50 to-white border border-purple-200'
              }`}
            >
              <div className="flex items-center gap-2 mb-1.5">
                <div className={`px-2.5 py-0.5 rounded-lg text-sm font-bold whitespace-nowrap ${
                  isFinished 
                    ? 'bg-gray-500 text-white' 
                    : 'bg-[#581B98] text-white'
                }`}>
                  {appointment.time}
                </div>
                <span
                  className={`text-xs px-2.5 py-0.5 rounded-lg font-semibold whitespace-nowrap ${
                    appointment.status === 'Finished'
                      ? 'bg-gray-400 text-gray-700'
                      : appointment.status === 'Confirmed'
                      ? 'bg-green-100 text-green-700'
                      : 'bg-yellow-100 text-yellow-700'
                  }`}
                >
                  {appointment.status}
                </span>
              </div>
              <div className="flex items-center gap-1">
                <p className="font-bold text-gray-900 text-sm whitespace-nowrap">
                  {appointment.patientName}
                </p>
                <p className="text-xs text-gray-600 whitespace-nowrap">{appointment.patientId}</p>
                <p className="text-xs text-gray-700 whitespace-nowrap">{appointment.type}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}