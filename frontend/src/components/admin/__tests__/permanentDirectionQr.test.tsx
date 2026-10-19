/**
 * RQ-18 — permanent direction QR admin surface pins (S-15 admin half).
 *
 * Contract: RQ-16.d backend is consumed as-is (NO second backend impl):
 *  - POST /queue/admin/directions/{profile_key}/public-address/provision —
 *    Admin-only, IDEMPOTENT: a re-provision returns the SAME address
 *    (created=false). The UI recovers the public_code after reload through
 *    this idempotent contract — no GET-public-code endpoint is added.
 *  - GET /queue/directions/{profile_key}/entry-methods — honest
 *    permanent_address.supported flag.
 *
 * Honesty pins (directive §5/§12/§13):
 *  - the QR payload is the ABSOLUTE canonical frontend origin + /q/<code>
 *    (never a backend origin, never a hardcoded deployment domain);
 *  - a read error NEVER renders as «not provisioned» (honest unknown);
 *  - the permanent address shows NO expiry/TTL phrasing (it is not a
 *    token) — the permanent/non-token note is always present;
 *  - supported=false + created=false (address exists, direction not
 *    bookable right now) shows the QR with an honest not-bookable note,
 *    never a false «готово».
 *
 * RQ-18 follow-up (owner round-1 review of merged #3360):
 *  - P2-3: after a successful provision the entry-methods are RE-READ —
 *    a freshly provisioned healthy direction drops the stale
 *    «запись недоступна» note; a failed recheck renders the honest
 *    unknown state, never a confident «недоступно»;
 *  - P2-4: one QR block PER PROFILE KEY — a profile carrying several
 *    queue_tags renders the block once; sibling tag rows show a pointer
 *    note instead of independent duplicate QR states.
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { ThemeProvider } from '@/contexts/ThemeContext';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
    get: vi.fn(),
    post: vi.fn(),
}));

vi.mock('../../../api/client', () => ({
    api: apiMocks,
}));

const queueResourcesMocks = vi.hoisted(() => ({
    listQueueResources: vi.fn(),
}));

vi.mock('../../../api/queueResources', () => queueResourcesMocks);

const directionMocks = vi.hoisted(() => ({
    fetchAdminQueueDirections: vi.fn(),
    provisionPublicAddress: vi.fn(),
    fetchDirectionEntryMethods: vi.fn(),
}));

vi.mock('../../../api/queueDirections', () => directionMocks);

vi.mock('qrcode.react', () => ({
    QRCodeSVG: (props: { value?: string; 'data-testid'?: string }) => (
        <div data-testid={props['data-testid'] || 'qr-svg'} data-qr-value={props.value} />
    ),
}));

import AdminSetupDirections from '../AdminSetupDirections';
import PermanentDirectionQr from '../PermanentDirectionQr';

const SERVICE_ROW = {
    id: 1,
    name: 'Service',
    active: true,
    requires_doctor: false,
    queue_tag: 'lab',
    doctor_id: null,
};

const PROFILE_ROW = {
    key: 'lab-key',
    title_ru: 'Лаборатория',
    is_active: true,
    show_on_qr_page: true,
    queue_tags: ['lab'],
};

const ADMIN_DIRECTION = {
    profile: {
        id: 7,
        key: 'lab-key',
        title: 'Laboratory',
        title_ru: 'Лаборатория',
        queue_tags: ['lab'],
        department_key: 'lab',
        is_active: true,
        show_on_qr_page: true,
        display_order: 1,
        icon: null,
        color: null,
    },
    resolved_mode: 'booking',
    configuration_state: 'ready',
    configuration_reasons: [],
    effective_availability: 'available',
    effective_availability_reasons: [],
    booking_targets: [],
    current_day_queues: [],
    public_availability: true,
    permanent_address_exists: false,
    precreate_by_tag: [],
    allowed_next_actions: [{
        kind: 'provision_permanent_address',
        entity_type: 'queue_profile',
        entity_id: 7,
        entity_key: 'lab-key',
    }],
};

/** Builds an entry-methods payload with the given permanent_address flag. */
function methodsPayload(supported: boolean) {
    return {
        direction_key: 'lab-key',
        entry_methods: [
            { method: 'session_qr', supported: true },
            { method: 'permanent_address', supported },
            { method: 'view_only', supported: true },
        ],
    };
}

