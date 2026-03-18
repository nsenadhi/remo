import { useState } from 'react';
import { Search, ArrowRight, Users } from 'lucide-react';

const allPatients = [
  {
    id: 'P-1523',
    name: 'Emily Davis',
    age: 45,
    condition: 'Diabetes',
    lastVisit: '2025-01-18',
    status: 'Stable',
  },
  {
    id: 'P-2847',
    name: 'Sarah Johnson',
    age: 62,
    condition: 'Hypertension',
    lastVisit: '2025-01-21',
    status: 'Critical',
  },
  {
    id: 'P-2891',
    name: 'Robert Wilson',
    age: 38,
    condition: 'Asthma',
    lastVisit: '2025-01-20',
    status: 'Stable',
  },
  {
    id: 'P-3147',
    name: 'Lisa Anderson',
    age: 51,
    condition: 'Arthritis',
    lastVisit: '2025-01-19',
    status: 'Stable',
  },
  {
    id: 'P-3921',
    name: 'Michael Chen',
    age: 29,
    condition: 'Heart Condition',
    lastVisit: '2025-01-21',
    status: 'Urgent',
  },
  {
    id: 'P-4562',
    name: 'James Martinez',
    age: 55,
    condition: 'High Cholesterol',
    lastVisit: '2025-01-17',
    status: 'Stable',
  },
  {
    id: 'P-5123',
    name: 'Jennifer Brown',
    age: 42,
    condition: 'Thyroid',
    lastVisit: '2025-01-16',
    status: 'Stable',
  },
  {
    id: 'P-6234',
    name: 'David Miller',
    age: 58,
    condition: 'Diabetes',
    lastVisit: '2025-01-15',
    status: 'Stable',
  },
];

interface PatientsListProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onViewPatient: (patientId: string) => void;
}

export function PatientsList({ searchQuery, onSearchChange, onViewPatient }: PatientsListProps) {
  const [showAll, setShowAll] = useState(false);

  const filteredPatients = allPatients.filter(
    (patient) =>
      patient.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      patient.id.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const displayedPatients = showAll ? filteredPatients : filteredPatients.slice(0, 6);

  const handleGotoPatient = (patientId: string) => {
    onViewPatient(patientId);
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Users className="w-5 h-5 text-[#9C1DE7]" />
          <h2 className="font-bold text-gray-900">Assigned Patients</h2>
          <span className="bg-[#9C1DE7] text-white text-xs px-2 py-1 rounded-full">
            {filteredPatients.length}
          </span>
        </div>
      </div>

      {/* Search Bar */}
      <div className="mb-4 relative">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
        <input
          type="text"
          placeholder="Search by patient name or ID..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9C1DE7] focus:border-transparent"
        />
      </div>

      {/* Patients Table */}
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">
                Patient ID
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">
                Patient Name
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">
                Age
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">
                Condition
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">
                Last Visit
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">
                Status
              </th>
              <th className="px-4 py-3 text-left text-xs font-semibold text-gray-600 uppercase">
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {displayedPatients.map((patient) => (
              <tr
                key={patient.id}
                className="border-b border-gray-100 hover:bg-gray-50 transition-colors"
              >
                <td className="px-4 py-3 text-sm font-medium text-[#581B98]">
                  {patient.id}
                </td>
                <td className="px-4 py-3 text-sm font-semibold text-gray-900">
                  {patient.name}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">{patient.age}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{patient.condition}</td>
                <td className="px-4 py-3 text-sm text-gray-600">{patient.lastVisit}</td>
                <td className="px-4 py-3">
                  <span
                    className={`text-xs px-2 py-1 rounded-full font-medium ${
                      patient.status === 'Critical'
                        ? 'bg-red-100 text-red-700'
                        : patient.status === 'Urgent'
                        ? 'bg-orange-100 text-orange-700'
                        : 'bg-green-100 text-green-700'
                    }`}
                  >
                    {patient.status}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button
                    onClick={() => handleGotoPatient(patient.id)}
                    className="text-[#581B98] hover:text-[#9C1DE7] font-medium text-sm flex items-center gap-1 transition-colors"
                  >
                    <span>Go to Patient Dashboard</span>
                    <ArrowRight className="w-4 h-4" />
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        
        {filteredPatients.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            No patients found matching your search.
          </div>
        )}
      </div>

      {/* See All Assigned Patients Button */}
      {filteredPatients.length > 6 && (
        <div className="mt-4 text-center">
          <button
            onClick={() => setShowAll(!showAll)}
            className="bg-[#581B98] hover:bg-[#9C1DE7] text-white px-6 py-3 rounded-lg font-semibold transition-colors"
          >
            {showAll ? 'Show Less' : `See All Assigned Patients (${filteredPatients.length})`}
          </button>
        </div>
      )}
    </div>
  );
}