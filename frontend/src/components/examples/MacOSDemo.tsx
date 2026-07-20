import { useState, useEffect } from 'react';
import type { CSSProperties } from 'react';
import {
  Button as RawButton,
  Input as RawInput,
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
  Modal as RawModal,
  Icon,
  Badge as RawBadge,
  Progress as RawProgress,
  CircularProgress as RawCircularProgress,
  Sidebar,
  Checkbox as RawCheckbox,
  Radio as RawRadio,
  Switch as RawSwitch,
  Select as RawSelect,
  SegmentedControl as RawSegmentedControl,
  Textarea as RawTextarea,
} from '../ui/macos';
const Button = RawButton as unknown as React.ComponentType<Record<string, unknown>>;
const Input = RawInput as unknown as React.ComponentType<Record<string, unknown>>;
const Modal = RawModal as unknown as React.ComponentType<Record<string, unknown>>;
const Badge = RawBadge as unknown as React.ComponentType<Record<string, unknown>>;
const Progress = RawProgress as unknown as React.ComponentType<Record<string, unknown>>;
const CircularProgress = RawCircularProgress as unknown as React.ComponentType<Record<string, unknown>>;
const Checkbox = RawCheckbox as unknown as React.ComponentType<Record<string, unknown>>;
const Radio = RawRadio as unknown as React.ComponentType<Record<string, unknown>>;
const Switch = RawSwitch as unknown as React.ComponentType<Record<string, unknown>>;
const Select = RawSelect as unknown as React.ComponentType<Record<string, unknown>>;
const SegmentedControl = RawSegmentedControl as unknown as React.ComponentType<Record<string, unknown>>;
const Textarea = RawTextarea as unknown as React.ComponentType<Record<string, unknown>>;
import './MacOSDemo.css';
import { AccentPicker } from '../ui/macos';
import { notify } from '../../services/notify';

/**
 * macOS UI Demo Component
 * Showcases all macOS-style components in action
 */