/** Default post-provision recheck behavior for existing pins. */
function mockRecheck(afterProvisionSupported: boolean | 'fail') {
    directionMocks.fetchDirectionEntryMethods.mockImplementation(
        (_profileKey: string) =>
            afterProvisionSupported === 'fail'
                ? Promise.reject(new Error('recheck failed'))
                : Promise.resolve(methodsPayload(afterProvisionSupported)),
    );
}

function setupApiMock(entryMethods: { data: unknown } | null) {
    directionMocks.fetchAdminQueueDirections.mockResolvedValue({
        as_of_day: '2026-10-18',
        directions: [ADMIN_DIRECTION],
        unattached: { queue_tags: [], services: [], resources: [] },
    });
    apiMocks.get.mockImplementation((url: string) => {
        if (url.startsWith('/services?')) {
            return Promise.resolve({ data: [SERVICE_ROW] });
        }
        if (url.startsWith('/queues/profiles')) {
            return Promise.resolve({ data: { profiles: [PROFILE_ROW] } });
        }
        if (url.startsWith('/services/admin/doctors')) {
            return Promise.resolve({ data: [] });
        }
        if (url.includes('/entry-methods')) {
            if (entryMethods === null) {
                return Promise.reject(new Error('read failed'));
            }
            return Promise.resolve(entryMethods);
        }
        return Promise.reject(new Error(`unexpected GET ${url}`));
    });
    queueResourcesMocks.listQueueResources.mockResolvedValue([]);
    if (entryMethods === null) {
        directionMocks.fetchDirectionEntryMethods.mockRejectedValue(new Error('read failed'));
    } else {
        directionMocks.fetchDirectionEntryMethods.mockResolvedValue(entryMethods.data);
    }
}

async function renderScreen(options: { expandQr?: boolean } = {}) {
    const result = render(
        <ThemeProvider>
            <MemoryRouter>
                <AdminSetupDirections />
            </MemoryRouter>
        </ThemeProvider>,
    );
    if (options.expandQr !== false) {
        const button = await screen.findByTestId('setup-qr-expand-lab');
        await userEvent.setup().click(button);
        await screen.findByTestId('setup-qr-block-lab');
    }
    return result;
}

const PROVISION_RESPONSE = {
    profile_id: 7,
    direction_key: 'lab-key',
    public_code: 'abcd1234efgh',
    url_path: '/q/abcd1234efgh',
    created: true,
    provisioned_at: '2026-09-20T00:00:00Z',
};

beforeEach(() => {
    vi.clearAllMocks();
    // default recheck: mirrors the pre-provision flag (false) — explicit
    // pins override this per test
    mockRecheck(false);
});

