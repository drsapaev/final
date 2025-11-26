import React, { useState, useEffect } from 'react';
import { 
  Button, 
  Input, 
  Card, 
  CardHeader, 
  CardTitle, 
  CardDescription, 
  CardContent, 
  CardFooter,
  Modal, 
  Tooltip, 
  Icon, 
  Badge, 
  Progress, 
  CircularProgress,
  Sidebar, 
  Checkbox,
  Radio,
  Switch,
  Select,
  SegmentedControl,
  Textarea,
  Toast,
  ToastContainer
} from '../ui/macos';
import AccentPicker from '../ui/macos/AccentPicker.jsx';

/**
 * macOS UI Demo Component
 * Showcases all macOS-style components in action
 */
const MacOSDemo = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeSidebarItem, setActiveSidebarItem] = useState('dashboard');
  const [segmentedValue, setSegmentedValue] = useState('all');
  const [textareaValue, setTextareaValue] = useState('');
  const [toasts, setToasts] = useState([]);
  const [isDarkMode, setIsDarkMode] = useState(false);
  
  // Tab states for demo
  const [activeTab1, setActiveTab1] = useState('tab1-2');
  const [activeTab2, setActiveTab2] = useState('tab2-3');
  const [activeTab3, setActiveTab3] = useState('tab3-2');

  // Detect system theme preference
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    const systemIsDark = mediaQuery.matches;
    setIsDarkMode(systemIsDark);
    
    // Initialize theme classes
    document.documentElement.style.colorScheme = systemIsDark ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', systemIsDark ? 'dark' : 'light');
    
    if (systemIsDark) {
      document.documentElement.classList.add('dark-theme');
      document.documentElement.classList.remove('light-theme');
    } else {
      document.documentElement.classList.add('light-theme');
      document.documentElement.classList.remove('dark-theme');
    }
    
    const handleChange = (e) => {
      const newIsDark = e.matches;
      setIsDarkMode(newIsDark);
      
      document.documentElement.style.colorScheme = newIsDark ? 'dark' : 'light';
      document.documentElement.setAttribute('data-theme', newIsDark ? 'dark' : 'light');
      
      if (newIsDark) {
        document.documentElement.classList.add('dark-theme');
        document.documentElement.classList.remove('light-theme');
      } else {
        document.documentElement.classList.add('light-theme');
        document.documentElement.classList.remove('dark-theme');
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, []);

  // Toggle dark mode with system integration
  const toggleDarkMode = () => {
    const newDarkMode = !isDarkMode;
    setIsDarkMode(newDarkMode);
    
    // Update system color scheme and theme class
    document.documentElement.style.colorScheme = newDarkMode ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newDarkMode ? 'dark' : 'light');
    
    // Force CSS variables update
    if (newDarkMode) {
      document.documentElement.classList.add('dark-theme');
      document.documentElement.classList.remove('light-theme');
    } else {
      document.documentElement.classList.add('light-theme');
      document.documentElement.classList.remove('dark-theme');
    }
  };

  const showToast = (type, message) => {
    const id = Math.random().toString(36).slice(2);
    setToasts(prev => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  const sidebarItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'house' },
    { id: 'patients', label: 'Patients', icon: 'person', badge: '12' },
    { id: 'appointments', label: 'Appointments', icon: 'calendar' },
    { id: 'reports', label: 'Reports', icon: 'chart.bar' },
    { id: 'settings', label: 'Settings', icon: 'gear' }
  ];

  return (
    <div style={{
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      background: 'var(--mac-gradient-window)',
      minHeight: '100vh',
      padding: '0',
      overflowX: 'hidden',
      overflowY: 'auto',
      display: 'flex',
      flexDirection: 'column',
      color: 'var(--mac-text-primary)',
      transition: 'background var(--mac-duration-normal) var(--mac-ease)'
    }}>
          {/* Custom Header с иконками */}
          <div style={{
            padding: '12px 0 0 0',
            backgroundColor: 'transparent'
          }}>
            <header style={{
              backgroundColor: 'var(--mac-bg-toolbar)',
              borderBottom: '1px solid var(--mac-separator)',
              borderRadius: 'var(--mac-radius-md)',
              boxShadow: 'var(--mac-shadow-sm)',
              backdropFilter: 'var(--mac-blur-light)',
              WebkitBackdropFilter: 'var(--mac-blur-light)',
              height: '54px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0 12px',
              position: 'sticky',
              top: '12px',
              margin: '0 12px',
              zIndex: 100
            }}>
              {/* Left section - Title */}
              <div style={{ 
                display: 'flex', 
                alignItems: 'center', 
                gap: '8px',
                flex: 1
              }}>
                <h1 style={{
                  fontSize: '15px',
                  fontWeight: '600',
                  color: 'var(--mac-text-primary)',
                  margin: 0
                }}>
                  macOS Medical Dashboard
                </h1>
                <Badge variant="secondary">Demo</Badge>
              </div>

              {/* Center section - Actions */}
              <div style={{ 
                display: 'flex', 
                gap: '8px',
                alignItems: 'center'
              }}>
                <Button 
                  variant="primary" 
                  size="small" 
                  onClick={() => showToast('success', 'Patient created!')}
                  style={{ fontWeight: '600', display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Icon name="plus" size="small" style={{ color: 'white' }} />
                  New Patient
                </Button>
                
                <Button 
                  variant="outline" 
                  size="small" 
                  onClick={() => showToast('info', 'Search initiated')}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Icon name="magnifyingglass" size="small" style={{ color: '#007aff' }} />
                  Search
                </Button>
                
                <Button 
                  variant="secondary" 
                  size="small" 
                  onClick={() => showToast('warning', 'Settings opened')}
                  style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
                >
                  <Icon name="gear" size="small" style={{ color: '#8e8e93' }} />
                  Settings
                </Button>
              </div>

              {/* Right section - Accent & Theme */}
              <div style={{ 
                display: 'flex', 
                gap: '8px',
                alignItems: 'center',
                marginLeft: '12px'
              }}>
                <AccentPicker />
                <Button 
                  variant="ghost" 
                  size="small" 
                  onClick={toggleDarkMode}
                  style={{
                    width: '32px',
                    height: '32px',
                    padding: 0,
                    borderRadius: '6px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center'
                  }}
                  title={`Switch to ${isDarkMode ? 'light' : 'dark'} mode`}
                >
                  <Icon name={isDarkMode ? 'sun' : 'moon'} size="small" style={{ color: isDarkMode ? '#ff9500' : '#5ac8fa' }} />
                </Button>
              </div>
            </header>
          </div>

      <div style={{ 
        display: 'flex', 
        gap: '20px', 
        marginTop: '0px', // Убираем marginTop, так как отступ уже есть в хедере
        flex: 1,
        minHeight: 0,
        overflow: 'hidden',
        padding: '0 0 16px 0' // Убираем боковые отступы
      }}>
            {/* Sidebar с отступом */}
            <div style={{
              marginTop: '20px', // Увеличиваем отступ сверху для сайдбара от хедера
              flexShrink: 0
            }}>
              <Sidebar
                items={sidebarItems}
                activeItem={activeSidebarItem}
                onItemClick={(item) => setActiveSidebarItem(item.id)}
                header="Medical System"
                style={{
                  background: 'var(--mac-gradient-sidebar)',
                  borderRight: '1px solid var(--mac-separator)',
                  borderRadius: 'var(--mac-radius-md)',
                  backdropFilter: 'var(--mac-blur-light)',
                  WebkitBackdropFilter: 'var(--mac-blur-light)'
                }}
              />
            </div>

        {/* Main Content */}
        <div style={{ 
          flex: 1,
          overflow: 'auto',
          paddingRight: '10px',
          marginTop: '20px', // Добавляем отступ сверху для контента, чтобы он был на том же уровне, что и сайдбар
          minHeight: 0,
          scrollbarWidth: 'thin',
          scrollbarColor: 'var(--mac-border) transparent'
        }}>
          <style>{`
            div::-webkit-scrollbar {
              width: 8px;
            }
            div::-webkit-scrollbar-track {
              background: transparent;
            }
            div::-webkit-scrollbar-thumb {
              background: var(--mac-border);
              border-radius: 4px;
            }
            div::-webkit-scrollbar-thumb:hover {
              background: var(--mac-text-secondary);
            }
          `}</style>
          {/* Demo Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: '20px',
            marginBottom: '20px',
            paddingBottom: '40px'
          }}>
            {/* Button Demo */}
            <Card>
              <CardHeader>
                <CardTitle>Button Components</CardTitle>
                <CardDescription>Various button styles and states</CardDescription>
              </CardHeader>
              <CardContent>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <Button variant="primary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Icon name="plus" size="small" style={{ color: 'white' }} />
                    Primary
                  </Button>
                  <Button variant="secondary" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Icon name="gear" size="small" style={{ color: '#8e8e93' }} />
                    Secondary
                  </Button>
                  <Button variant="outline" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Icon name="square.and.arrow.up" size="small" style={{ color: '#007aff' }} />
                    Outline
                  </Button>
                  <Button variant="ghost" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Icon name="eye" size="small" style={{ color: '#34c759' }} />
                    Ghost
                  </Button>
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <Button variant="success" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Icon name="checkmark.circle" size="small" style={{ color: '#34c759' }} />
                    Success
                  </Button>
                  <Button variant="warning" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Icon name="exclamationmark.triangle" size="small" style={{ color: '#ff9500' }} />
                    Warning
                  </Button>
                  <Button variant="danger" style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <Icon name="trash" size="small" style={{ color: '#ff3b30' }} />
                    Danger
                  </Button>
                </div>
                </div>
              </CardContent>
            </Card>

            {/* Input Demo */}
            <Card>
              <CardHeader>
                <CardTitle>Input Components</CardTitle>
                <CardDescription>Text inputs with validation</CardDescription>
              </CardHeader>
              <CardContent>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <Input
                    label="Patient Name"
                    placeholder="Enter patient name"
                    hint="Full name as on ID"
                  />
                  <Input
                    label="Email Address"
                    type="email"
                    placeholder="patient@example.com"
                    error="Invalid email format"
                  />
                  <Input
                    label="Phone Number"
                    type="tel"
                    placeholder="+1 (555) 123-4567"
                    disabled
                  />
                </div>
              </CardContent>
            </Card>

            {/* Progress Demo */}
            <Card>
              <CardHeader>
                <CardTitle>Progress Indicators</CardTitle>
                <CardDescription>Loading states and progress bars</CardDescription>
              </CardHeader>
              <CardContent>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                  <div>
                    <div style={{ marginBottom: '8px', fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                      Treatment Progress
                    </div>
                    <Progress value={75} max={100} showValue />
                  </div>
                  <div>
                    <div style={{ marginBottom: '8px', fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                      Data Sync
                    </div>
                    <Progress value={45} max={100} variant="primary" />
                  </div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <CircularProgress value={85} size="small" />
                    <span style={{ fontSize: '11px', color: 'var(--mac-text-secondary)' }}>85%</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Form Controls Demo */}
          <Card style={{ marginBottom: '24px' }}>
            <CardHeader>
              <CardTitle>Form Controls</CardTitle>
              <CardDescription>Complete set of macOS form components</CardDescription>
            </CardHeader>
            <CardContent>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '24px' }}>
                <div style={{ display: 'grid', gap: '16px' }}>
                  <h4 style={{ margin: 0, fontSize: '13px', color: 'var(--mac-text-secondary)', fontWeight: '600' }}>Checkboxes</h4>
                  <Checkbox label="Receive notifications" description="Email and push" defaultChecked />
                  <Checkbox label="Enable auto-backup" />
                  <Checkbox label="Sync with cloud" disabled />
                </div>
                
                <div style={{ display: 'grid', gap: '16px' }}>
                  <h4 style={{ margin: 0, fontSize: '13px', color: 'var(--mac-text-secondary)', fontWeight: '600' }}>Radio Buttons</h4>
                  <Radio name="priority" value="normal" label="Normal Priority" defaultChecked />
                  <Radio name="priority" value="urgent" label="Urgent Priority" />
                  <Radio name="priority" value="low" label="Low Priority" />
                </div>
                
                <div style={{ display: 'grid', gap: '16px' }}>
                  <h4 style={{ margin: 0, fontSize: '13px', color: 'var(--mac-text-secondary)', fontWeight: '600' }}>Switches</h4>
                  <Switch label="Dark Mode" />
                  <Switch label="Push Notifications" defaultChecked />
                  <Switch label="Auto-save" />
                </div>
                
                <div style={{ display: 'grid', gap: '16px' }}>
                  <h4 style={{ margin: 0, fontSize: '13px', color: 'var(--mac-text-secondary)', fontWeight: '600' }}>Select Dropdown</h4>
                  <Select
                    label="Department"
                    options={[
                      { value: 'cardio', label: 'Cardiology' },
                      { value: 'derma', label: 'Dermatology' },
                      { value: 'dental', label: 'Dentistry' },
                      { value: 'lab', label: 'Laboratory' }
                    ]}
                    placeholder="Choose department"
                  />
                </div>
              </div>
              
              <div style={{ marginTop: '32px', display: 'grid', gap: '20px' }}>
                <div>
                  <h4 style={{ margin: '0 0 16px 0', fontSize: '13px', color: 'var(--mac-text-secondary)', fontWeight: '600' }}>Segmented Control</h4>
                  <SegmentedControl
                    options={[
                      { value: 'all', label: 'All Patients' },
                      { value: 'active', label: 'Active' },
                      { value: 'pending', label: 'Pending' },
                      { value: 'completed', label: 'Completed' }
                    ]}
                    value={segmentedValue}
                    onChange={setSegmentedValue}
                  />
                </div>
                
                <div>
                  <h4 style={{ margin: '0 0 16px 0', fontSize: '13px', color: 'var(--mac-text-secondary)', fontWeight: '600' }}>Textarea</h4>
                  <Textarea
                    label="Patient Notes"
                    placeholder="Enter detailed patient notes..."
                    hint="Include symptoms, diagnosis, and treatment plan"
                    value={textareaValue}
                    onChange={(e) => setTextareaValue(e.target.value)}
                    minRows={3}
                    maxRows={8}
                    autoResize
                    maxLength={500}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Tab System Demo */}
          <Card style={{ marginBottom: '40px' }}>
            <CardHeader>
              <CardTitle>Tab System Variants</CardTitle>
              <CardDescription>Three different macOS tab styles for visual comparison</CardDescription>
            </CardHeader>
            <CardContent>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
                
                {/* Variant 1: Underline Style (Safari-like) */}
                <div>
                  <h4 style={{ 
                    margin: '0 0 16px 0', 
                    fontSize: '13px', 
                    color: 'var(--mac-text-secondary)', 
                    fontWeight: '600' 
                  }}>
                    Variant 1: Underline Style (Safari-like)
                  </h4>
                  <div style={{ 
                    display: 'flex', 
                    marginBottom: '24px',
                    borderBottom: '1px solid var(--mac-border)'
                  }}>
                    {[
                      { id: 'tab1-1', label: 'Overview', icon: 'house' },
                      { id: 'tab1-2', label: 'Patients', icon: 'person' },
                      { id: 'tab1-3', label: 'Reports', icon: 'chart.bar' },
                      { id: 'tab1-4', label: 'Settings', icon: 'gear' }
                    ].map((tab) => {
                      const isActive = tab.id === activeTab1;
                      
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab1(tab.id)}
                          style={{
                            padding: '12px 20px',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
                            fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                            fontSize: 'var(--mac-font-size-sm)',
                            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                            position: 'relative',
                            borderBottom: isActive ? '2px solid var(--mac-accent-blue)' : '2px solid transparent',
                            marginBottom: '-1px'
                          }}
                          onMouseEnter={(e) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-primary)';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-secondary)';
                            }
                          }}
                        >
                          <Icon name={tab.icon} size="small" style={{ 
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
                          }} />
                          {tab.label}
                        </button>
                      );
                    })}
                  </div>
                  
                  {/* Active tab indicator */}
                  <div style={{
                    padding: '12px',
                    backgroundColor: 'var(--mac-bg-tertiary)',
                    borderRadius: 'var(--mac-radius-sm)',
                    fontSize: '12px',
                    color: 'var(--mac-text-secondary)',
                    fontFamily: 'SF Mono, Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace'
                  }}>
                    Active: <strong style={{ color: 'var(--mac-accent-blue)' }}>
                      {[
                        { id: 'tab1-1', label: 'Overview' },
                        { id: 'tab1-2', label: 'Patients' },
                        { id: 'tab1-3', label: 'Reports' },
                        { id: 'tab1-4', label: 'Settings' }
                      ].find(tab => tab.id === activeTab1)?.label}
                    </strong>
                  </div>
                </div>

                {/* Variant 2: Colored Bar Style (Finder-like) */}
                <div>
                  <h4 style={{ 
                    margin: '0 0 16px 0', 
                    fontSize: '13px', 
                    color: 'var(--mac-text-secondary)', 
                    fontWeight: '600' 
                  }}>
                    Variant 2: Colored Bar Style (Finder-like)
                  </h4>
                  <div style={{ 
                    display: 'flex', 
                    marginBottom: '24px'
                  }}>
                    {[
                      { id: 'tab2-1', label: 'Dashboard', icon: 'house' },
                      { id: 'tab2-2', label: 'Analytics', icon: 'chart.bar' },
                      { id: 'tab2-3', label: 'Users', icon: 'person' },
                      { id: 'tab2-4', label: 'System', icon: 'gear' }
                    ].map((tab) => {
                      const isActive = tab.id === activeTab2;
                      
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab2(tab.id)}
                          style={{
                            padding: '12px 20px',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
                            fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                            fontSize: 'var(--mac-font-size-sm)',
                            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                            position: 'relative',
                            marginBottom: '-1px'
                          }}
                          onMouseEnter={(e) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-primary)';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-secondary)';
                            }
                          }}
                        >
                          <Icon name={tab.icon} size="small" style={{ 
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
                          }} />
                          {tab.label}
                          {isActive && (
                            <div style={{
                              position: 'absolute',
                              bottom: '0',
                              left: '0',
                              right: '0',
                              height: '3px',
                              backgroundColor: 'var(--mac-accent-blue)',
                              borderRadius: '2px 2px 0 0'
                            }} />
                          )}
                        </button>
                      );
                    })}
                  </div>
                  <div style={{ 
                    borderBottom: '1px solid var(--mac-border)',
                    marginBottom: '24px'
                  }} />
                  
                  {/* Active tab indicator */}
                  <div style={{
                    padding: '12px',
                    backgroundColor: 'var(--mac-bg-tertiary)',
                    borderRadius: 'var(--mac-radius-sm)',
                    fontSize: '12px',
                    color: 'var(--mac-text-secondary)',
                    fontFamily: 'SF Mono, Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace'
                  }}>
                    Active: <strong style={{ color: 'var(--mac-accent-blue)' }}>
                      {[
                        { id: 'tab2-1', label: 'Dashboard' },
                        { id: 'tab2-2', label: 'Analytics' },
                        { id: 'tab2-3', label: 'Users' },
                        { id: 'tab2-4', label: 'System' }
                      ].find(tab => tab.id === activeTab2)?.label}
                    </strong>
                  </div>
                </div>

                {/* Variant 3: Rounded Style (Xcode-like) */}
                <div>
                  <h4 style={{ 
                    margin: '0 0 16px 0', 
                    fontSize: '13px', 
                    color: 'var(--mac-text-secondary)', 
                    fontWeight: '600' 
                  }}>
                    Variant 3: Rounded Style (Xcode-like)
                  </h4>
                  <div style={{ 
                    display: 'flex', 
                    gap: '8px', 
                    marginBottom: '24px',
                    backgroundColor: 'var(--mac-bg-secondary)',
                    borderRadius: 'var(--mac-radius-md)',
                    padding: '4px'
                  }}>
                    {[
                      { id: 'tab3-1', label: 'Files', icon: 'folder' },
                      { id: 'tab3-2', label: 'Search', icon: 'magnifyingglass' },
                      { id: 'tab3-3', label: 'Debug', icon: 'gear' },
                      { id: 'tab3-4', label: 'Help', icon: 'help' }
                    ].map((tab) => {
                      const isActive = tab.id === activeTab3;
                      
                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab3(tab.id)}
                          style={{
                            padding: '8px 16px',
                            border: 'none',
                            background: isActive ? 'var(--mac-accent-blue)' : 'transparent',
                            color: isActive ? 'white' : 'var(--mac-text-secondary)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: '8px',
                            fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                            fontSize: 'var(--mac-font-size-sm)',
                            borderRadius: 'var(--mac-radius-sm)',
                            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                            boxShadow: isActive ? 'var(--mac-shadow-sm)' : 'none'
                          }}
                          onMouseEnter={(e) => {
                            if (!isActive) {
                              e.target.style.backgroundColor = 'var(--mac-bg-tertiary)';
                              e.target.style.color = 'var(--mac-text-primary)';
                            }
                          }}
                          onMouseLeave={(e) => {
                            if (!isActive) {
                              e.target.style.backgroundColor = 'transparent';
                              e.target.style.color = 'var(--mac-text-secondary)';
                            }
                          }}
                        >
                          <Icon name={tab.icon} size="small" style={{ 
                            color: isActive ? 'white' : 'var(--mac-text-secondary)'
                          }} />
                          {tab.label}
                        </button>
                      );
                    })}
                  </div>
                  
                  {/* Active tab indicator */}
                  <div style={{
                    padding: '12px',
                    backgroundColor: 'var(--mac-bg-tertiary)',
                    borderRadius: 'var(--mac-radius-sm)',
                    fontSize: '12px',
                    color: 'var(--mac-text-secondary)',
                    fontFamily: 'SF Mono, Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace'
                  }}>
                    Active: <strong style={{ color: 'var(--mac-accent-blue)' }}>
                      {[
                        { id: 'tab3-1', label: 'Files' },
                        { id: 'tab3-2', label: 'Search' },
                        { id: 'tab3-3', label: 'Debug' },
                        { id: 'tab3-4', label: 'Help' }
                      ].find(tab => tab.id === activeTab3)?.label}
                    </strong>
                  </div>
                </div>

                {/* Usage Guidelines */}
                <div style={{
                  padding: '16px',
                  backgroundColor: 'var(--mac-bg-tertiary)',
                  borderRadius: 'var(--mac-radius-md)',
                  border: '1px solid var(--mac-border)'
                }}>
                  <h5 style={{ 
                    margin: '0 0 12px 0', 
                    fontSize: '13px', 
                    color: 'var(--mac-text-primary)', 
                    fontWeight: '600' 
                  }}>
                    Usage Guidelines:
                  </h5>
                  <ul style={{ 
                    margin: 0, 
                    paddingLeft: '20px', 
                    fontSize: '12px', 
                    color: 'var(--mac-text-secondary)',
                    lineHeight: '1.5'
                  }}>
                    <li><strong>Variant 1 (Underline):</strong> Best for content-heavy interfaces like Safari, perfect for medical dashboards</li>
                    <li><strong>Variant 2 (Colored Bar):</strong> Great for file management and hierarchical navigation</li>
                    <li><strong>Variant 3 (Rounded):</strong> Ideal for development tools and compact interfaces</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Icon Demo */}
          <Card style={{ marginBottom: '40px' }}>
            <CardHeader>
              <CardTitle>Icon System</CardTitle>
              <CardDescription>SF Symbols-like icon collection</CardDescription>
            </CardHeader>
            <CardContent>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(70px, 1fr))',
                gap: '20px'
              }}>
                {[
                  'house', 'person', 'heart', 'gear', 'bell', 'chart.bar',
                  'magnifyingglass', 'plus', 'trash', 'eye', 'phone', 'envelope'
                ].map((iconName) => (
                  <div key={iconName} style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '10px',
                    padding: '16px',
                    borderRadius: '10px',
                    backgroundColor: 'var(--mac-bg-tertiary)',
                    transition: 'all 0.2s ease'
                  }}>
                    <Icon name={iconName} size="large" />
                    <span style={{
                      fontSize: '11px',
                      color: 'var(--mac-text-secondary)',
                      textAlign: 'center',
                      fontWeight: '500'
                    }}>
                      {iconName}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>

      {/* Demo Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="macOS Modal Demo"
        actions={
          <>
            <Button 
              variant="outline" 
              onClick={() => setIsModalOpen(false)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Icon name="xmark" size="small" style={{ color: '#8e8e93' }} />
              Cancel
            </Button>
            <Button 
              variant="primary" 
              onClick={() => setIsModalOpen(false)}
              style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
            >
              <Icon name="checkmark" size="small" style={{ color: 'white' }} />
              Confirm
            </Button>
          </>
        }
      >
        <p style={{ margin: 0, lineHeight: '1.5' }}>
          This is a demonstration of the macOS-style modal component.
          It features backdrop blur, smooth animations, and proper accessibility.
        </p>

        <div style={{ marginTop: '16px' }}>
          <Input
            label="Demo Input"
            placeholder="Type something..."
          />
        </div>
      </Modal>

      {/* Toast Notifications */}
      {toasts.map(toast => (
        <Toast
          key={toast.id}
          type={toast.type}
          message={toast.message}
          position="top-right"
        />
      ))}

      {/* Demo Button */}
      <div style={{ position: 'fixed', bottom: '20px', right: '20px' }}>
        <Button
          variant="primary"
          size="large"
          onClick={() => setIsModalOpen(true)}
        >
          <Icon name="plus" />
          Open Demo Modal
        </Button>
      </div>
    </div>
  );
};

export default MacOSDemo;

