import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import Icon from '../components/Icon';
import { Plus, Search, Filter, Calendar, Stethoscope, Edit, Trash2 } from 'lucide-react';

// Компоненты
import UnifiedLayout from '../components/layout/UnifiedLayout';
import { PatientCard, MetricCard, MedicalTable } from '../components/medical';
import MedicalCard from '../components/medical/MedicalCard';
import { useTheme } from '../contexts/ThemeContext';
import '../styles/full-width.css';
import '../styles/cursor-effects.css';
import '../styles/animations.css';
import '../styles/responsive.css';

/**
 * Демонстрационная страница нового дизайна MediLab
 * Показывает все новые компоненты в действии
 */
const MediLabDemo = () => {
  const { isDark } = useTheme();
  const location = useLocation();
  const [searchQuery, setSearchQuery] = useState('');

  // Определяем активную вкладку из URL
  const getCurrentTab = () => {
    const path = location.pathname;
    if (path.includes('/patients')) return 'patients';
    if (path.includes('/appointments')) return 'appointments';
    if (path.includes('/staff-schedule')) return 'staff-schedule';
    return 'dashboard';
  };

  const [activeTab, setActiveTab] = useState(getCurrentTab());

  // Обновляем активную вкладку при изменении URL
  useEffect(() => {
    setActiveTab(getCurrentTab());
  }, [location.pathname]);

  // Моковые данные для демонстрации
  const dashboardMetrics = [
    {
      title: 'Total Patients',
      value: '1,247',
      change: 12.5,
      iconName: 'Users',
      color: 'blue'
    },
    {
      title: 'Appointments',
      value: '3,421',
      change: 8.2,
      iconName: 'Calendar',
      color: 'green'
    },
    {
      title: 'Revenue',
      value: '$2.8M',
      change: 15.7,
      iconName: 'DollarSign',
      color: 'purple'
    },
    {
      title: 'Active Users',
      value: '89',
      change: -2.1,
      iconName: 'Activity',
      color: 'orange'
    }
  ];

  const patients = [
    {
      id: 1,
      name: 'Duncan Pitt',
      patientId: 'A6S9T2D0P5',
      age: 45,
      gender: 'M',
      lastVisit: '2 days ago',
      department: 'Cardiology',
      status: 'active',
      avatar: null
    },
    {
      id: 2,
      name: 'Mary Weather',
      patientId: 'R4L7Y9C2E1',
      age: 32,
      gender: 'F',
      lastVisit: '1 week ago',
      department: 'Dermatology',
      status: 'active',
      avatar: null
    },
    {
      id: 3,
      name: 'Matthew Abel',
      patientId: 'N3B8V1M4W7',
      age: 28,
      gender: 'M',
      lastVisit: '3 days ago',
      department: 'Pediatrics',
      status: 'pending',
      avatar: null
    },
    {
      id: 4,
      name: 'Gill Hames',
      patientId: 'L219K6T3C1',
      age: 55,
      gender: 'F',
      lastVisit: '1 day ago',
      department: 'Orthopedics',
      status: 'active',
      avatar: null
    },
    {
      id: 5,
      name: 'Finn McDonald',
      patientId: 'E1M7D4S9T0',
      age: 41,
      gender: 'M',
      lastVisit: '4 days ago',
      department: 'Neurology',
      status: 'urgent',
      avatar: null
    }
  ];

  const appointments = [
    {
      id: 'K8L5Z0I7F2',
      name: 'Millie Simons',
      date: '8/6/2023',
      time: '11:00',
      notes: 'Regular checkup',
      status: 'scheduled'
    },
    {
      id: 'D3X9Y2A6R1',
      name: 'Betty Haise',
      date: '13/6/2023',
      time: '09:00',
      notes: 'Follow-up appointment',
      status: 'confirmed'
    },
    {
      id: 'G5N2M1U9V4',
      name: 'Penny Minister',
      date: '16/6/2023',
      time: '08:00',
      notes: 'First visit',
      status: 'pending'
    },
    {
      id: 'J2T1W4K3PO',
      name: 'Mark Brent',
      date: '21/6/2023',
      time: '11:00',
      notes: 'Consultation',
      status: 'scheduled'
    }
  ];

  const staffSchedule = [
    {
      name: 'Boris Hahn',
      role: 'Doctor',
      shifts: [
        { start: '10:30', end: '14:30', type: 'appointment', color: 'pink' }
      ]
    },
    {
      name: 'Dominic Proque',
      role: 'Assistant',
      shifts: [
        { start: '10:00', end: '14:00', type: 'support', color: 'yellow' }
      ]
    },
    {
      name: 'Lin Tran',
      role: 'Doctor',
      shifts: [
        { start: '11:00', end: '15:00', type: 'surgery', color: 'purple' }
      ]
    },
    {
      name: 'Alicia Munoz',
      role: 'Doctor',
      shifts: [
        { start: '13:00', end: '16:30', type: 'consultation', color: 'blue' }
      ]
    }
  ];

  // Рендер дашборда
  const renderDashboard = () => (
    <div className="h-full flex flex-col w-full">
      {/* Заголовок - компактный */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            MediLab Dashboard
          </h1>
          <p className="text-sm text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Medical clinic management system
          </p>
        </div>
      </div>

      {/* Объединенная сетка - метрики и контент */}
      <div className="responsive-grid flex-1 min-h-0 w-full">
        {/* Метрики */}
        {dashboardMetrics.map((metric, index) => (
          <MetricCard
            key={index}
            title={metric.title}
            value={metric.value}
            change={metric.change}
            iconName={metric.iconName}
            color={metric.color}
            compact={true}
            className={`h-16 animate-fade-in-up animate-delay-${(index + 1) * 100} metric-card-responsive`}
          />
        ))}
        
        {/* Разделитель */}
        <div 
          className="col-span-full h-px my-4" 
          style={{ 
            backgroundColor: isDark ? '#374151' : '#e5e7eb' 
          }}
        ></div>
        
         {/* Recent Activity */}
         <MedicalCard className="h-48 animate-fade-in-left animate-delay-200 card-responsive">
           <h3 className="text-responsive-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
             Recent Activity
           </h3>
           <div className="space-y-3">
             {[
               { 
                 action: 'New patient registered', 
                 time: '2 min ago', 
                 iconName: 'User',
                 bgColor: '#0088cc',
                 iconColor: '#ffffff'
               },
               { 
                 action: 'Appointment completed', 
                 time: '15 min ago', 
                 iconName: 'Calendar',
                 bgColor: '#00a884',
                 iconColor: '#ffffff'
               },
               { 
                 action: 'Payment received', 
                 time: '1 hour ago', 
                 iconName: 'DollarSign',
                 bgColor: '#ff6b6b',
                 iconColor: '#ffffff'
               },
               { 
                 action: 'System backup completed', 
                 time: '2 hours ago', 
                 iconName: 'Activity',
                 bgColor: '#ffa726',
                 iconColor: '#ffffff'
               }
             ].map((item, index) => (
               <div key={index} className={`flex items-center gap-3 animate-fade-in-left animate-delay-${(index + 1) * 100}`}>
                 <div 
                   className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
                   style={{
                     backgroundColor: item.bgColor,
                     boxShadow: `0 2px 8px ${item.bgColor}40`
                   }}
                 >
                   <Icon
                     name={item.iconName}
                     size={24}
                     color={item.iconColor}
                   />
                 </div>
                 <div className="flex-1 min-w-0">
                   <p className="text-base font-medium truncate" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
                     {item.action}
                   </p>
                   <p className="text-sm text-gray-500" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
                     {item.time}
                   </p>
                 </div>
               </div>
             ))}
           </div>
         </MedicalCard>

         {/* Quick Actions */}
         <MedicalCard className="h-48 animate-fade-in-right animate-delay-300 card-responsive">
           <h3 className="text-responsive-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
             Quick Actions
           </h3>
           <div className="grid grid-cols-2 gap-3">
             {[
               { 
                 label: 'New Patient', 
                 iconName: 'User',
                 bgColor: '#0088cc',
                 hoverColor: '#006699'
               },
               { 
                 label: 'Schedule', 
                 iconName: 'Calendar',
                 bgColor: '#00a884',
                 hoverColor: '#008a6b'
               },
               { 
                 label: 'Reports', 
                 iconName: 'BarChart3',
                 bgColor: '#ff6b6b',
                 hoverColor: '#ff5252'
               },
               { 
                 label: 'Staff', 
                 iconName: 'Stethoscope',
                 bgColor: '#ffa726',
                 hoverColor: '#ff9800'
               }
             ].map((action, index) => (
               <button
                 key={index}
                 className={`p-4 rounded-xl text-white transition-all duration-200 text-center h-16 flex flex-col items-center justify-center hover:scale-105 animate-fade-in-scale animate-delay-${(index + 1) * 100} button-responsive`}
                 style={{
                   backgroundColor: action.bgColor,
                   boxShadow: `0 2px 8px ${action.bgColor}40`
                 }}
                 onMouseEnter={(e) => {
                   e.target.style.backgroundColor = action.hoverColor;
                   e.target.style.boxShadow = `0 4px 12px ${action.bgColor}60`;
                 }}
                 onMouseLeave={(e) => {
                   e.target.style.backgroundColor = action.bgColor;
                   e.target.style.boxShadow = `0 2px 8px ${action.bgColor}40`;
                 }}
                 aria-label={`${action.label} action`}
               >
                 <Icon
                   name={action.iconName}
                   size={24}
                   className="mb-2"
                 />
                 <span className="text-sm font-semibold">{action.label}</span>
               </button>
             ))}
           </div>
         </MedicalCard>

         {/* Today's Summary */}
         <MedicalCard className="h-48 animate-fade-in-scale animate-delay-400 card-responsive">
           <h3 className="text-responsive-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
             Today&apos;s Summary
           </h3>
           <div className="space-y-3">
             <div className="flex justify-between items-center animate-fade-in-left animate-delay-100">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Appointments</span>
               <span className="text-base font-semibold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>24</span>
             </div>
             <div className="flex justify-between items-center animate-fade-in-left animate-delay-200">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Completed</span>
               <span className="text-base font-semibold text-green-600">18</span>
             </div>
             <div className="flex justify-between items-center animate-fade-in-left animate-delay-300">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Pending</span>
               <span className="text-base font-semibold text-yellow-600">6</span>
             </div>
             <div className="flex justify-between items-center animate-fade-in-left animate-delay-400">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Revenue</span>
               <span className="text-base font-semibold text-green-600">$12,450</span>
             </div>
           </div>
         </MedicalCard>

         {/* Additional Stats */}
         <MedicalCard className="h-48 animate-fade-in-left animate-delay-500 card-responsive">
           <h3 className="text-responsive-lg font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
             Performance
           </h3>
           <div className="space-y-3">
             <div className="flex justify-between items-center animate-fade-in-right animate-delay-100">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Efficiency</span>
               <span className="text-base font-semibold text-green-600">94%</span>
             </div>
             <div className="flex justify-between items-center animate-fade-in-right animate-delay-200">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Satisfaction</span>
               <span className="text-base font-semibold text-blue-600">4.8/5</span>
             </div>
             <div className="flex justify-between items-center animate-fade-in-right animate-delay-300">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Wait Time</span>
               <span className="text-base font-semibold text-orange-600">12 min</span>
             </div>
             <div className="flex justify-between items-center animate-fade-in-right animate-delay-400">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Capacity</span>
               <span className="text-base font-semibold text-purple-600">78%</span>
             </div>
           </div>
         </MedicalCard>

         {/* System Status */}
         <MedicalCard className="h-48">
           <h3 className="text-base font-semibold mb-4" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
             System Status
           </h3>
           <div className="space-y-3">
             <div className="flex justify-between items-center">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Server</span>
               <span className="text-base font-semibold text-green-600">Online</span>
             </div>
             <div className="flex justify-between items-center">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Database</span>
               <span className="text-base font-semibold text-green-600">Healthy</span>
             </div>
             <div className="flex justify-between items-center">
               <span className="text-base" style={{ color: isDark ? '#cbd5e1' : '#64748b' }}>Backup</span>
               <span className="text-base font-semibold text-blue-600">2h ago</span>
             </div>
           </div>
         </MedicalCard>
      </div>
    </div>
  );

  // Рендер пациентов
  const renderPatients = () => (
    <div className="h-full flex flex-col w-full">
      {/* Заголовок - компактный */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Patients Directory
          </h1>
          <p className="text-sm text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Manage patient records and information
          </p>
        </div>
        <button 
          className="px-4 py-2 bg-gradient-to-r from-blue-600 to-blue-700 text-white rounded-lg hover:from-blue-700 hover:to-blue-800 transition-all duration-200 text-sm font-medium shadow-md hover:shadow-lg flex items-center gap-2 interactive-element hover-lift ripple-effect action-button-hover focus-ring"
          style={{
            boxShadow: '0 4px 6px -1px rgba(59, 130, 246, 0.3)'
          }}
          aria-label="Add new patient"
        >
          <Plus className="h-4 w-4" />
          Add New Patient
        </button>
      </div>

      {/* Поиск и фильтры - компактные */}
      <div className="mb-4">
        <div className="flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              placeholder="Search patients..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent text-sm"
              style={{
                backgroundColor: isDark ? '#1e293b' : '#ffffff',
                borderColor: isDark ? '#334155' : '#d1d5db',
                color: isDark ? '#f8fafc' : '#374151'
              }}
            />
          </div>
          <button className="px-3 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors text-sm interactive-element hover-lift ripple-effect magnetic-hover focus-ring" aria-label="Filter patients">
            <Filter className="h-4 w-4 mr-1" />
            Filter
          </button>
        </div>
      </div>

      {/* Карточки пациентов - на всю ширину */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-3 flex-1 overflow-y-auto w-full">
        {patients.map((patient) => (
          <PatientCard
            key={patient.id}
            patient={patient}
            onView={(patient) => console.log('View patient:', patient)}
            onEdit={(patient) => console.log('Edit patient:', patient)}
            onDelete={(patient) => console.log('Delete patient:', patient)}
            className="h-40"
          />
        ))}
      </div>
    </div>
  );

  // Рендер записей
  const renderAppointments = () => (
    <div className="h-full flex flex-col w-full">
      {/* Заголовок - компактный */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Appointments
          </h1>
          <p className="text-sm text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Manage patient appointments and schedule
          </p>
        </div>
        <div className="flex gap-2">
          <button 
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 transition-all duration-200 text-sm font-medium flex items-center gap-2 interactive-element hover-lift ripple-effect magnetic-hover focus-ring"
            style={{ 
              borderColor: isDark ? '#374151' : '#d1d5db',
              color: isDark ? '#f9fafb' : '#374151'
            }}
            aria-label="Switch to calendar view"
          >
            <Calendar className="h-4 w-4" />
            Calendar View
          </button>
          <button 
            className="px-4 py-2 bg-gradient-to-r from-green-600 to-green-700 text-white rounded-lg hover:from-green-700 hover:to-green-800 transition-all duration-200 text-sm font-medium shadow-md hover:shadow-lg flex items-center gap-2 interactive-element hover-lift ripple-effect action-button-hover focus-ring"
            style={{
              boxShadow: '0 4px 6px -1px rgba(34, 197, 94, 0.3)'
            }}
            aria-label="Create new appointment"
          >
            <Plus className="h-4 w-4" />
            New Appointment
          </button>
        </div>
      </div>

      {/* Таблица записей - на всю ширину */}
      <div className="flex-1 min-h-0 w-full">
        <MedicalCard className="h-full">
          <MedicalTable
            columns={[
              { key: 'id', label: 'ID' },
              { key: 'name', label: 'Name' },
              { key: 'date', label: 'Date' },
              { key: 'time', label: 'Time' },
              { key: 'notes', label: 'Notes' },
              { 
                key: 'status', 
                label: 'Status',
                render: (value) => (
                  <span 
                    className={`px-2 py-1 rounded-full text-xs ${
                      value === 'confirmed' ? 'bg-green-100 text-green-800' :
                      value === 'scheduled' ? 'bg-blue-100 text-blue-800' :
                      'bg-yellow-100 text-yellow-800'
                    }`}
                  >
                    {value}
                  </span>
                )
              }
            ]}
            data={appointments}
            onView={(appointment) => console.log('View appointment:', appointment)}
            onEdit={(appointment) => console.log('Edit appointment:', appointment)}
            onDelete={(appointment) => console.log('Delete appointment:', appointment)}
            pagination={false}
          />
        </MedicalCard>
      </div>
    </div>
  );

  // Рендер расписания персонала
  const renderStaffSchedule = () => (
    <div className="h-full flex flex-col w-full">
      {/* Заголовок - компактный */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
            Staff Schedule
          </h1>
          <p className="text-sm text-gray-600" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
            Manage staff shifts and schedules
          </p>
        </div>
        <button 
          className="px-4 py-2 bg-gradient-to-r from-purple-600 to-purple-700 text-white rounded-lg hover:from-purple-700 hover:to-purple-800 transition-all duration-200 text-sm font-medium shadow-md hover:shadow-lg flex items-center gap-2 interactive-element hover-lift ripple-effect action-button-hover focus-ring"
          style={{
            boxShadow: '0 4px 6px -1px rgba(147, 51, 234, 0.3)'
          }}
          aria-label="Add new staff shift"
        >
          <Plus className="h-4 w-4" />
          Add Shift
        </button>
      </div>

      {/* Расписание - на всю ширину */}
      <div className="flex-1 min-h-0 w-full">
        <MedicalCard className="h-full">
          <div className="mb-3">
            <h3 className="text-base font-semibold mb-1" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
              June, Friday 5th 2023
            </h3>
            <p className="text-xs font-medium" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
              Emergency shift
            </p>
          </div>

          {/* Временная шкала - на всю ширину */}
          <div className="mb-3">
            <div className="flex items-center gap-8 text-xs" style={{ color: isDark ? '#94a3b8' : '#6b7280' }}>
              {['10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'].map((time) => (
                <div key={time} className="text-center">
                  <div 
                    className="w-12 h-0.5 mb-1"
                    style={{ backgroundColor: isDark ? '#4b5563' : '#d1d5db' }}
                  ></div>
                  <span className="text-xs">{time}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Расписание персонала - на всю ширину */}
          <div className="space-y-3">
            {staffSchedule.map((staff, index) => (
              <div key={index} className="flex items-center gap-4">
                <div className="w-32 flex-shrink-0">
                  <div className="flex items-center gap-2">
                    <div 
                      className="w-8 h-8 rounded-full flex items-center justify-center"
                      style={{
                        backgroundColor: isDark ? '#1e3a8a' : '#dbeafe'
                      }}
                    >
                      <Stethoscope 
                        className="h-4 w-4" 
                        style={{ color: isDark ? '#60a5fa' : '#2563eb' }}
                      />
                    </div>
                    <div>
                      <p className="text-sm font-medium" style={{ color: isDark ? '#f8fafc' : '#1e293b' }}>
                        {staff.name}
                      </p>
                      <p className="text-xs text-gray-500" style={{ color: isDark ? '#94a3b8' : '#64748b' }}>
                        {staff.role}
                      </p>
                    </div>
                  </div>
                </div>
                
                <div className="flex-1 relative">
                  <div 
                    className="h-8 rounded relative"
                    style={{
                      backgroundColor: isDark ? '#374151' : '#f3f4f6'
                    }}
                  >
                    {staff.shifts.map((shift, shiftIndex) => (
                      <div
                        key={shiftIndex}
                        className="absolute h-full rounded flex items-center justify-between px-2"
                        style={{
                          left: `${((parseInt(shift.start.split(':')[0]) - 10) / 7) * 100}%`,
                          width: `${((parseInt(shift.end.split(':')[0]) - parseInt(shift.start.split(':')[0])) / 7) * 100}%`,
                          backgroundColor: shift.color === 'pink' ? (isDark ? '#7c2d12' : '#fce7f3') :
                                         shift.color === 'yellow' ? (isDark ? '#78350f' : '#fef3c7') :
                                         shift.color === 'purple' ? (isDark ? '#581c87' : '#e9d5ff') :
                                         shift.color === 'blue' ? (isDark ? '#1e3a8a' : '#dbeafe') : 
                                         (isDark ? '#374151' : '#f3f4f6')
                        }}
                      >
                        <span className="text-xs font-medium">
                          {shift.start}-{shift.end}
                        </span>
                        <div className="flex gap-1">
                          <button 
                            className="p-1 rounded interactive-element hover-scale ripple-effect magnetic-hover focus-ring" 
                            aria-label="Edit shift"
                            style={{
                              backgroundColor: 'transparent'
                            }}
                            onMouseEnter={(e) => {
                              e.target.style.backgroundColor = isDark ? '#4b5563' : '#ffffff';
                            }}
                            onMouseLeave={(e) => {
                              e.target.style.backgroundColor = 'transparent';
                            }}
                          >
                            <Edit className="h-4 w-4" />
                          </button>
                          <button 
                            className="p-1 rounded interactive-element hover-scale ripple-effect magnetic-hover focus-ring" 
                            aria-label="Delete shift"
                            style={{
                              backgroundColor: 'transparent'
                            }}
                            onMouseEnter={(e) => {
                              e.target.style.backgroundColor = isDark ? '#4b5563' : '#ffffff';
                            }}
                            onMouseLeave={(e) => {
                              e.target.style.backgroundColor = 'transparent';
                            }}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </MedicalCard>
      </div>
    </div>
  );

  // Основной рендер контента
  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return renderDashboard();
      case 'patients':
        return renderPatients();
      case 'appointments':
        return renderAppointments();
      case 'staff-schedule':
        return renderStaffSchedule();
      default:
        return renderDashboard();
    }
  };

  return (
    <UnifiedLayout showSidebar={true}>
      {renderContent()}
    </UnifiedLayout>
  );
};

export default MediLabDemo;
