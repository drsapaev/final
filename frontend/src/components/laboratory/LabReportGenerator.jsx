/**
 * Lab Report Generator Component
 * Генератор отчетов лабораторных исследований
 * Согласно MASTER_TODO_LIST строка 288
 */
import React, { useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  Button,
  Grid,
  Paper,
  Divider,
  Alert,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
} from '@mui/material';
import {
  PictureAsPdf,
  Print,
  Email,
  CheckCircle,
  Warning,
  TrendingUp,
  TrendingDown,
  Science,
  LocalHospital,
} from '@mui/icons-material';
import { jsPDF } from 'jspdf';
import 'jspdf-autotable';
import { api } from '../../api/client';

const LabReportGenerator = ({ 
  results = [], 
  patient = {}, 
  doctor = {}, 
  clinic = {},
  visitId 
}) => {
  const [generating, setGenerating] = useState(false);

  // Группировка результатов по категориям
  const groupResultsByCategory = () => {
    const grouped = {};
    results.forEach(result => {
      if (!grouped[result.category]) {
        grouped[result.category] = [];
      }
      grouped[result.category].push(result);
    });
    return grouped;
  };

  // Генерация PDF
  const generatePDF = async () => {
    setGenerating(true);
    
    try {
      const doc = new jsPDF();
      
      // Заголовок
      doc.setFontSize(20);
      doc.text(clinic.name || 'Медицинская клиника', 105, 20, { align: 'center' });
      
      doc.setFontSize(16);
      doc.text('Результаты лабораторных исследований', 105, 30, { align: 'center' });
      
      // Информация о пациенте
      doc.setFontSize(12);
      doc.text(`Пациент: ${patient.name || 'Не указан'}`, 20, 50);
      doc.text(`Дата рождения: ${patient.birthDate || 'Не указана'}`, 20, 57);
      doc.text(`Телефон: ${patient.phone || 'Не указан'}`, 20, 64);
      
      // Информация о враче
      doc.text(`Врач: ${doctor.name || 'Не указан'}`, 120, 50);
      doc.text(`Специальность: ${doctor.specialty || 'Не указана'}`, 120, 57);
      doc.text(`Дата: ${new Date().toLocaleDateString()}`, 120, 64);
      
      // Линия
      doc.line(20, 70, 190, 70);
      
      // Результаты по категориям
      let yPosition = 80;
      const groupedResults = groupResultsByCategory();
      
      Object.entries(groupedResults).forEach(([category, categoryResults]) => {
        // Заголовок категории
        doc.setFontSize(14);
        doc.setFont(undefined, 'bold');
        doc.text(getCategoryName(category), 20, yPosition);
        yPosition += 10;
        
        // Таблица результатов
        const tableData = categoryResults.map(result => [
          result.test_name,
          `${result.value} ${result.unit}`,
          `${result.reference_min}-${result.reference_max} ${result.unit}`,
          getStatusText(result.status),
        ]);
        
        doc.autoTable({
          startY: yPosition,
          head: [['Исследование', 'Результат', 'Норма', 'Статус']],
          body: tableData,
          theme: 'striped',
          headStyles: { fillColor: [66, 139, 202] },
          columnStyles: {
            0: { cellWidth: 70 },
            1: { cellWidth: 40 },
            2: { cellWidth: 40 },
            3: { cellWidth: 30 },
          },
          didDrawCell: (data) => {
            // Выделение отклонений красным
            if (data.column.index === 3 && data.cell.raw === 'Отклонение') {
              doc.setTextColor(255, 0, 0);
            }
          },
        });
        
        yPosition = doc.lastAutoTable.finalY + 10;
        doc.setFont(undefined, 'normal');
        
        // Проверка на новую страницу
        if (yPosition > 250) {
          doc.addPage();
          yPosition = 20;
        }
      });
      
      // Заключение
      const abnormalResults = results.filter(r => r.status === 'abnormal');
      if (abnormalResults.length > 0) {
        doc.setFontSize(14);
        doc.setFont(undefined, 'bold');
        doc.text('Внимание! Обнаружены отклонения:', 20, yPosition);
        yPosition += 10;
        
        doc.setFontSize(11);
        doc.setFont(undefined, 'normal');
        abnormalResults.forEach(result => {
          doc.text(`• ${result.test_name}: ${result.value} ${result.unit}`, 25, yPosition);
          yPosition += 6;
        });
      }
      
      // Подпись
      doc.setFontSize(10);
      doc.text('Результаты действительны на момент исследования.', 20, 270);
      doc.text('Интерпретацию результатов проводит лечащий врач.', 20, 275);
      
      // Сохранение
      doc.save(`lab_results_${patient.name}_${new Date().toISOString().split('T')[0]}.pdf`);
      
    } catch (error) {
      console.error('Ошибка генерации PDF:', error);
    } finally {
      setGenerating(false);
    }
  };

  // Печать отчета
  const printReport = () => {
    window.print();
  };

  // Отправка по email
  const sendByEmail = async () => {
    try {
      await api.post(`/visits/${visitId}/lab-results/email`, {
        patient_email: patient.email,
      });
      alert('Отчет отправлен на email пациента');
    } catch (error) {
      console.error('Ошибка отправки email:', error);
    }
  };

  // Получение названия категории
  const getCategoryName = (category) => {
    const names = {
      blood: 'Анализы крови',
      urine: 'Анализы мочи',
      biochemistry: 'Биохимия',
      hormones: 'Гормоны',
      other: 'Другие исследования',
    };
    return names[category] || category;
  };

  // Получение текста статуса
  const getStatusText = (status) => {
    const texts = {
      pending: 'Ожидается',
      in_progress: 'В работе',
      completed: 'Норма',
      abnormal: 'Отклонение',
    };
    return texts[status] || status;
  };

  // Статистика результатов
  const getStatistics = () => {
    const total = results.length;
    const normal = results.filter(r => r.status === 'completed').length;
    const abnormal = results.filter(r => r.status === 'abnormal').length;
    const pending = results.filter(r => r.status === 'pending' || r.status === 'in_progress').length;
    
    return { total, normal, abnormal, pending };
  };

  const stats = getStatistics();
  const groupedResults = groupResultsByCategory();

  return (
    <Box className="lab-report-generator">
      <Card>
        <CardContent>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h6">
              <Science sx={{ mr: 1, verticalAlign: 'middle' }} />
              Отчет по анализам
            </Typography>
            
            <Box sx={{ display: 'flex', gap: 1 }}>
              <Button
                variant="contained"
                startIcon={<PictureAsPdf />}
                onClick={generatePDF}
                disabled={generating || results.length === 0}
              >
                Скачать PDF
              </Button>
              <Button
                variant="outlined"
                startIcon={<Print />}
                onClick={printReport}
                disabled={results.length === 0}
              >
                Печать
              </Button>
              <Button
                variant="outlined"
                startIcon={<Email />}
                onClick={sendByEmail}
                disabled={!patient.email || results.length === 0}
              >
                Email
              </Button>
            </Box>
          </Box>

          {/* Статистика */}
          <Grid container spacing={2} sx={{ mb: 3 }}>
            <Grid item xs={3}>
              <Paper sx={{ p: 2, textAlign: 'center' }}>
                <Typography variant="h4">{stats.total}</Typography>
                <Typography variant="caption" color="text.secondary">
                  Всего анализов
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={3}>
              <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'success.light' }}>
                <Typography variant="h4">{stats.normal}</Typography>
                <Typography variant="caption">
                  В норме
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={3}>
              <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'error.light' }}>
                <Typography variant="h4">{stats.abnormal}</Typography>
                <Typography variant="caption">
                  Отклонения
                </Typography>
              </Paper>
            </Grid>
            <Grid item xs={3}>
              <Paper sx={{ p: 2, textAlign: 'center', bgcolor: 'warning.light' }}>
                <Typography variant="h4">{stats.pending}</Typography>
                <Typography variant="caption">
                  Ожидается
                </Typography>
              </Paper>
            </Grid>
          </Grid>

          {/* Предпросмотр отчета для печати */}
          <Paper sx={{ p: 3, display: 'none', '@media print': { display: 'block' } }}>
            <Typography variant="h5" align="center" gutterBottom>
              {clinic.name || 'Медицинская клиника'}
            </Typography>
            <Typography variant="h6" align="center" gutterBottom>
              Результаты лабораторных исследований
            </Typography>
            
            <Divider sx={{ my: 2 }} />
            
            <Grid container spacing={2}>
              <Grid item xs={6}>
                <Typography><strong>Пациент:</strong> {patient.name}</Typography>
                <Typography><strong>Дата рождения:</strong> {patient.birthDate}</Typography>
                <Typography><strong>Телефон:</strong> {patient.phone}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography><strong>Врач:</strong> {doctor.name}</Typography>
                <Typography><strong>Дата:</strong> {new Date().toLocaleDateString()}</Typography>
              </Grid>
            </Grid>
            
            <Divider sx={{ my: 2 }} />
            
            {Object.entries(groupedResults).map(([category, categoryResults]) => (
              <Box key={category} sx={{ mb: 3 }}>
                <Typography variant="h6" gutterBottom>
                  {getCategoryName(category)}
                </Typography>
                
                <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                  <thead>
                    <tr>
                      <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>
                        Исследование
                      </th>
                      <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>
                        Результат
                      </th>
                      <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>
                        Норма
                      </th>
                      <th style={{ border: '1px solid #ddd', padding: '8px', textAlign: 'left' }}>
                        Статус
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {categoryResults.map((result, index) => (
                      <tr key={index}>
                        <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                          {result.test_name}
                        </td>
                        <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                          {result.value} {result.unit}
                        </td>
                        <td style={{ border: '1px solid #ddd', padding: '8px' }}>
                          {result.reference_min}-{result.reference_max} {result.unit}
                        </td>
                        <td style={{ 
                          border: '1px solid #ddd', 
                          padding: '8px',
                          color: result.status === 'abnormal' ? 'red' : 'inherit'
                        }}>
                          {getStatusText(result.status)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Box>
            ))}
          </Paper>

          {/* Предпросмотр на экране */}
          <Paper sx={{ p: 2, '@media print': { display: 'none' } }}>
            <Typography variant="subtitle1" gutterBottom>
              Предпросмотр отчета
            </Typography>
            
            {Object.entries(groupedResults).map(([category, categoryResults]) => (
              <Box key={category} sx={{ mb: 2 }}>
                <Typography variant="subtitle2" color="primary" gutterBottom>
                  {getCategoryName(category)}
                </Typography>
                
                <List dense>
                  {categoryResults.map((result, index) => (
                    <ListItem key={index}>
                      <ListItemIcon>
                        {result.status === 'abnormal' ? (
                          <Warning color="error" />
                        ) : (
                          <CheckCircle color="success" />
                        )}
                      </ListItemIcon>
                      <ListItemText
                        primary={result.test_name}
                        secondary={
                          <Box sx={{ display: 'flex', gap: 2 }}>
                            <Typography variant="caption">
                              Результат: {result.value} {result.unit}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              Норма: {result.reference_min}-{result.reference_max}
                            </Typography>
                          </Box>
                        }
                      />
                    </ListItem>
                  ))}
                </List>
              </Box>
            ))}
            
            {stats.abnormal > 0 && (
              <Alert severity="warning" sx={{ mt: 2 }}>
                Обнаружено {stats.abnormal} отклонений от нормы. 
                Рекомендуется консультация специалиста.
              </Alert>
            )}
          </Paper>
        </CardContent>
      </Card>
    </Box>
  );
};

export default LabReportGenerator;

