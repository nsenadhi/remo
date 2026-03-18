import { useEffect, useState } from 'react';
import { Search, ArrowRight, Users } from 'lucide-react';

const fallbackPatients = [
  {
    id: '00001',
    name: 'Emily Davis',
    age: 45,
    condition: 'Diabetes',
    lastVisit: '2025-01-18',
    status: 'Stable',
  },
  {
    id: '00002',
    name: 'Sarah Johnson',
    age: 62,
    condition: 'Hypertension',
    lastVisit: '2025-01-21',
    status: 'Critical',
  },
  {
    id: '00003',
    name: 'Robert Wilson',
    age: 38,
    condition: 'Asthma',
    lastVisit: '2025-01-20',
    status: 'Stable',
  },
  {
    id: '00004',
    name: 'Lisa Anderson',
    age: 51,
    condition: 'Arthritis',
    lastVisit: '2025-01-19',
    status: 'Stable',
  },
  {
    id: '00005',
    name: 'Michael Chen',
    age: 29,
    condition: 'Heart Condition',
    lastVisit: '2025-01-21',
    status: 'Urgent',
  },
  {
    id: '00006',
    name: 'James Martinez',
    age: 55,
    condition: 'High Cholesterol',
    lastVisit: '2025-01-17',
    status: 'Stable',
  },
  {
    id: '00007',
    name: 'Jennifer Brown',
    age: 42,
    condition: 'Thyroid',
    lastVisit: '2025-01-16',
    status: 'Stable',
  },
  {
    id: '00008',
    name: 'David Miller',
    age: 58,
    condition: 'Diabetes',
    lastVisit: '2025-01-15',
    status: 'Stable',
  },
];

const conditionOptions = [
  'Hypertension',
  'Diabetes',
  'Asthma',
  'Arthritis',
  'Heart Condition',
  'High Cholesterol',
  'Thyroid',
  'COPD',
];

const statusOptions = ['Stable', 'Urgent', 'Critical'];

const padPatientId = (value: string) => value.padStart(5, '0');

const splitCsvLine = (line: string) => {
  const result: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
      continue;
    }
    current += char;
  }
  result.push(current);
  return result.map((entry) => entry.trim());
};

const formatDateISO = (date: Date) => date.toISOString().slice(0, 10);

interface PatientsListProps {
  searchQuery: string;
  onSearchChange: (query: string) => void;
  onViewPatient: (patientId: string) => void;
}

export function PatientsList({ searchQuery, onSearchChange, onViewPatient }: PatientsListProps) {
  const [showAll, setShowAll] = useState(false);
  const [allPatients, setAllPatients] = useState(fallbackPatients);

  useEffect(() => {
    fetch('/static/local_data/fake_patient_meta_data.csv')
      .then((res) => res.text())
      .then((text) => {
        const lines = text.split(/\r?\n/).filter(Boolean);
        if (lines.length <= 1) return;
        const headers = splitCsvLine(lines.shift() || '').map((header) => header.toLowerCase());
        const idIndex = headers.indexOf('patient_id');
        const nameIndex = headers.indexOf('name');
        const ageIndex = headers.indexOf('age');
        const rows = lines
          .map((line) => splitCsvLine(line))
          .map((cols, idx) => {
            const rawId = (cols[idIndex] || '').trim();
            const id = rawId ? padPatientId(String(rawId)) : '';
            const name = (cols[nameIndex] || '').trim();
            const ageValue = Number(cols[ageIndex]);
            const age = Number.isFinite(ageValue) && ageValue > 0 ? ageValue : 30 + (idx % 40);
            const condition = conditionOptions[(Number(rawId) || idx) % conditionOptions.length];
            const status = statusOptions[(Number(rawId) || idx) % statusOptions.length];
            const lastVisitDate = new Date();
            lastVisitDate.setDate(lastVisitDate.getDate() - ((Number(rawId) || idx) % 14));
            const lastVisit = formatDateISO(lastVisitDate);
            return {
              id,
              name,
              age,
              condition,
              lastVisit,
              status,
            };
          })
          .filter((row) => row.id && row.name);
        if (rows.length) {
          setAllPatients(rows);
        }
      })
      .catch(() => {});
  }, []);

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
