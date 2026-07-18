
import { api } from '../../api/client';
import { useState, useEffect, useCallback } from 'react';
import {
  Image,
  Video,
  FileText,
  Plus,
  Trash2,
  Edit,
  Eye,
  Upload,
  Play,


  Monitor } from
'lucide-react';
import { Card, Button as ButtonRaw, Badge as BadgeRaw,
  Input as InputRaw } from '../ui/macos';
import logger from '../../utils/logger';
import tokenManager from '../../utils/tokenManager';
import PropTypes from 'prop-types';
import { useTranslation } from '../../i18n/useTranslation';
import React from "react";
const Badge = BadgeRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Input = InputRaw as unknown as React.ComponentType<Record<string, unknown>>;
const Button = ButtonRaw as unknown as React.ComponentType<Record<string, unknown>>;
/**
 * Управление контентом для табло
 * Основа: passport.md стр. 2571-3324
 */
const DisplayContentManager = ({
  boardId,
  className = ''
}) => {
  const { t: rawT } = useTranslation();
  const t = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  const t18 = rawT as unknown as (key: string, options?: Record<string, unknown>) => string;
  void t;
  const [activeTab, setActiveTab] = useState('banners');
  const [content, setContent] = useState({
    banners: [],
    announcements: [],
    videos: [],
    themes: []
  });
  const [, setLoading] = useState(false);
  const [uploadDialog, setUploadDialog] = useState({ open: false, type: '' });

  const contentTabs = [
  { id: 'banners', label: t('misc.dcm_tab_banners'), icon: Image, color: 'text-blue-600' },
  { id: 'announcements', label: t('misc.dcm_tab_announcements'), icon: FileText, color: 'text-green-600' },
  { id: 'videos', label: t('misc.dcm_tab_videos'), icon: Video, color: 'text-purple-600' },
  { id: 'themes', label: t('misc.dcm_tab_themes'), icon: Monitor, color: 'text-gray-600' }];

  const loadContent = useCallback(async () => {
    try {
      setLoading(true);

      // Загружаем контент для табло
      const response = await fetch(`/admin/display-boards/${boardId}/content`, {
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        const data = await response.json();
        setContent(data);
      }
    } catch (error) {
      logger.error('Ошибка загрузки контента:', error);
    } finally {
      setLoading(false);
    }
  }, [boardId]);

  useEffect(() => {
    loadContent();
  }, [loadContent]);























  const handleDeleteContent = async (contentId: string | number, contentType?: string) => {
    try {
      const response = await fetch(`/admin/display-boards/content/${contentId}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${tokenManager.getAccessToken()}` }
      });

      if (response.ok) {
        await loadContent();
      }
    } catch (error) {
      logger.error('Ошибка удаления контента:', error);
    }
  };

  const renderBannersTab = () =>
  <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">{t('misc.dcm_banners_title')}</h3>
        <Button onClick={() => setUploadDialog({ open: true, type: 'banner' })}>
          <Plus size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="mr-2" />
          {t('misc.dcm_add_banner')}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {content.banners.map((banner) =>
      <Card key={banner.id} className="overflow-hidden">
            <div className="aspect-video bg-gray-100 flex items-center justify-center">
              {banner.file_url ?
          <img
            src={banner.file_url}
            alt={banner.title}
            className="w-full h-full object-cover" /> :


          <Image size={48} className="text-gray-400" />
          }
            </div>
            <div className="p-3">
              <div className="font-medium text-sm mb-1">{banner.title}</div>
              <div className="text-xs text-gray-500 mb-2">{banner.description}</div>
              <div className="flex justify-between items-center">
                <Badge variant={banner.active ? 'success' : 'secondary'} size="small">
                  {banner.active ? t('misc.dcm_active') : t('misc.dcm_inactive')}
                </Badge>
                <div className="flex space-x-1">
                  <Button
                    size="small"
                    variant="outline"
                    type="button"
                    title={t18('misc.dcm_view_banner', { title: banner.title })}
                    aria-label={t18('misc.dcm_view_banner', { title: banner.title })}>
                    <Eye aria-hidden="true" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                  </Button>
                  <Button
                    size="small"
                    variant="outline"
                    type="button"
                    title={t18('misc.dcm_edit_banner', { title: banner.title })}
                    aria-label={t18('misc.dcm_edit_banner', { title: banner.title })}>
                    <Edit aria-hidden="true" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                  </Button>
                  <Button
                size="small"
                variant="outline"
                type="button"
                title={t18('misc.dcm_delete_banner', { title: banner.title })}
                aria-label={t18('misc.dcm_delete_banner', { title: banner.title })}
                onClick={() => handleDeleteContent(banner.id, 'banner')}>

                    <Trash2 aria-hidden="true" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                  </Button>
                </div>
              </div>
            </div>
          </Card>
      )}
      </div>
    </div>;


  const renderAnnouncementsTab = () =>
  <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">{t('misc.dcm_announcements_title')}</h3>
        <Button onClick={() => setUploadDialog({ open: true, type: 'announcement' })}>
          <Plus size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="mr-2" />
          {t('misc.dcm_add_announcement')}
        </Button>
      </div>

      <div className="space-y-3">
        {content.announcements.map((announcement) =>
      <Card key={announcement.id} className="p-4">
            <div className="flex justify-between items-start">
              <div className="flex-1">
                <div className="font-medium mb-2">{announcement.title}</div>
                <div className="text-gray-600 text-sm mb-3">{announcement.text}</div>
                <div className="flex items-center space-x-3">
                  <Badge
                variant={
                announcement.priority === 'high' ? 'error' :
                announcement.priority === 'medium' ? 'warning' : 'info'
                }
                size="small">
                
                    {announcement.priority === 'high' ? t('misc.dcm_priority_high') :
                announcement.priority === 'medium' ? t('misc.dcm_priority_medium') : t('misc.dcm_priority_normal')}
                  </Badge>
                  <span className="text-xs text-gray-500">
                    {t('misc.dcm_created')} {new Date(announcement.created_at).toLocaleDateString('ru-RU')}
                  </span>
                </div>
              </div>
              <div className="flex space-x-2 ml-4">
                <Button
                  size="small"
                  variant="outline"
                  type="button"
                  title={t18('misc.dcm_edit_announcement', { title: announcement.title })}
                  aria-label={t18('misc.dcm_edit_announcement', { title: announcement.title })}>
                  <Edit aria-hidden="true" size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                </Button>
                <Button
              size="small"
              variant="outline"
              type="button"
              title={t18('misc.dcm_delete_announcement', { title: announcement.title })}
              aria-label={t18('misc.dcm_delete_announcement', { title: announcement.title })}
              onClick={() => handleDeleteContent(announcement.id, 'announcement')}>

                  <Trash2 aria-hidden="true" size={14 as unknown as "small" | "default" | "large" | "xlarge"} />
                </Button>
              </div>
            </div>
          </Card>
      )}
      </div>
    </div>;


  const renderVideosTab = () =>
  <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-medium">{t('misc.dcm_videos_title')}</h3>
        <Button onClick={() => setUploadDialog({ open: true, type: 'video' })}>
          <Plus size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="mr-2" />
          {t('misc.dcm_add_video')}
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {content.videos.map((video) =>
      <Card key={video.id} className="overflow-hidden">
            <div className="aspect-video bg-gray-900 flex items-center justify-center relative">
              {video.thumbnail_url ?
          <img
            src={video.thumbnail_url}
            alt={video.title}
            className="w-full h-full object-cover" /> :


          <Video size={48} className="text-gray-400" />
          }
              <div className="absolute inset-0 bg-black bg-opacity-50 flex items-center justify-center">
                <Play size={32 as unknown as "small" | "default" | "large" | "xlarge"} className="text-white" />
              </div>
            </div>
            <div className="p-3">
              <div className="font-medium text-sm mb-1">{video.title}</div>
              <div className="text-xs text-gray-500 mb-2">
                {t('misc.dcm_duration')} {video.duration || t('misc.dcm_not_specified')}
              </div>
              <div className="flex justify-between items-center">
                <Badge variant={video.active ? 'success' : 'secondary'} size="small">
                  {video.active ? t('misc.dcm_showing') : t('misc.dcm_inactive')}
                </Badge>
                <div className="flex space-x-1">
                  <Button
                    size="small"
                    variant="outline"
                    type="button"
                    title={t18('misc.dcm_play_video', { title: video.title })}
                    aria-label={t18('misc.dcm_play_video', { title: video.title })}>
                    <Play aria-hidden="true" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                  </Button>
                  <Button
                    size="small"
                    variant="outline"
                    type="button"
                    title={t18('misc.dcm_edit_video', { title: video.title })}
                    aria-label={t18('misc.dcm_edit_video', { title: video.title })}>
                    <Edit aria-hidden="true" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                  </Button>
                  <Button
                size="small"
                variant="outline"
                type="button"
                title={t18('misc.dcm_delete_video', { title: video.title })}
                aria-label={t18('misc.dcm_delete_video', { title: video.title })}
                onClick={() => handleDeleteContent(video.id, 'video')}>

                    <Trash2 aria-hidden="true" size={12 as unknown as "small" | "default" | "large" | "xlarge"} />
                  </Button>
                </div>
              </div>
            </div>
          </Card>
      )}
      </div>
    </div>;


  const renderThemesTab = () =>
  <div className="space-y-4">
      <h3 className="text-lg font-medium">{t('misc.dcm_themes_title')}</h3>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
      { id: 'light', name: t('misc.dcm_theme_light'), preview: 'var(--mac-bg-secondary)' },
      { id: 'dark', name: t('misc.dcm_theme_dark'), preview: '#1a202c' },
      { id: 'medical', name: t('misc.dcm_theme_medical'), preview: '#f0fff4' }].
      map((theme) =>
      <Card key={theme.id} className="cursor-pointer hover:shadow-lg transition-shadow">
            <div
          className="h-24 rounded-t-lg"
          style={{ background: theme.preview }} />

            <div className="p-3">
              <div className="font-medium">{theme.name}</div>
              <div className="text-sm text-gray-500">{t('misc.dcm_theme_label', { id: theme.id })}</div>
            </div>
          </Card>
      )}
      </div>
    </div>;


  return (
    <div className={`space-y-6 ${className}`}>
      {/* Заголовок */}
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">{t('misc.dcm_title')}</h2>
        <Badge variant="info">
          {t('misc.dcm_board', { id: boardId })}
        </Badge>
      </div>

      {/* Вкладки */}
      <div className="flex space-x-1 border-b border-gray-200">
        {contentTabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const TabIcon = tab.icon;

          return (
            <button
              key={tab.id}
              className={`flex items-center px-4 py-2 text-sm font-medium rounded-t-lg transition-colors ${isActive ?
              'bg-blue-50 text-blue-700 border-b-2 border-blue-500' :
              'text-gray-500 hover:text-gray-700'}`
              }
              onClick={() => setActiveTab(tab.id)}>
              
              <TabIcon size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="mr-2" />
              {tab.label}
            </button>);

        })}
      </div>

      {/* Контент вкладок */}
      <div>
        {activeTab === 'banners' && renderBannersTab()}
        {activeTab === 'announcements' && renderAnnouncementsTab()}
        {activeTab === 'videos' && renderVideosTab()}
        {activeTab === 'themes' && renderThemesTab()}
      </div>

      {/* Диалог загрузки */}
      {uploadDialog.open &&
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <Card className="w-full max-w-md mx-4">
            <div className="p-6">
              <h3 className="text-lg font-medium mb-4">
                {t('misc.dcm_upload')} {uploadDialog.type === 'banner' ? t('misc.dcm_type_banner') :
              uploadDialog.type === 'video' ? t('misc.dcm_type_video') : t('misc.dcm_type_content')}
              </h3>

              <div className="space-y-4">
                <div>
                  <label htmlFor="display-content-title" className="block text-sm font-medium text-gray-700 mb-2">
                    {t('misc.dcm_name_label')}
                  </label>
                  <Input
                  id="display-content-title"
                  type="text"
                  aria-label="Display content title"
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
                  placeholder={t('misc.dcm_name_placeholder')} />
                
                </div>

                <div>
                  <label htmlFor="display-content-file" className="block text-sm font-medium text-gray-700 mb-2">
                    {t('misc.dcm_file_label')}
                  </label>
                  <input
                  id="display-content-file"
                  type="file"
                  aria-label="Display content file"
                  accept={
                  uploadDialog.type === 'banner' ? 'image/*' :
                  uploadDialog.type === 'video' ? 'video/*' : '*/*'
                  }
                  className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500" />
                
                </div>
              </div>

              <div className="flex justify-end space-x-3 mt-6">
                <Button
                variant="outline"
                onClick={() => setUploadDialog({ open: false, type: '' })}>

                  {t('misc.dcm_cancel')}
                </Button>
                <Button onClick={() => {/* Логика загрузки */}}>
                  <Upload size={16 as unknown as "small" | "default" | "large" | "xlarge"} className="mr-2" />
                  {t('misc.dcm_upload_btn')}
                </Button>
              </div>
            </div>
          </Card>
        </div>
      }
    </div>);

};


DisplayContentManager.propTypes = {
  ...(DisplayContentManager.propTypes || {}),
  boardId: PropTypes.any,
  className: PropTypes.any,
};

export default DisplayContentManager;
