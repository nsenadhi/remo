import { Calendar, ChevronLeft, ChevronRight, CalendarCheck } from 'lucide-react';
import { useRef, useState } from 'react';

const patientsPool = [
  { id: '00008', name: 'Kimberly Moore' },
  { id: '00009', name: 'Antonio Chapman' },
  { id: '00010', name: 'Susan Fischer' },
  { id: '00011', name: 'Jennifer Park DVM' },
  { id: '00012', name: 'Tracy Hill' },
  { id: '00013', name: 'Timothy Bush' },
  { id: '00014', name: 'Samuel Rios' },
  { id: '00015', name: 'James Thompson' },
  { id: '00016', name: 'James Coffey' },
  { id: '00017', name: 'Aaron Brown' },
  { id: '00018', name: 'Bonnie Robertson' },
  { id: '00019', name: 'Cory Martinez' },
];

const appointmentTypes = ['Follow-up', 'Consultation', 'Checkup', 'Emergency Review'];
const appointmentStatuses = ['Confirmed', 'Pending'];
const baseTimes = [
  '8:00 AM',
  '9:30 AM',
  '10:45 AM',
  '12:00 PM',
  '1:30 PM',
  '2:45 PM',
  '3:30 PM',
  '4:15 PM',
  '5:00 PM',
  '6:00 PM',
  '6:30 PM',
  '7:15 PM',
];

const appointmentsData = {
  '2026-02-02': [
    {
      id: 1,
      time: '8:00 AM',
      patientName: 'Kimberly Moore',
      patientId: '00008',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 2,
      time: '9:30 AM',
      patientName: 'Antonio Chapman',
      patientId: '00009',
      type: 'Consultation',
      status: 'Confirmed',
    },
    {
      id: 3,
      time: '10:45 AM',
      patientName: 'Susan Fischer',
      patientId: '00010',
      type: 'Checkup',
      status: 'Confirmed',
    },
    {
      id: 4,
      time: '12:00 PM',
      patientName: 'Jennifer Park DVM',
      patientId: '00011',
      type: 'Follow-up',
      status: 'Pending',
    },
    {
      id: 5,
      time: '1:30 PM',
      patientName: 'Tracy Hill',
      patientId: '00012',
      type: 'Emergency Review',
      status: 'Confirmed',
    },
    {
      id: 6,
      time: '2:45 PM',
      patientName: 'Timothy Bush',
      patientId: '00013',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 7,
      time: '3:30 PM',
      patientName: 'Samuel Rios',
      patientId: '00014',
      type: 'Consultation',
      status: 'Pending',
    },
    {
      id: 8,
      time: '4:15 PM',
      patientName: 'James Thompson',
      patientId: '00015',
      type: 'Checkup',
      status: 'Confirmed',
    },
    {
      id: 9,
      time: '5:00 PM',
      patientName: 'James Coffey',
      patientId: '00016',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 10,
      time: '6:00 PM',
      patientName: 'Aaron Brown',
      patientId: '00017',
      type: 'Consultation',
      status: 'Pending',
    },
    {
      id: 11,
      time: '6:30 PM',
      patientName: 'Bonnie Robertson',
      patientId: '00018',
      type: 'Follow-up',
      status: 'Confirmed',
    },
    {
      id: 12,
      time: '7:15 PM',
      patientName: 'Cory Martinez',
      patientId: '00019',
      type: 'Checkup',
      status: 'Pending',
    },
    {
      id: 100,
      time: '7:00 AM',
      patientName: 'Samuel Rios',
      patientId: '00014',
      type: 'Follow-up',
      status: 'Finished',
    },
    {
      id: 101,
      time: '7:30 AM',
      patientName: 'James Thompson',
      patientId: '00015',
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

const hashDate = (dateStr: string) => {
  let hash = 0;
  for (let i = 0; i < dateStr.length; i += 1) {
    hash = (hash * 31 + dateStr.charCodeAt(i)) % 100000;
  }
  return hash;
};

const timeToMinutes = (timeStr: string) => {
  const [timePart, meridiem] = timeStr.split(' ');
  const [rawHour, rawMinute] = timePart.split(':').map(Number);
  let hour = rawHour % 12;
  if (meridiem.toUpperCase() === 'PM') hour += 12;
  return hour * 60 + (rawMinute || 0);
};

const toISODateOnly = (value: Date) =>
  new Date(value.getFullYear(), value.getMonth(), value.getDate());

const generateAppointmentsForDate = (dateStr: string) => {
  const seed = hashDate(dateStr);
  const count = 8 + (seed % 4);
  const startIndex = seed % patientsPool.length;
  const items = [];
  for (let i = 0; i < count; i += 1) {
    const patient = patientsPool[(startIndex + i) % patientsPool.length];
    const type = appointmentTypes[(seed + i) % appointmentTypes.length];
    const status = appointmentStatuses[(seed + i * 3) % appointmentStatuses.length];
    items.push({
      id: Number(`${seed}`) + i + 1,
      time: baseTimes[i % baseTimes.length],
      patientName: patient.name,
      patientId: patient.id,
      type,
      status,
    });
  }

  const selectedDate = new Date(`${dateStr}T00:00:00`);
  const today = toISODateOnly(new Date());
  if (toISODateOnly(selectedDate).getTime() <= today.getTime()) {
    const finishedCount = 2;
    for (let i = 0; i < finishedCount; i += 1) {
      const patient = patientsPool[(startIndex + count + i) % patientsPool.length];
      items.push({
        id: Number(`${seed}`) + count + i + 1,
        time: baseTimes[i % baseTimes.length],
        patientName: patient.name,
        patientId: patient.id,
        type: appointmentTypes[(seed + i + 1) % appointmentTypes.length],
        status: 'Finished',
      });
    }
  }

  return items;
};

export function Appointments() {
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const dateInputRef = useRef<HTMLInputElement>(null);
  const today = new Date().toISOString().slice(0, 10);
  const [selectedDate, setSelectedDate] = useState(today);

  const rawAppointments =
    appointmentsData[selectedDate as keyof typeof appointmentsData] ||
    generateAppointmentsForDate(selectedDate);
  
  // Sort appointments: upcoming ones by time first, then finished ones at the end
  const selectedDateObj = new Date(`${selectedDate}T00:00:00`);
  const todayObj = new Date(`${today}T00:00:00`);
  const nowMinutes = (() => {
    const now = new Date();
    return now.getHours() * 60 + now.getMinutes();
  })();

  const withLiveStatus = rawAppointments.map((appointment) => {
    if (selectedDateObj.getTime() > todayObj.getTime()) {
      return appointment;
    }
    if (selectedDateObj.getTime() < todayObj.getTime()) {
      return { ...appointment, status: 'Finished' as const };
    }
    const appointmentMinutes = timeToMinutes(appointment.time);
    if (appointmentMinutes <= nowMinutes) {
      return { ...appointment, status: 'Finished' as const };
    }
    return appointment;
  });

  const appointments = [...withLiveStatus].sort((a, b) => {
    // If one is finished and the other isn't, finished goes to the end
    if (a.status === 'Finished' && b.status !== 'Finished') return 1;
    if (a.status !== 'Finished' && b.status === 'Finished') return -1;
    
    // Otherwise sort by time
    const timeA = timeToMinutes(a.time);
    const timeB = timeToMinutes(b.time);
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
    const input = dateInputRef.current;
    if (!input) return;
    if (typeof (input as any).showPicker === 'function') {
      (input as any).showPicker();
    } else {
      input.click();
      input.focus();
    }
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
