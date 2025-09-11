import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Card,
  CardContent,
  Typography,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Grid,
  Paper,
  Chip
} from '@mui/material';
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts';

const AdvancedCharts = ({ data, type = 'line', title, height = 300 }) => {
  const [chartType, setChartType] = useState(type);
  const [selectedPeriod, setSelectedPeriod] = useState('7d');
  const chartRef = useRef(null);

  const chartTypes = [
    { value: 'line', label: 'Линейный график' },
    { value: 'area', label: 'Областной график' },
    { value: 'bar', label: 'Столбчатая диаграмма' },
    { value: 'pie', label: 'Круговая диаграмma' }
  ];

  const periods = [
    { value: '1d', label: '1 день' },
    { value: '7d', label: '7 дней' },
    { value: '30d', label: '30 дней' },
    { value: '90d', label: '90 дней' }
  ];

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  const renderChart = () => {
    const commonProps = {
      data: data,
      margin: { top: 5, right: 30, left: 20, bottom: 5 }
    };

    switch (chartType) {
      case 'line':
        return (
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Line 
              type="monotone" 
              dataKey="value" 
              stroke="#8884d8" 
              strokeWidth={2}
              dot={{ fill: '#8884d8', strokeWidth: 2, r: 4 }}
            />
          </LineChart>
        );
      
      case 'area':
        return (
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Area 
              type="monotone" 
              dataKey="value" 
              stroke="#8884d8" 
              fill="#8884d8"
              fillOpacity={0.3}
            />
          </AreaChart>
        );
      
      case 'bar':
        return (
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="name" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="value" fill="#8884d8" />
          </BarChart>
        );
      
      case 'pie':
        return (
          <PieChart {...commonProps}>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip />
            <Legend />
          </PieChart>
        );
      
      default:
        return null;
    }
  };

  const getChartDescription = () => {
    switch (chartType) {
      case 'line':
        return 'Показывает тренды и изменения данных во времени';
      case 'area':
        return 'Визуализирует объем данных с заливкой области';
      case 'bar':
        return 'Сравнивает значения между различными категориями';
      case 'pie':
        return 'Отображает пропорциональное распределение данных';
      default:
        return '';
    }
  };

  return (
    <Card sx={{ height: '100%' }}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
          <Typography variant="h6" component="h3">
            {title || 'Аналитическая диаграмма'}
          </Typography>
          <Chip 
            label={getChartDescription()} 
            size="small" 
            color="primary" 
            variant="outlined"
          />
        </Box>

        <Grid container spacing={2} mb={2}>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth size="small">
              <InputLabel>Тип диаграммы</InputLabel>
              <Select
                value={chartType}
                label="Тип диаграммы"
                onChange={(e) => setChartType(e.target.value)}
              >
                {chartTypes.map((type) => (
                  <MenuItem key={type.value} value={type.value}>
                    {type.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
          <Grid item xs={12} sm={6}>
            <FormControl fullWidth size="small">
              <InputLabel>Период</InputLabel>
              <Select
                value={selectedPeriod}
                label="Период"
                onChange={(e) => setSelectedPeriod(e.target.value)}
              >
                {periods.map((period) => (
                  <MenuItem key={period.value} value={period.value}>
                    {period.label}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          </Grid>
        </Grid>

        <Paper 
          sx={{ 
            p: 2, 
            height: height, 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center' 
          }}
        >
          {data && data.length > 0 ? (
            <ResponsiveContainer width="100%" height="100%">
              {renderChart()}
            </ResponsiveContainer>
          ) : (
            <Typography variant="body2" color="text.secondary">
              Нет данных для отображения
            </Typography>
          )}
        </Paper>

        <Box mt={2} display="flex" justifyContent="space-between" alignItems="center">
          <Typography variant="caption" color="text.secondary">
            Период: {periods.find(p => p.value === selectedPeriod)?.label}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            Обновлено: {new Date().toLocaleTimeString()}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export default AdvancedCharts;
