import React, { useEffect, useRef, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from './ui/tabs';
import { Button } from './ui/button';
import { Download, RefreshCw, BarChart3, PieChart, TrendingUp, Activity } from 'lucide-react';

// Динамический импорт Chart.js для оптимизации
let Chart = null;
const loadChart = async () => {
  if (!Chart) {
    const { Chart: ChartJS, registerables } = await import('chart.js');
    ChartJS.register(...registerables);
    Chart = ChartJS;
  }
  return Chart;
};

const AnalyticsCharts = ({ 
  data, 
  loading = false, 
  onRefresh,
  onExport,
  title = "Аналитические графики"
}) => {
  const chartRefs = useRef({});
  const [activeTab, setActiveTab] = useState('overview');
  const [chartsLoaded, setChartsLoaded] = useState(false);

  useEffect(() => {
    loadChart().then(() => setChartsLoaded(true));
  }, []);

  useEffect(() => {
    if (chartsLoaded && data?.charts) {
      renderCharts();
    }
  }, [chartsLoaded, data, activeTab]);

  const renderCharts = async () => {
    if (!Chart || !data?.charts) return;

    // Уничтожаем существующие графики
    Object.values(chartRefs.current).forEach(chart => {
      if (chart) chart.destroy();
    });
    chartRefs.current = {};

    // Рендерим новые графики
    for (const [chartName, chartConfig] of Object.entries(data.charts)) {
      const canvasId = `chart-${chartName}`;
      const canvas = document.getElementById(canvasId);
      
      if (canvas) {
        const ctx = canvas.getContext('2d');
        chartRefs.current[chartName] = new Chart(ctx, chartConfig);
      }
    }
  };

  const getChartIcon = (chartType) => {
    switch (chartType) {
      case 'line': return <TrendingUp className="w-4 h-4" />;
      case 'bar': return <BarChart3 className="w-4 h-4" />;
      case 'doughnut': return <PieChart className="w-4 h-4" />;
      case 'radar': return <Activity className="w-4 h-4" />;
      default: return <BarChart3 className="w-4 h-4" />;
    }
  };

  const renderChartCard = (chartName, chartConfig) => {
    const canvasId = `chart-${chartName}`;
    
    return (
      <Card key={chartName} className="w-full">
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            {getChartIcon(chartConfig.type)}
            {chartConfig.options?.plugins?.title?.text || chartName}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64 w-full">
            <canvas id={canvasId}></canvas>
          </div>
        </CardContent>
      </Card>
    );
  };

  const renderTabContent = (tabData, tabName) => {
    if (!tabData || !tabData.charts) return null;

    const charts = Object.entries(tabData.charts);
    
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {charts.map(([chartName, chartConfig]) => 
          renderChartCard(chartName, chartConfig)
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <Card className="w-full">
        <CardContent className="flex items-center justify-center h-64">
          <div className="flex items-center space-x-2">
            <RefreshCw className="w-4 h-4 animate-spin" />
            <span>Загрузка графиков...</span>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!data || !data.charts) {
    return (
      <Card className="w-full">
        <CardContent className="flex items-center justify-center h-64">
          <div className="text-center">
            <BarChart3 className="w-12 h-12 mx-auto text-gray-400 mb-4" />
            <p className="text-gray-500">Нет данных для отображения</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-2xl font-bold">{title}</h2>
        <div className="flex space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            disabled={loading}
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
            Обновить
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={onExport}
          >
            <Download className="w-4 h-4 mr-2" />
            Экспорт
          </Button>
        </div>
      </div>

      {data.summary && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold">{data.summary.total_charts}</div>
              <p className="text-sm text-gray-500">Всего графиков</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold">{data.summary.chart_types?.length || 0}</div>
              <p className="text-sm text-gray-500">Типов графиков</p>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4">
              <div className="text-2xl font-bold">
                {data.period ? 
                  `${new Date(data.period.start_date).toLocaleDateString()} - ${new Date(data.period.end_date).toLocaleDateString()}` 
                  : 'N/A'
                }
              </div>
              <p className="text-sm text-gray-500">Период анализа</p>
            </CardContent>
          </Card>
        </div>
      )}

      {Object.keys(data.charts).length > 1 ? (
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="overview">Обзор</TabsTrigger>
            <TabsTrigger value="kpi">KPI</TabsTrigger>
            <TabsTrigger value="doctors">Врачи</TabsTrigger>
            <TabsTrigger value="revenue">Доходы</TabsTrigger>
          </TabsList>
          
          <TabsContent value="overview">
            {renderTabContent(data.charts.overview || data, 'overview')}
          </TabsContent>
          
          <TabsContent value="kpi">
            {renderTabContent(data.charts.kpi, 'kpi')}
          </TabsContent>
          
          <TabsContent value="doctors">
            {renderTabContent(data.charts.doctors, 'doctors')}
          </TabsContent>
          
          <TabsContent value="revenue">
            {renderTabContent(data.charts.revenue, 'revenue')}
          </TabsContent>
        </Tabs>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {Object.entries(data.charts).map(([chartName, chartConfig]) => 
            renderChartCard(chartName, chartConfig)
          )}
        </div>
      )}
    </div>
  );
};

export default AnalyticsCharts;
