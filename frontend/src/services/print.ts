/**
 * Сервис печати документов
 * Централизованная работа с принтерами и документами
 */
import { api } from '../api/client';
import { getErrorMessage } from '../utils/type-guards';

const normalizePrintResponse = (responseData: Record<string, unknown>, fallbackErrorMessage: string) => {
  if (responseData?.success === false) {
    return {
      success: false,
      error: responseData.error || responseData.message || fallbackErrorMessage,
      data: responseData
    };
  }

  return {
    success: true,
    data: responseData
  };
};

const normalizePrintError = (error: unknown, fallbackMessage: string) => ({
  success: false,
  error: getErrorMessage(error) || fallbackMessage
});

/**
 * RETRO-3921-01 (consolidated post-merge review of PR 3921):
 * distinguish a DEFINITE negative answer from an UNKNOWN transport result.
 *
 * A rejection is a definite failure ONLY when the server answered (an HTTP
 * error status reached the client): the print pipeline refused the job, so
 * the operator-driven PDF fallback may proceed. A rejection WITHOUT a
 * response — client timeout, dropped connection mid-flight, abort — is an
 * UNKNOWN outcome: the server may have already accepted and queued the
 * physical job, so the result is reported ambiguous and the caller must
 * NOT open a second print route.
 */
const isUnknownTransportOutcome = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return true;
  }
  const err = error as { response?: unknown };
  // A server answer (even an error status) is a definite negative ACK.
  if (err.response !== undefined && err.response !== null) {
    return false;
  }
  // No response at all: timeout, connection lost, abort — unknown fate.
  return true;
};

export const printService = {
  /**
   * Получение списка принтеров
   */
  async getPrinters() {
    try {
      const response = await api.get('/print/printers');
      
      return {
        success: true,
        data: response.data.printers || []
      };
    } catch (error) {
      return normalizePrintError(error, 'Ошибка получения принтеров');
    }
  },

  /**
   * Печать талона очереди
   */
  async printTicket(ticketData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/ticket', ticketData);

      return normalizePrintResponse(response.data, 'Ошибка печати талона');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати талона');
    }
  },

  /**
   * Печать рецепта (PDF)
   */
  async printPrescription(prescriptionData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/prescription', prescriptionData);

      return normalizePrintResponse(response.data, 'Ошибка печати рецепта');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати рецепта');
    }
  },

  /**
   * Печать справки
   */
  async printCertificate(certificateData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/certificate', certificateData);

      return normalizePrintResponse(response.data, 'Ошибка печати справки');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати справки');
    }
  },

  /**
   * Печать лабораторного бланка.
   *
   * LABPRINT-FE-001 (audit 3886, round 14): отправляется ТОЛЬКО
   * авторизованный идентификатор отчёта (+ опция принтера) — сервер
   * материализует значения из БД тем же пайплайном, что канонический
   * /lab/report-instances/{id}/pdf. Клиентские значения больше не
   * передаются и не рендерятся.
   *
   * LABPRINT-FE-003 (audit 3886, round 14): строгий ACK. Прежний
   * «non-false»-нормализатор (normalizePrintResponse) считал успехом
   * ЛЮБОЙ 2xx без явного success:false — {}/{success:null} синтезировали
   * подтверждение и UI помечал отчёт PRINTED без подтверждённого задания
   * печати. Теперь успех только при success === true; 2xx без
   * положительного ACK — честный ambiguous-отказ (задание могло уже
   * встать в очередь: никакого слепого повтора/автофолбэка).
   */
  async printLabResults(command: { report_instance_id: number; printer_name?: string | null }) {
    try {
      const response = await api.post('/print/lab-results', command);
      const payload = (response?.data ?? null) as Record<string, unknown> | null;
      if (payload && payload.success === true) {
        return { success: true, data: payload };
      }
      if (payload && payload.success === false) {
        return {
          success: false,
          ambiguous: false,
          error: (payload.error as string) || (payload.message as string) || 'Ошибка печати лабораторных результатов',
          data: payload,
        };
      }
      return {
        success: false,
        ambiguous: true,
        error: 'print_ack_unconfirmed',
        data: payload,
      };
    } catch (error) {
      // RETRO-3921-01: a missing transport result (timeout, connection
      // dropped after the server may have queued the job, abort) is NOT a
      // definite refusal — report it ambiguous so the caller stops the
      // fallback instead of opening a second print route. Only a
      // server-RETURNED error (definite negative ACK / validation refusal)
      // remains a known failure.
      if (isUnknownTransportOutcome(error)) {
        return {
          success: false,
          ambiguous: true,
          error: 'print_ack_unconfirmed',
          data: null,
        };
      }
      // Известный отказ транспорта — не ambiguous.
      return { ...normalizePrintError(error, 'Ошибка печати лабораторных результатов'), ambiguous: false };
    }
  },

  /**
   * Печать чека
   */
  async printReceipt(receiptData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/receipt', receiptData);

      return normalizePrintResponse(response.data, 'Ошибка печати чека');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка печати чека');
    }
  },

  /**
   * Быстрая печать
   */
  async quickPrint(text: string, printerName = 'default') {
    return {
      success: false,
      error:
        'Generic quickPrint is deprecated. Use printTicket, printReceipt, quickQueueTicket, or quickPaymentReceipt.'
    };
  },

  /**
   * Быстрая печать талона очереди
   */
  async quickQueueTicket(ticketData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/quick/queue-ticket', ticketData);

      return normalizePrintResponse(response.data, 'Ошибка быстрой печати талона');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка быстрой печати талона');
    }
  },

  /**
   * Быстрая печать чека
   */
  async quickPaymentReceipt(receiptData: Record<string, unknown>) {
    try {
      const response = await api.post('/print/quick/payment-receipt', receiptData);

      return normalizePrintResponse(response.data, 'Ошибка быстрой печати чека');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка быстрой печати чека');
    }
  },

  /**
   * Получение шаблонов печати
   */
  async getTemplates(templateType: string, language = 'ru') {
    try {
      const response = await api.get('/print/templates/templates', {
        params: { template_type: templateType, language }
      });
      
      return {
        success: true,
        data: response.data
      };
    } catch (error) {
      return normalizePrintError(error, 'Ошибка получения шаблонов');
    }
  },

  /**
   * Проверка статуса принтера
   */
  async checkPrinterStatus(printerName: string) {
    try {
      const response = await api.get(`/print/printers/${printerName}/status`);

      return normalizePrintResponse(response.data, 'Ошибка проверки принтера');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка проверки принтера');
    }
  },

  /**
   * Тестовая печать
   */
  async testPrint(printerName: string) {
    try {
      const response = await api.post(
        `/print/printers/${encodeURIComponent(printerName)}/test`
      );

      return normalizePrintResponse(response.data, 'Ошибка тестовой печати');
    } catch (error) {
      return normalizePrintError(error, 'Ошибка тестовой печати');
    }
  }
};
