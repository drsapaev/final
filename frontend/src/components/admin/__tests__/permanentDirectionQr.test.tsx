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
 */
import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
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
    provisionPublicAddress: vi.fn(),
}));

vi.mock('../../../api/queueDirections', () => directionMocks);

vi.mock('qrcode.react', () => ({
    QRCodeSVG: (props: { value?: string; 'data-testid'?: string }) => (
        <div data-testid={props['data-testid'] || 'qr-svg'} data-qr-value={props.value} />
    ),
}));

import AdminSetupDirections from '../AdminSetupDirections';

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

function setupApiMock(entryMethods: { data: unknown } | null) {
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
}

function renderScreen() {
    return render(
        <ThemeProvider>
            <MemoryRouter>
                <AdminSetupDirections />
            </MemoryRouter>
        </ThemeProvider>,
    );
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
});

describe('RQ-18 — permanent direction QR admin surface', () => {
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
        renderScreen();
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-block-lab')).toBeTruthy();
        });
    });

    it('PIN 2: provision response renders the QR image and the /q/<code> URL', async () => {
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
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        renderScreen();
        const btn = await screen.findByTestId('setup-qr-provision-lab');
        fireEvent.click(btn);
        expect(await screen.findByTestId('setup-qr-image-lab')).toBeTruthy();
        expect(screen.getByTestId('setup-qr-url-lab').textContent).toContain('/q/abcd1234efgh');
        expect(directionMocks.provisionPublicAddress).toHaveBeenCalledWith('lab-key');
    });

    it('PIN 3: re-provision (reload recovery) keeps the SAME code (created=false path)', async () => {
        setupApiMock({
            data: {
                direction_key: 'lab-key',
                entry_methods: [
                    { method: 'session_qr', supported: true },
                    { method: 'permanent_address', supported: true },
                    { method: 'view_only', supported: true },
                ],
            },
        });
        directionMocks.provisionPublicAddress.mockResolvedValue({
            ...PROVISION_RESPONSE,
            created: false,
        });
        renderScreen();
        // supported=true → «Показать QR» (idempotent re-provision recovery)
        const btn = await screen.findByTestId('setup-qr-show-lab');
        fireEvent.click(btn);
        expect(await screen.findByTestId('setup-qr-image-lab')).toBeTruthy();
        expect(screen.getByTestId('setup-qr-url-lab').textContent).toContain('/q/abcd1234efgh');
        expect(directionMocks.provisionPublicAddress).toHaveBeenCalledTimes(1);
    });

    it('PIN 4: QR payload is the absolute canonical frontend origin + /q/<public_code>', async () => {
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
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        const qr = screen.getByTestId('setup-qr-image-lab').querySelector('[data-qr-value]');
        expect(qr?.getAttribute('data-qr-value')).toBe(
            `${window.location.origin}/q/abcd1234efgh`,
        );
    });

    it('PIN 5: entry-methods read failure renders honest unknown — never «not provisioned»', async () => {
        setupApiMock(null);
        renderScreen();
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-unknown-lab')).toBeTruthy();
        });
        expect(screen.queryByTestId('setup-qr-provision-lab')).toBeNull();
    });

    it('PIN 6: the permanent surface never shows expiry/TTL phrasing and always the non-token note', async () => {
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
        directionMocks.provisionPublicAddress.mockResolvedValue(PROVISION_RESPONSE);
        const { container } = renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await screen.findByTestId('setup-qr-image-lab');
        const block = screen.getByTestId('setup-qr-block-lab');
        expect(block.textContent).not.toMatch(/истек|действует до|expires|TTL|срок/i);
        expect(screen.getByTestId('setup-qr-permanent-note-lab')).toBeTruthy();
        // honest success/error not by color alone: textual state markers exist
        expect(container.querySelector('[data-testid="setup-qr-url-lab"]')).toBeTruthy();
    });

    it('PIN 6b: created=false while supported=false → QR shown WITH an honest not-bookable note', async () => {
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
        directionMocks.provisionPublicAddress.mockResolvedValue({
            ...PROVISION_RESPONSE,
            created: false,
        });
        renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        expect(await screen.findByTestId('setup-qr-image-lab')).toBeTruthy();
        expect(screen.getByTestId('setup-qr-not-bookable-note-lab')).toBeTruthy();
    });

    it('PIN 6c: provision failure shows an explicit error — no silent fake success', async () => {
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
        directionMocks.provisionPublicAddress.mockRejectedValue(
            new Error('provision refused'),
        );
        renderScreen();
        fireEvent.click(await screen.findByTestId('setup-qr-provision-lab'));
        await waitFor(() => {
            expect(screen.getByTestId('setup-qr-error-lab')).toBeTruthy();
        });
        expect(screen.queryByTestId('setup-qr-image-lab')).toBeNull();
    });

    it('PIN 7-loop: checklist load does NOT loop — GET count stays bounded (pre-existing main defect found by the QR state pin)', async () => {
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
        renderScreen();
        await screen.findByTestId('setup-qr-provision-lab');
        await new Promise((r) => setTimeout(r, 400));
        // main pre-fix: 360+ GETs in 400ms (infinite loadCore refire loop);
        // fixed: one load cycle settles — a handful of reads, no growth.
        const calls = apiMocks.get.mock.calls.length;
        expect(calls).toBeGreaterThan(0);
        expect(calls).toBeLessThanOrEqual(8);
    });
});
