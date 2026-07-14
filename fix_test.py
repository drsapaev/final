import re

with open('frontend/src/pages/__tests__/DoctorPanels.contract.test.jsx', 'r') as f:
    content = f.read()

new_test = """
  it('keeps the active doctor queue page action visibility backend-owned', () => {
    const queueCard = read('components/queue/QueueManagementCard.jsx');
    const doctorPanel = read('pages/DoctorPanel.jsx');

    expect(doctorPanel).toContain('const hasBackendQueueAction =');
    expect(doctorPanel).toContain('canCallNext');

    expect(queueCard).toContain("hasBackendQueueAction(entry, 'no_show', 'can_no_show')");
    expect(queueCard).toContain("hasBackendQueueAction(entry, 'send_to_diagnostics', 'can_send_to_diagnostics')");
    expect(queueCard).toContain("hasBackendQueueAction(entry, 'notify_diagnostics_return', 'can_notify_diagnostics_return')");
    expect(queueCard).toContain("hasBackendQueueAction(entry, 'restore_next', 'can_restore_next')");
  });
"""

pattern = r"  it\('keeps the active doctor queue page action visibility backend-owned', \(\) => \{.*?\n  \}\);"
content = re.sub(pattern, new_test.strip('\n'), content, flags=re.DOTALL)

with open('frontend/src/pages/__tests__/DoctorPanels.contract.test.jsx', 'w') as f:
    f.write(content)
