/**
 * CSH-FE-051 (follow-up audit 2026-11-02): бейдж типа возврата честен
 * для каждого значения канонического RefundType бэкенда
 * (bank_transfer | deposit | cash) и для неизвестных значений.
 *
 * Red-first: на префиксном коде всё, кроме `deposit`, рисовалось как
 * «На карту» — наличный возврат выдавал себя за карточный.
 */
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { getRefundTypeBadge } from '../refundRequestsColumns';

const t = (key: string) => key;

describe('CSH-FE-051: refund type badge vocabulary', () => {
  it('deposit → «На депозит»', () => {
    render(<div>{getRefundTypeBadge('deposit', t)}</div>);
    expect(screen.getByText('misc.rrt_na_depozit')).toBeInTheDocument();
  });

  it('bank_transfer → «На карту» (honest for a bank transfer)', () => {
    render(<div>{getRefundTypeBadge('bank_transfer', t)}</div>);
    expect(screen.getByText('misc.rrt_na_kartu')).toBeInTheDocument();
  });

  it('cash → «Наличными», NOT «На карту»', () => {
    render(<div>{getRefundTypeBadge('cash', t)}</div>);
    expect(screen.getByText('misc.rrt_nalichnymi')).toBeInTheDocument();
    expect(screen.queryByText('misc.rrt_na_kartu')).not.toBeInTheDocument();
  });

  it('unknown value → honest «Неизвестно», not a fabricated card label', () => {
    render(<div>{getRefundTypeBadge('crypto', t)}</div>);
    expect(screen.getByText('misc.rrt_unknown')).toBeInTheDocument();
    expect(screen.queryByText('misc.rrt_na_kartu')).not.toBeInTheDocument();
  });

  it('null → honest «Неизвестно»', () => {
    render(<div>{getRefundTypeBadge(null, t)}</div>);
    expect(screen.getByText('misc.rrt_unknown')).toBeInTheDocument();
  });
});