describe('RQ-18 — permanent direction QR admin surface', () => {
    it('defers the profile QR read until its disclosure is opened', async () => {
        setupApiMock({ data: methodsPayload(false) });
        await renderScreen({ expandQr: false });
        await screen.findByTestId('setup-checklist-row-lab');
        expect(directionMocks.fetchDirectionEntryMethods).not.toHaveBeenCalled();

        await userEvent.setup().click(screen.getByTestId('setup-qr-expand-lab'));
        expect(await screen.findByTestId('setup-qr-block-lab')).toBeTruthy();
        expect(directionMocks.fetchDirectionEntryMethods).toHaveBeenCalledWith('lab-key');
    });

    it('PIN 1 (red on main): checklist exposes a permanent-QR block per QR-visible direction', async () => {
        setupApiMock({
            data: {
                direction_key: 'lab-key',
                entry_methods: [
                    { method: 'session_qr', supported: true },
                    { method: 'permanent_address', supported: false },
                    { method: 'view_only', supported: true },
                ],
            },
        });
        await renderScreen();
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-block-lab')).toBeTruthy();
        });
    });

    it('PIN 2: provision response renders the QR image and the /q/<code> URL', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        const btn = await screen.findByTestId('setup-qr-provision-lab');
        fireEvent.click(btn);
        expect(await screen.findByTestId('setup-qr-image-lab')).toBeTruthy();
        expect(screen.getByTestId('setup-qr-url-lab').textContent).toContain('/q/abcd1234efgh');
        expect(directionMocks.provisionPublicAddress).toHaveBeenCalledWith('lab-key');
    });

    it('notifies the parent when a permanent address is provisioned', async () => {
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        const onAddressProvisioned = vi.fn();
        render(
            <ThemeProvider>
                <PermanentDirectionQr
                    profileKey="lab-key"
                    tag="lab"
                    supported={false}
                    onAddressProvisioned={onAddressProvisioned}
                    supportGeneration={12}
                />
            </ThemeProvider>,
        );

        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await waitFor(() => expect(onAddressProvisioned).toHaveBeenCalledWith('lab-key', 12));
    });

    it('PIN 3: re-provision (reload recovery) keeps the SAME code (created=false path)', async () => {
        setupApiMock({ data: methodsPayload(true) });
        directionMocks.provisionPublicAddress.mockResolvedValue({
            ...PROVISION_RESPONSE,
            created: false,
        });
        await renderScreen();
        // supported=true → «Показать QR» (idempotent re-provision recovery)
        const btn = await screen.findByTestId('setup-qr-show-lab');
        fireEvent.click(btn);
        expect(await screen.findByTestId('setup-qr-image-lab')).toBeTruthy();
        expect(screen.getByTestId('setup-qr-url-lab').textContent).toContain('/q/abcd1234efgh');
        expect(directionMocks.provisionPublicAddress).toHaveBeenCalledTimes(1);
    });

    it('PIN 4: QR payload is the absolute canonical frontend origin + /q/<public_code>', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        const qr = screen.getByTestId('setup-qr-image-lab').querySelector('[data-qr-value]');
        expect(qr?.getAttribute('data-qr-value')).toBe(
            `${window.location.origin}/q/abcd1234efgh`,
        );
    });

    it('PIN 5: entry-methods read failure stays separate from direction facts — never «not provisioned»', async () => {
        setupApiMock(null);
        await renderScreen({ expandQr: false });
        await screen.findByTestId('setup-checklist-row-lab');
        await userEvent.setup().click(screen.getByTestId('setup-qr-expand-lab'));
        expect(await screen.findByTestId('setup-qr-read-retry-lab')).toBeVisible();
        expect(screen.getByTestId('setup-checklist-row-lab')).toBeVisible();
        expect(screen.queryByTestId('setup-qr-provision-lab')).toBeNull();
    });

    it('PIN 6: the permanent surface never shows expiry/TTL phrasing and always the non-token note', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        const { container } = await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        const block = screen.getByTestId('setup-qr-block-lab');
        expect(block.textContent).not.toMatch(/истек|действует до|expires|TTL|срок/i);
        expect(screen.getByTestId('setup-qr-permanent-note-lab')).toBeTruthy();
        // honest success/error not by color alone: textual state markers exist
        expect(container.querySelector('[data-testid="setup-qr-url-lab"]')).toBeTruthy();
    });

    it('PIN 6b: created=false while supported=false → QR shown WITH an honest not-bookable note', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.provisionPublicAddress.mockResolvedValue({
            ...PROVISION_RESPONSE,
            created: false,
        });
        await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        expect(await screen.findByTestId('setup-qr-image-lab')).toBeTruthy();
        // the note shows only after the recheck PROVES false; the
        // transient pending state is pinned separately in PIN 8 (a
        // controlled pending recheck promise)
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-not-bookable-note-lab')).toBeTruthy();
        });
        expect(screen.queryByTestId('setup-qr-unknown-lab')).toBeNull();
    });

    it('PIN 6c: provision failure shows an explicit error — no silent fake success', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.provisionPublicAddress.mockRejectedValue(
            new Error('provision refused'),
        );
        await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-error-lab')).toBeTruthy();
        });
        expect(screen.queryByTestId('setup-qr-image-lab')).toBeNull();
    });

    it('PIN 7-loop: checklist load does NOT loop — GET count stays bounded (pre-existing main defect found by the QR state pin)', async () => {
        setupApiMock({ data: methodsPayload(false) });
        await renderScreen();
        await screen.findByTestId('setup-qr-provision-lab');
        await new Promise((r) => setTimeout(r, 400));
        // Core facts use one request. The one lazy QR read occurs only after
        // opening the disclosure; neither request loops on rerender.
        expect(directionMocks.fetchAdminQueueDirections).toHaveBeenCalledTimes(1);
        expect(directionMocks.fetchDirectionEntryMethods).toHaveBeenCalledTimes(1);
    });

    it('PIN 8 (round-2 P2): while the post-provision recheck is pending the state is an honest UNKNOWN — no stale not-bookable note; a proven true drops the note', async () => {
        setupApiMock({ data: methodsPayload(false) });
        let resolveRecheck: (value: unknown) => void = () => {};
        const pendingRecheck = new Promise((resolve) => {
            resolveRecheck = resolve;
        });
        directionMocks.fetchDirectionEntryMethods
            .mockResolvedValueOnce(methodsPayload(false))
            .mockReturnValueOnce(pendingRecheck as never);
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        // the recheck is still in flight: NO stale «недоступна» note, honest unknown
        expect(screen.queryByTestId('setup-qr-not-bookable-note-lab')).toBeNull();
        expect(screen.getByTestId('setup-qr-unknown-lab')).toBeTruthy();
        // the recheck answers: the direction became bookable
        await React.act(async () => {
            resolveRecheck(methodsPayload(true));
        });
        await waitFor(() => {
            expect(screen.queryByTestId('setup-qr-unknown-lab')).toBeNull();
        });
        expect(screen.queryByTestId('setup-qr-not-bookable-note-lab')).toBeNull();
    });

    it('PIN 8b: after provision the entry-methods are re-read — the not-bookable note disappears when the direction became bookable', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.fetchDirectionEntryMethods
            .mockResolvedValueOnce(methodsPayload(false))
            .mockResolvedValueOnce(methodsPayload(true));
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        // the recheck happened against the right direction
        await waitFor(() => {
            expect(directionMocks.fetchDirectionEntryMethods).toHaveBeenCalledWith('lab-key');
        });
        // freshly provisioned healthy direction: NO stale «недоступна» note
        await waitFor(() => {
            expect(screen.queryByTestId('setup-qr-not-bookable-note-lab')).toBeNull();
        });
    });

    it('PIN 9: the recheck is honest in the reverse race — supported=false after provision keeps the note', async () => {
        setupApiMock({ data: methodsPayload(false) });
        mockRecheck(false);
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-not-bookable-note-lab')).toBeTruthy();
        });
    });

    it('PIN 10 (round-2 P2): a failed recheck renders the honest UNKNOWN state in the QR block', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.fetchDirectionEntryMethods
            .mockResolvedValueOnce(methodsPayload(false))
            .mockRejectedValueOnce(new Error('recheck failed'));
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        // honest unknown banner (read failed), QR stays shown
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-unknown-lab')).toBeTruthy();
        });
        expect(screen.queryByTestId('setup-qr-not-bookable-note-lab')).toBeNull();
    });

    it('PIN 11: a profile with multiple queue tags still has one QR disclosure and one QR block', async () => {
        directionMocks.fetchAdminQueueDirections.mockResolvedValue({
            as_of_day: '2026-10-18',
            directions: [{
                ...ADMIN_DIRECTION,
                profile: { ...ADMIN_DIRECTION.profile, queue_tags: ['lab', 'lab_extra'] },
            }],
            unattached: { queue_tags: [], services: [], resources: [] },
        });
        directionMocks.fetchDirectionEntryMethods.mockResolvedValue(methodsPayload(false));
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        await screen.findByTestId('setup-checklist-row-lab');
        await screen.findByTestId('setup-qr-block-lab');
        const blocks = screen.getAllByTestId(/^setup-qr-block-/).filter((el) =>
            el.getAttribute('data-testid')?.startsWith('setup-qr-block-'),
        );
        expect(blocks.length).toBe(1);
        expect(screen.queryByTestId('setup-qr-block-lab_extra')).toBeNull();
    });

    it('updates the address-exists fact after successful provisioning', async () => {
        setupApiMock({ data: methodsPayload(false) });
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        await renderScreen();
        const row = () => screen.getByTestId('setup-row-permanent-address');
        expect(row()).toHaveTextContent('Нет');
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        await waitFor(() => {
            expect(row()).toHaveTextContent('Да');
        });
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-expand-lab')).toHaveTextContent('Проверить постоянный QR');
        });
        expect(screen.queryByText('Создать постоянный адрес QR')).toBeNull();
    });

    it('keeps an existing permanent QR inspectable when the public entry-methods read rejects for an archived direction', async () => {
        directionMocks.fetchAdminQueueDirections.mockResolvedValue({
            as_of_day: '2026-10-18',
            directions: [{
                ...ADMIN_DIRECTION,
                profile: { ...ADMIN_DIRECTION.profile, is_active: false },
                public_availability: false,
                permanent_address_exists: true,
                allowed_next_actions: [],
            }],
            unattached: { queue_tags: [], services: [], resources: [] },
        });
        directionMocks.fetchDirectionEntryMethods.mockRejectedValue(new Error('archived profile is not publicly selectable'));
        directionMocks.provisionPublicAddress.mockResolvedValue({
            ...PROVISION_RESPONSE,
            created: false,
        });

        await renderScreen({ expandQr: false });
        const inspectButton = await screen.findByTestId('setup-qr-expand-lab');
        expect(inspectButton).toHaveTextContent('Проверить постоянный QR');
        await userEvent.setup().click(inspectButton);

        expect(await screen.findByTestId('setup-qr-block-lab')).toBeTruthy();
        await userEvent.setup().click(await screen.findByTestId('setup-qr-show-lab'));
        expect(await screen.findByTestId('setup-qr-image-lab')).toBeTruthy();
        expect(screen.getByTestId('setup-qr-url-lab')).toHaveTextContent('/q/abcd1234efgh');
        expect(await screen.findByTestId('setup-qr-not-bookable-note-lab')).toBeTruthy();
        expect(directionMocks.provisionPublicAddress).toHaveBeenCalledWith('lab-key');
        expect(directionMocks.fetchDirectionEntryMethods).not.toHaveBeenCalled();
    });

    it('drops a stale per-profile QR response after a newer full read', async () => {
        setupApiMock({ data: methodsPayload(false) });
        let resolveOldRead: (value: unknown) => void = () => {};
        const oldRead = new Promise((resolve) => {
            resolveOldRead = resolve;
        });
        directionMocks.fetchDirectionEntryMethods
            .mockImplementationOnce(() => oldRead as never)
            .mockResolvedValueOnce(methodsPayload(false));
        await renderScreen({ expandQr: false });
        await screen.findByTestId('setup-checklist-row-lab');
        await userEvent.setup().click(screen.getByTestId('setup-qr-expand-lab'));
        await waitFor(() => expect(directionMocks.fetchDirectionEntryMethods).toHaveBeenCalledTimes(1));

        await userEvent.setup().click(screen.getByTestId('setup-refresh'));
        await waitFor(() => expect(directionMocks.fetchAdminQueueDirections).toHaveBeenCalledTimes(2));
        await screen.findByTestId('setup-checklist-row-lab');
        await userEvent.setup().click(screen.getByTestId('setup-qr-expand-lab'));
        await React.act(async () => resolveOldRead(methodsPayload(true)));
        await waitFor(() => expect(directionMocks.fetchDirectionEntryMethods).toHaveBeenCalledTimes(2));
        expect(await screen.findByTestId('setup-qr-provision-lab')).toBeVisible();
        await React.act(async () => {});
        expect(screen.getByTestId('setup-qr-provision-lab')).toBeVisible();
        expect(screen.queryByTestId('setup-qr-show-lab')).toBeNull();
    });

    it('PIN 37 (round-5 P2-2): a LATE provision response never paints the block-local unknown over a fresher full read', async () => {
        // The exact round-5 review race, driven on the CHILD contract
        // directly (a full-page refresh unmounts the block, so the
        // parent-composition test cannot reach this window):
        //   R1 provision starts at generation 1 → a newer full read lands
        //   (generation 2, supported=false) → R1's provision resolves LATE
        //   → the pre-fix child unconditionally set its local override to
        //   null (unknown) and the stale recheck's early return never
        //   cleaned it up — the block stayed on «статус неизвестен» until
        //   the next Refresh. The generation-tagged override makes the
        //   stale local state inert.
        let resolveRecheck: (value: unknown) => void = () => {};
        const pendingRecheck = new Promise((resolve) => {
            resolveRecheck = resolve;
        });
        directionMocks.fetchDirectionEntryMethods.mockReturnValue(pendingRecheck as never);
        let resolveProvision: (value: unknown) => void = () => {};
        const pendingProvision = new Promise((resolve) => {
            resolveProvision = resolve;
        });
        directionMocks.provisionPublicAddress.mockReturnValue(pendingProvision as never);

        const view = render(
            <ThemeProvider>
                <MemoryRouter>
                    <PermanentDirectionQr
                        profileKey="lab-key"
                        tag="lab"
                        supported={false}
                        supportGeneration={1}
                    />
                </MemoryRouter>
            </ThemeProvider>,
        );

        // R1 provision starts (generation 1) and hangs
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-provision-lab').hasAttribute('disabled')).toBe(
                true,
            );
        });

        // THE NEWER FULL READ: generation 2 lands with supported=false
        view.rerender(
            <ThemeProvider>
                <MemoryRouter>
                    <PermanentDirectionQr
                        profileKey="lab-key"
                        tag="lab"
                        supported={false}
                        supportGeneration={2}
                    />
                </MemoryRouter>
            </ThemeProvider>,
        );
        await React.act(async () => {});

        // R1's provision resolves LATE — after the fresh generation landed
        await React.act(async () => {
            resolveProvision(PROVISION_RESPONSE);
        });
        await screen.findByTestId('setup-qr-image-lab');
        // pre-fix: the block painted its own unknown banner here and kept
        // it until the next Refresh. Round-5: the gen-1 override is inert —
        // the fresh gen-2 answer (false) owns the block.
        expect(screen.queryByTestId('setup-qr-unknown-lab')).toBeNull();
        expect(screen.getByTestId('setup-qr-not-bookable-note-lab')).toBeTruthy();

        // the STALE recheck also resolves — still no lingering unknown
        await React.act(async () => {
            resolveRecheck(methodsPayload(true));
        });
        await React.act(async () => {});
        expect(screen.queryByTestId('setup-qr-unknown-lab')).toBeNull();
        expect(screen.getByTestId('setup-qr-not-bookable-note-lab')).toBeTruthy();
    });
});