const MacOSDemo = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeSidebarItem, setActiveSidebarItem] = useState('dashboard');
  const [segmentedValue, setSegmentedValue] = useState('all');
  const [textareaValue, setTextareaValue] = useState('');
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
    // UX Audit #1930: Toast component removed in PR #1928. Use notify service.
    if (type === 'success') notify.success(message);
    else if (type === 'error') notify.error(message);
    else if (type === 'warning') notify.warning(message);
    else notify.info(message);
  };

  const sidebarItems = [
  { id: 'dashboard', label: 'Dashboard', icon: 'house' },
  { id: 'patients', label: 'Patients', icon: 'person', badge: '12' },
  { id: 'appointments', label: 'Appointments', icon: 'calendar' },
  { id: 'reports', label: 'Reports', icon: 'chart.bar' },
  { id: 'settings', label: 'Settings', icon: 'gear' }];


  return (
    <div className="demo-root">
          {/* Custom Header с иконками */}
          <div className="demo-header-wrapper">
            <header className="demo-header">
              {/* Left section - Title */}
              <div className="demo-header-left">
                <h1 className="demo-header-title">
                  macOS Medical Dashboard
                </h1>
                <Badge variant="secondary">Demo</Badge>
              </div>

              {/* Center section - Actions */}
              <div className="demo-header-center">
                <Button
              variant="primary"
              size="small"
              onClick={() => notify.success('Patient created!')}
              className="demo-btn-icon-semibold">

                  <Icon name="plus" size="small" style={{ color: 'white' }} />
                  New Patient
                </Button>
                
                <Button
              variant="outline"
              size="small"
              onClick={() => notify.info('Search initiated')}
              className="demo-btn-icon">

                  <Icon name="magnifyingglass" size="small" className="demo-tab-indicator-strong" />
                  Search
                </Button>
                
                <Button
              variant="secondary"
              size="small"
              onClick={() => notify.warning('Settings opened')}
              className="demo-btn-icon">

                  <Icon name="gear" size="small" style={{ color: 'var(--mac-text-tertiary)' }} />
                  Settings
                </Button>
              </div>

              {/* Right section - Accent & Theme */}
              <div className="demo-header-right">
                <AccentPicker />
                <Button
              variant="ghost"
              size="small"
              onClick={toggleDarkMode}
              className="demo-theme-btn"
              aria-label={`Switch to ${isDarkMode ? 'light' : 'dark'} mode`}
              title={`Switch to ${isDarkMode ? 'light' : 'dark'} mode`}>

                  <Icon name={isDarkMode ? 'sun' : 'moon'} size="small" style={{ color: isDarkMode ? 'var(--mac-warning)' : 'var(--mac-accent-blue-light)' }} />
                </Button>
              </div>
            </header>
          </div>

      <div className="demo-main-layout">
            {/* Sidebar с отступом */}
            <div className="demo-sidebar-wrapper">
              <Sidebar
            items={sidebarItems}
            activeItem={activeSidebarItem}
            onItemClick={(item) => setActiveSidebarItem(item.id)}
            header="Medical System"
            className="demo-sidebar" />

            </div>

        {/* Main Content */}
        <div className="demo-content">
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
          <div className="demo-card-grid">
            {/* Button Demo */}
            <Card>
              <CardHeader>
                <CardTitle>Button Components</CardTitle>
                <CardDescription>Various button styles and states</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="demo-flex-col-3">
                <div className="demo-flex-wrap-2">
                  <Button variant="primary" className="demo-btn-icon">
                    <Icon name="plus" size="small" style={{ color: 'white' }} />
                    Primary
                  </Button>
                  <Button variant="secondary" className="demo-btn-icon">
                    <Icon name="gear" size="small" style={{ color: 'var(--mac-text-tertiary)' }} />
                    Secondary
                  </Button>
                  <Button variant="outline" className="demo-btn-icon">
                    <Icon name="square.and.arrow.up" size="small" className="demo-tab-indicator-strong" />
                    Outline
                  </Button>
                  <Button variant="ghost" className="demo-btn-icon">
                    <Icon name="eye" size="small" style={{ color: 'var(--mac-success)' }} />
                    Ghost
                  </Button>
                </div>
                <div className="demo-flex-wrap-2">
                  <Button variant="success" className="demo-btn-icon">
                    <Icon name="checkmark.circle" size="small" style={{ color: 'var(--mac-success)' }} />
                    Success
                  </Button>
                  <Button variant="warning" className="demo-btn-icon">
                    <Icon name="exclamationmark.triangle" size="small" style={{ color: 'var(--mac-warning)' }} />
                    Warning
                  </Button>
                  <Button variant="danger" className="demo-btn-icon">
                    <Icon name="trash" size="small" style={{ color: 'var(--mac-error)' }} />
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
                <div className="demo-flex-col-4">
                  <Input
                    label="Patient Name"
                    placeholder="Enter patient name"
                    hint="Full name as on ID" />

                  <Input
                    label="Email Address"
                    type="email"
                    placeholder="patient@example.com"
                    error="Invalid email format" />

                  <Input
                    label="Phone Number"
                    type="tel"
                    placeholder="+1 (555) 123-4567"
                    disabled />

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
                <div className="demo-flex-col-4">
                  <div>
                    <div className="demo-progress-label">
                      Treatment Progress
                    </div>
                    <Progress value={75} max={100} showValue />
                  </div>
                  <div>
                    <div className="demo-progress-label">
                      Data Sync
                    </div>
                    <Progress value={45} max={100} variant="primary" />
                  </div>
                  <div className="demo-flex-center-2">
                    <CircularProgress value={85} size="small" />
                    <span className="demo-progress-percent">85%</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Form Controls Demo */}
          <Card className="demo-card-mb-6">
            <CardHeader>
              <CardTitle>Form Controls</CardTitle>
              <CardDescription>Complete set of macOS form components</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="demo-form-grid">
                <div className="demo-form-subsection">
                  <h4 className="demo-section-heading">Checkboxes</h4>
                  <Checkbox label="Receive notifications" description="Email and push" defaultChecked />
                  <Checkbox label="Enable auto-backup" />
                  <Checkbox label="Sync with cloud" disabled />
                </div>
                
                <div className="demo-form-subsection">
                  <h4 className="demo-section-heading">Radio Buttons</h4>
                  <Radio name="priority" value="normal" label="Normal Priority" defaultChecked />
                  <Radio name="priority" value="urgent" label="Urgent Priority" />
                  <Radio name="priority" value="low" label="Low Priority" />
                </div>
                
                <div className="demo-form-subsection">
                  <h4 className="demo-section-heading">Switches</h4>
                  <Switch label="Dark Mode" />
                  <Switch label="Push Notifications" defaultChecked />
                  <Switch label="Auto-save" />
                </div>
                
                <div className="demo-form-subsection">
                  <h4 className="demo-section-heading">Select Dropdown</h4>
                  <Select
                    label="Department"
                    options={[
                    { value: 'cardio', label: 'Cardiology' },
                    { value: 'derma', label: 'Dermatology' },
                    { value: 'dental', label: 'Dentistry' },
                    { value: 'lab', label: 'Laboratory' }]
                    }
                    placeholder="Choose department" />

                </div>
              </div>
              
              <div className="demo-form-extra">
                <div>
                  <h4 className="demo-section-heading-mb16">Segmented Control</h4>
                  <SegmentedControl
                    options={[
                    { value: 'all', label: 'All Patients' },
                    { value: 'active', label: 'Active' },
                    { value: 'pending', label: 'Pending' },
                    { value: 'completed', label: 'Completed' }]
                    }
                    value={segmentedValue}
                    onChange={(v: unknown) => setSegmentedValue(String(v))} />

                </div>
                
                <div>
                  <h4 className="demo-section-heading-mb16">Textarea</h4>
                  <Textarea
                    label="Patient Notes"
                    placeholder="Enter detailed patient notes..."
                    hint="Include symptoms, diagnosis, and treatment plan"
                    value={textareaValue}
                    onChange={(e) => setTextareaValue(e.target.value)}
                    minRows={3}
                    maxRows={8}
                    autoResize
                    maxLength={500} />

                </div>
              </div>
            </CardContent>
          </Card>

          {/* Tab System Demo */}
          <Card className="demo-card-mb-40">
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
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)',
                    fontWeight: 'var(--mac-font-weight-semibold)'
                  }}>
                    Variant 1: Underline Style (Safari-like)
                  </h4>
                  <div className="demo-tab-variant-1">
                    {[
                    { id: 'tab1-1', label: 'Overview', icon: 'house' },
                    { id: 'tab1-2', label: 'Patients', icon: 'person' },
                    { id: 'tab1-3', label: 'Reports', icon: 'chart.bar' },
                    { id: 'tab1-4', label: 'Settings', icon: 'gear' }].
                    map((tab) => {
                      const isActive = tab.id === activeTab1;

                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab1(tab.id)}
                          style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-5)',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--mac-spacing-2)',
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
                            fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                            fontSize: 'var(--mac-font-size-sm)',
                            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                            position: 'relative',
                            borderBottom: isActive ? '2px solid var(--mac-accent-blue)' : '2px solid transparent',
                            marginBottom: '-1px'
                          }}
                          onMouseEnter={(e: any) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-primary)';
                            }
                          }}
                          onMouseLeave={(e: any) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-secondary)';
                            }
                          }}>

                          <Icon name={tab.icon} size="small" style={{
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
                          }} />
                          {tab.label}
                        </button>);

                    })}
                  </div>
                  
                  {/* Active tab indicator */}
                  <div className="demo-tab-indicator">
                    Active: <strong className="demo-tab-indicator-strong">
                      {[
                      { id: 'tab1-1', label: 'Overview' },
                      { id: 'tab1-2', label: 'Patients' },
                      { id: 'tab1-3', label: 'Reports' },
                      { id: 'tab1-4', label: 'Settings' }].
                      find((tab) => tab.id === activeTab1)?.label}
                    </strong>
                  </div>
                </div>

                {/* Variant 2: Colored Bar Style (Finder-like) */}
                <div>
                  <h4 style={{
                    margin: '0 0 16px 0',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)',
                    fontWeight: 'var(--mac-font-weight-semibold)'
                  }}>
                    Variant 2: Colored Bar Style (Finder-like)
                  </h4>
                  <div className="demo-tab-variant-2">
                    {[
                    { id: 'tab2-1', label: 'Dashboard', icon: 'house' },
                    { id: 'tab2-2', label: 'Analytics', icon: 'chart.bar' },
                    { id: 'tab2-3', label: 'Users', icon: 'person' },
                    { id: 'tab2-4', label: 'System', icon: 'gear' }].
                    map((tab) => {
                      const isActive = tab.id === activeTab2;

                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab2(tab.id)}
                          style={{
                            padding: 'var(--mac-spacing-3) var(--mac-spacing-5)',
                            border: 'none',
                            background: 'transparent',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--mac-spacing-2)',
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)',
                            fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                            fontSize: 'var(--mac-font-size-sm)',
                            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                            position: 'relative',
                            marginBottom: '-1px'
                          }}
                          onMouseEnter={(e: any) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-primary)';
                            }
                          }}
                          onMouseLeave={(e: any) => {
                            if (!isActive) {
                              e.target.style.color = 'var(--mac-text-secondary)';
                            }
                          }}>

                          <Icon name={tab.icon} size="small" style={{
                            color: isActive ? 'var(--mac-accent-blue)' : 'var(--mac-text-secondary)'
                          }} />
                          {tab.label}
                          {isActive &&
                          <div style={{
                            position: 'absolute',
                            bottom: '0',
                            left: '0',
                            right: '0',
                            height: '3px',
                            backgroundColor: 'var(--mac-accent-blue)',
                            borderRadius: '2px 2px 0 0'
                          }} />
                          }
                        </button>);

                    })}
                  </div>
                  <div className="demo-tab-border" />
                  
                  {/* Active tab indicator */}
                  <div className="demo-tab-indicator">
                    Active: <strong className="demo-tab-indicator-strong">
                      {[
                      { id: 'tab2-1', label: 'Dashboard' },
                      { id: 'tab2-2', label: 'Analytics' },
                      { id: 'tab2-3', label: 'Users' },
                      { id: 'tab2-4', label: 'System' }].
                      find((tab) => tab.id === activeTab2)?.label}
                    </strong>
                  </div>
                </div>

                {/* Variant 3: Rounded Style (Xcode-like) */}
                <div>
                  <h4 style={{
                    margin: '0 0 16px 0',
                    fontSize: 'var(--mac-font-size-sm)',
                    color: 'var(--mac-text-secondary)',
                    fontWeight: 'var(--mac-font-weight-semibold)'
                  }}>
                    Variant 3: Rounded Style (Xcode-like)
                  </h4>
                  <div className="demo-tab-variant-3">
                    {[
                    { id: 'tab3-1', label: 'Files', icon: 'folder' },
                    { id: 'tab3-2', label: 'Search', icon: 'magnifyingglass' },
                    { id: 'tab3-3', label: 'Debug', icon: 'gear' },
                    { id: 'tab3-4', label: 'Help', icon: 'help' }].
                    map((tab) => {
                      const isActive = tab.id === activeTab3;

                      return (
                        <button
                          key={tab.id}
                          onClick={() => setActiveTab3(tab.id)}
                          style={{
                            padding: 'var(--mac-spacing-2) var(--mac-spacing-4)',
                            border: 'none',
                            background: isActive ? 'var(--mac-accent-blue)' : 'transparent',
                            color: isActive ? 'white' : 'var(--mac-text-secondary)',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            gap: 'var(--mac-spacing-2)',
                            fontWeight: isActive ? 'var(--mac-font-weight-semibold)' : 'var(--mac-font-weight-normal)',
                            fontSize: 'var(--mac-font-size-sm)',
                            borderRadius: 'var(--mac-radius-sm)',
                            transition: 'all var(--mac-duration-normal) var(--mac-ease)',
                            boxShadow: isActive ? 'var(--mac-shadow-sm)' : 'none'
                          }}
                          onMouseEnter={(e: any) => {
                            if (!isActive) {
                              e.target.style.backgroundColor = 'var(--mac-bg-tertiary)';
                              e.target.style.color = 'var(--mac-text-primary)';
                            }
                          }}
                          onMouseLeave={(e: any) => {
                            if (!isActive) {
                              e.target.style.backgroundColor = 'transparent';
                              e.target.style.color = 'var(--mac-text-secondary)';
                            }
                          }}>

                          <Icon name={tab.icon} size="small" style={{
                            color: isActive ? 'white' : 'var(--mac-text-secondary)'
                          }} />
                          {tab.label}
                        </button>);

                    })}
                  </div>
                  
                  {/* Active tab indicator */}
                  <div className="demo-tab-indicator">
                    Active: <strong className="demo-tab-indicator-strong">
                      {[
                      { id: 'tab3-1', label: 'Files' },
                      { id: 'tab3-2', label: 'Search' },
                      { id: 'tab3-3', label: 'Debug' },
                      { id: 'tab3-4', label: 'Help' }].
                      find((tab) => tab.id === activeTab3)?.label}
                    </strong>
                  </div>
                </div>

                {/* Usage Guidelines */}
                <div className="demo-guidelines">
                  <h5 className="demo-guidelines-title">
                    Usage Guidelines:
                  </h5>
                  <ul className="demo-guidelines-list">
                    <li><strong>Variant 1 (Underline):</strong> Best for content-heavy interfaces like Safari, perfect for medical dashboards</li>
                    <li><strong>Variant 2 (Colored Bar):</strong> Great for file management and hierarchical navigation</li>
                    <li><strong>Variant 3 (Rounded):</strong> Ideal for development tools and compact interfaces</li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Icon Demo */}
          <Card className="demo-card-mb-40">
            <CardHeader>
              <CardTitle>Icon System</CardTitle>
              <CardDescription>SF Symbols-like icon collection</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="demo-icon-grid">
                {[
                'house', 'person', 'heart', 'gear', 'bell', 'chart.bar',
                'magnifyingglass', 'plus', 'trash', 'eye', 'phone', 'envelope'].
                map((iconName) =>
                <div key={iconName} className="demo-icon-cell">
                    <Icon name={iconName} size="large" />
                    <span className="demo-icon-label">
                      {iconName}
                    </span>
                  </div>
                )}
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
            className="demo-btn-icon">

              <Icon name="xmark" size="small" style={{ color: 'var(--mac-text-tertiary)' }} />
              Cancel
            </Button>
            <Button
            variant="primary"
            onClick={() => setIsModalOpen(false)}
            className="demo-btn-icon">

              <Icon name="checkmark" size="small" style={{ color: 'white' }} />
              Confirm
            </Button>
          </>
        }>

        <p className="demo-modal-text">
          This is a demonstration of the macOS-style modal component.
          It features backdrop blur, smooth animations, and proper accessibility.
        </p>

        <div className="demo-modal-input">
          <Input
            label="Demo Input"
            placeholder="Type something..." />

        </div>
      </Modal>

      {/* Toast Notifications — removed in PR #1928. showToast() now uses notify service. */}

      {/* Demo Button */}
      <div className="demo-fab">
        <Button
          variant="primary"
          size="large"
          onClick={() => setIsModalOpen(true)}>

          <Icon name="plus" />
          Open Demo Modal
        </Button>
      </div>
    </div>);

};

export default MacOSDemo;
