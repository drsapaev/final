import React, { useState } from 'react';
import {
  Button,
  Input,
  Card,
  Modal,
  Table,
  Tooltip,
  Icon,
  Badge,
  Progress,
  Avatar,
  Sidebar,
  Header
} from '../ui/macos';

/**
 * macOS UI Demo Component
 * Showcases all macOS-style components in action
 */
const MacOSDemo = () => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [activeSidebarItem, setActiveSidebarItem] = useState('dashboard');

  const sidebarItems = [
    { id: 'dashboard', label: 'Dashboard', icon: 'house' },
    { id: 'patients', label: 'Patients', icon: 'person', badge: '12' },
    { id: 'appointments', label: 'Appointments', icon: 'calendar' },
    { id: 'reports', label: 'Reports', icon: 'chart.bar' },
    { id: 'settings', label: 'Settings', icon: 'gear' }
  ];

  const tableData = [
    { id: 1, name: 'John Doe', status: 'Active', progress: 75 },
    { id: 2, name: 'Jane Smith', status: 'Pending', progress: 45 },
    { id: 3, name: 'Bob Johnson', status: 'Completed', progress: 100 }
  ];

  return (
    <div style={{
      fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", system-ui, sans-serif',
      backgroundColor: 'var(--mac-bg-secondary)',
      minHeight: '100vh',
      padding: '20px'
    }}>
      {/* Header */}
      <Header
        title="macOS Medical Dashboard"
        subtitle="Demonstrating native macOS UI components"
        user={{
          name: 'Dr. Smith',
          avatar: null,
          status: 'online'
        }}
        onSettingsClick={() => console.log('Settings clicked')}
        onUserClick={() => console.log('User clicked')}
        actions={
          <div style={{ display: 'flex', gap: '8px' }}>
            <Button variant="primary" size="small">
              <Icon name="plus" size="small" />
              New Patient
            </Button>
            <Button variant="outline" size="small">
              Export
            </Button>
          </div>
        }
      />

      <div style={{ display: 'flex', gap: '20px', marginTop: '20px' }}>
        {/* Sidebar */}
        <Sidebar
          items={sidebarItems}
          activeItem={activeSidebarItem}
          onItemClick={(item) => setActiveSidebarItem(item.id)}
          header="Medical System"
          style={{ flexShrink: 0 }}
        />

        {/* Main Content */}
        <div style={{ flex: 1 }}>
          {/* Demo Cards */}
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
            gap: '20px',
            marginBottom: '20px'
          }}>
            {/* Button Demo */}
            <Card>
              <Card.Header>
                <Card.Title>Button Components</Card.Title>
                <Card.Description>Various button styles and states</Card.Description>
              </Card.Header>
              <Card.Content>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <Button variant="primary">Primary</Button>
                    <Button variant="secondary">Secondary</Button>
                    <Button variant="outline">Outline</Button>
                    <Button variant="ghost">Ghost</Button>
                  </div>
                  <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                    <Button variant="success">Success</Button>
                    <Button variant="warning">Warning</Button>
                    <Button variant="danger">Danger</Button>
                  </div>
                </div>
              </Card.Content>
            </Card>

            {/* Input Demo */}
            <Card>
              <Card.Header>
                <Card.Title>Input Components</Card.Title>
                <Card.Description>Text inputs with validation</Card.Description>
              </Card.Header>
              <Card.Content>
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
              </Card.Content>
            </Card>

            {/* Progress Demo */}
            <Card>
              <Card.Header>
                <Card.Title>Progress Indicators</Card.Title>
                <Card.Description>Loading states and progress bars</Card.Description>
              </Card.Header>
              <Card.Content>
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
                    <Progress.Circular value={85} size="small" />
                    <span style={{ fontSize: '11px', color: 'var(--mac-text-secondary)' }}>85%</span>
                  </div>
                </div>
              </Card.Content>
            </Card>

            {/* Avatar Demo */}
            <Card>
              <Card.Header>
                <Card.Title>Avatar Components</Card.Title>
                <Card.Description>User avatars with status indicators</Card.Description>
              </Card.Header>
              <Card.Content>
                <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <Avatar
                    name="John Doe"
                    size="large"
                    status="online"
                    onClick={() => console.log('Avatar clicked')}
                  />
                  <div>
                    <div style={{ fontSize: '15px', fontWeight: '600', color: 'var(--mac-text-primary)' }}>
                      John Doe
                    </div>
                    <div style={{ fontSize: '13px', color: 'var(--mac-text-secondary)' }}>
                      Chief Physician
                    </div>
                  </div>
                </div>

                <div style={{ marginTop: '16px' }}>
                  <Avatar.Group
                    avatars={[
                      { name: 'Alice Johnson' },
                      { name: 'Bob Smith' },
                      { name: 'Carol Davis' },
                      { name: 'David Wilson' }
                    ]}
                    max={3
                  />
                </div>
              </Card.Content>
            </Card>
          </div>

          {/* Table Demo */}
          <Card>
            <Card.Header>
              <Card.Title>Patient Records</Card.Title>
              <Card.Description>Interactive data table with sorting</Card.Description>
            </Card.Header>
            <Card.Content>
              <Table striped hoverable>
                <Table.Header>
                  <Table.HeaderCell sortable sorted sortDirection="asc" onSort={(direction) => console.log('Sort:', direction)}>
                    Patient Name
                  </Table.HeaderCell>
                  <Table.HeaderCell>Status</Table.HeaderCell>
                  <Table.HeaderCell>Progress</Table.HeaderCell>
                  <Table.HeaderCell>Actions</Table.HeaderCell>
                </Table.Header>
                <Table.Body>
                  {tableData.map((patient) => (
                    <Table.Row key={patient.id} hoverable>
                      <Table.Cell>{patient.name}</Table.Cell>
                      <Table.Cell>
                        <Badge variant={patient.status === 'Active' ? 'success' : patient.status === 'Pending' ? 'warning' : 'primary'}>
                          {patient.status}
                        </Badge>
                      </Table.Cell>
                      <Table.Cell>
                        <Progress value={patient.progress} max={100} size="small" />
                      </Table.Cell>
                      <Table.Cell>
                        <Button variant="ghost" size="small">
                          <Icon name="eye" size="small" />
                        </Button>
                      </Table.Cell>
                    </Table.Row>
                  ))}
                </Table.Body>
              </Table>
            </Card.Content>
          </Card>

          {/* Icon Demo */}
          <Card>
            <Card.Header>
              <Card.Title>Icon System</Card.Title>
              <Card.Description>SF Symbols-like icon collection</Card.Description>
            </Card.Header>
            <Card.Content>
              <div style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(auto-fill, minmax(60px, 1fr))',
                gap: '16px'
              }}>
                {[
                  'house', 'person', 'heart', 'gear', 'bell', 'chart.bar',
                  'magnifyingglass', 'plus', 'trash', 'eye', 'phone', 'envelope'
                ].map((iconName) => (
                  <div key={iconName} style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    gap: '8px',
                    padding: '12px',
                    borderRadius: '8px',
                    backgroundColor: 'var(--mac-bg-tertiary)',
                    transition: 'all 0.2s ease'
                  }}>
                    <Icon name={iconName} size="large" />
                    <span style={{
                      fontSize: '11px',
                      color: 'var(--mac-text-secondary)',
                      textAlign: 'center'
                    }}>
                      {iconName}
                    </span>
                  </div>
                ))}
              </div>
            </Card.Content>
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
            <Button variant="outline" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setIsModalOpen(false)}>
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
