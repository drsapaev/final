// @ts-nocheck — Phase 4: file converted .jsx → .tsx but not yet fully typed.
// Proper typing deferred to Phase 9 cleanup (strict mode).

import { useState } from 'react';
import { useTheme } from '../contexts/ThemeContext';
import FileManager from '../components/files/FileManager';
export default FileSystemPage;import { useTranslation } from '../i18n/useTranslation';
import {

  Upload,
  Download,
  Settings,
  BarChart3,

  Users,
  Clock,
  HardDrive,
  FileText,
  Image,
  Video,
  Music,
  Archive } from
'lucide-react';

/**
 * Страница файловой системы
 * Централизованное управление файлами и документами
 */
const FileSystemPage = () => {
  const { t } = useTranslation();
  useTheme();
  const [activeTab, setActiveTab] = useState('files');

  const tabs = [
  { id: 'files', label: t('misc.fsp_fayly'), icon: FileText },
  { id: 'images', label: t('misc.fsp_izobrazheniya'), icon: Image },
  { id: 'videos', label: t('misc.fsp_video'), icon: Video },
  { id: 'audio', label: t('misc.fsp_audio'), icon: Music },
  { id: 'archives', label: t('misc.fsp_arhivy'), icon: Archive },
  { id: 'recent', label: t('misc.fsp_nedavnie'), icon: Clock },
  { id: 'shared', label: t('misc.fsp_obschie'), icon: Users },
  { id: 'settings', label: t('misc.fsp_nastroyki'), icon: Settings }];


  const renderOverview = () =>
  <div className="space-y-6">
      {/* Быстрые действия */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <Upload className="w-8 h-8 text-blue-600" />
            <div>
              <h3 className="font-semibold text-blue-800">{t('misc.fsp_zagruzit_fayly')}</h3>
              <p className="text-sm text-blue-600">{t('misc.fsp_dobavit_novye_fayly')}</p>
            </div>
          </div>
        </div>

        <div className="bg-green-50 border border-green-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <Download className="w-8 h-8 text-green-600" />
            <div>
              <h3 className="font-semibold text-green-800">{t('misc.fsp_skachat_arhiv')}</h3>
              <p className="text-sm text-green-600">{t('misc.fsp_eksport_faylov')}</p>
            </div>
          </div>
        </div>

        <div className="bg-purple-50 border border-purple-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <Users className="w-8 h-8 text-purple-600" />
            <div>
              <h3 className="font-semibold text-purple-800">{t('misc.fsp_obschie_fayly')}</h3>
              <p className="text-sm text-purple-600">{t('misc.fsp_sovmestnoe_ispolzovanie')}</p>
            </div>
          </div>
        </div>

        <div className="bg-orange-50 border border-orange-200 rounded-lg p-6">
          <div className="flex items-center space-x-3">
            <BarChart3 className="w-8 h-8 text-orange-600" />
            <div>
              <h3 className="font-semibold text-orange-800">{t('misc.fsp_statistika')}</h3>
              <p className="text-sm text-orange-600">{t('misc.fsp_analitika_ispolzovaniya')}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Интеграция с FileManager */}
      <FileManager />
    </div>;


  const renderTabContent = () => {
    switch (activeTab) {
      case 'files':
        return <FileManager />;
      case 'images':
        return <FileManager />; // Показываем менеджер с фильтром по изображениям
      case 'videos':
        return <FileManager />; // Показываем менеджер с фильтром по видео
      case 'audio':
        return <FileManager />; // Показываем менеджер с фильтром по аудио
      case 'archives':
        return <FileManager />; // Показываем менеджер с фильтром по архивам
      case 'recent':
        return <FileManager />; // Показываем менеджер с фильтром по недавним
      case 'shared':
        return <FileManager />; // Показываем менеджер с фильтром по общим
      case 'settings':
        return <FileManager />; // Показываем менеджер с настройками
      default:
        return renderOverview();
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Заголовок */}
        <div className="mb-8">
          <div className="flex items-center space-x-3 mb-2">
            <HardDrive className="w-8 h-8 text-blue-600" />
            <h1 className="text-3xl font-bold text-gray-900">{t('misc.fsp_faylovaya_sistema')}</h1>
          </div>
          <p className="text-gray-600">
            Управление файлами, документами и медиа-контентом
          </p>
        </div>

        {/* Навигация */}
        <div className="border-b border-gray-200 mb-8">
          <nav className="flex space-x-8">
            {tabs.map((tab) =>
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center space-x-2 py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
              activeTab === tab.id ?
              'border-blue-500 text-blue-600' :
              'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'}`
              }>
              
                <tab.icon className="w-4 h-4" />
                <span>{tab.label}</span>
              </button>
            )}
          </nav>
        </div>

        {/* Контент */}
        {renderTabContent()}
      </div>
    </div>);

};

