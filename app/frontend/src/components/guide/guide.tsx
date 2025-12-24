import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useTranslation } from 'react-i18next';
import { Key, Play, Network, Languages, ExternalLink, ChevronRight } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useTabsContext } from '@/contexts/tabs-context';
import { TabService } from '@/services/tab-service';

export function Guide() {
  const { t } = useTranslation();
  const { openTab } = useTabsContext();

  const handleOpenSettings = () => {
    const tabData = TabService.createSettingsTab(t('settings.title'));
    openTab(tabData);
  };

  const sections = [
    {
      id: 'api-keys',
      icon: Key,
      title: t('guide.apiKeys.title'),
      description: t('guide.apiKeys.description'),
      items: [
        {
          title: t('guide.apiKeys.financialData.title'),
          content: (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">{t('guide.apiKeys.financialData.desc')}</p>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                <li>{t('guide.apiKeys.financialData.financialDatasets')}</li>
                <li>{t('guide.apiKeys.financialData.deepalpha')}</li>
              </ul>
              <Button
                variant="outline"
                size="sm"
                onClick={handleOpenSettings}
                className="mt-2"
              >
                {t('guide.apiKeys.financialData.openSettings')}
                <ChevronRight className="ml-1 h-3 w-3" />
              </Button>
            </div>
          ),
        },
        {
          title: t('guide.apiKeys.languageModels.title'),
          content: (
            <div className="space-y-2">
              <p className="text-sm text-muted-foreground">{t('guide.apiKeys.languageModels.desc')}</p>
              <ul className="list-disc list-inside space-y-1 text-sm text-muted-foreground ml-4">
                <li>{t('guide.apiKeys.languageModels.step1')}</li>
                <li>{t('guide.apiKeys.languageModels.step2')}</li>
                <li>{t('guide.apiKeys.languageModels.step3')}</li>
              </ul>
              <Button
                variant="outline"
                size="sm"
                onClick={handleOpenSettings}
                className="mt-2"
              >
                {t('guide.apiKeys.languageModels.openSettings')}
                <ChevronRight className="ml-1 h-3 w-3" />
              </Button>
            </div>
          ),
        },
      ],
    },
    {
      id: 'default-flow',
      icon: Play,
      title: t('guide.defaultFlow.title'),
      description: t('guide.defaultFlow.description'),
      items: [
        {
          title: t('guide.defaultFlow.step1.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.defaultFlow.step1.desc')}</p>
          ),
        },
        {
          title: t('guide.defaultFlow.step2.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.defaultFlow.step2.desc')}</p>
          ),
        },
        {
          title: t('guide.defaultFlow.step3.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.defaultFlow.step3.desc')}</p>
          ),
        },
      ],
    },
    {
      id: 'custom-flow',
      icon: Network,
      title: t('guide.customFlow.title'),
      description: t('guide.customFlow.description'),
      items: [
        {
          title: t('guide.customFlow.step1.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.customFlow.step1.desc')}</p>
          ),
        },
        {
          title: t('guide.customFlow.step2.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.customFlow.step2.desc')}</p>
          ),
        },
        {
          title: t('guide.customFlow.step3.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.customFlow.step3.desc')}</p>
          ),
        },
        {
          title: t('guide.customFlow.step4.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.customFlow.step4.desc')}</p>
          ),
        },
      ],
    },
    {
      id: 'language',
      icon: Languages,
      title: t('guide.language.title'),
      description: t('guide.language.description'),
      items: [
        {
          title: t('guide.language.step1.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.language.step1.desc')}</p>
          ),
        },
        {
          title: t('guide.language.step2.title'),
          content: (
            <p className="text-sm text-muted-foreground">{t('guide.language.step2.desc')}</p>
          ),
        },
      ],
    },
  ];

  return (
    <div className="h-full overflow-auto bg-panel">
      <div className="max-w-4xl mx-auto p-8 space-y-6">
        {/* Header */}
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-primary">{t('guide.title')}</h1>
          <p className="text-muted-foreground">{t('guide.description')}</p>
        </div>

        {/* Sections */}
        {sections.map((section, sectionIndex) => {
          const Icon = section.icon;
          return (
            <Card key={section.id} className="bg-panel border-gray-700 dark:border-gray-700">
              <CardHeader>
                <CardTitle className="text-xl font-semibold text-primary flex items-center gap-3">
                  <Icon className="h-5 w-5" />
                  {section.title}
                </CardTitle>
                <p className="text-sm text-muted-foreground mt-2">{section.description}</p>
              </CardHeader>
              <CardContent className="space-y-4">
                {section.items.map((item, itemIndex) => (
                  <div key={itemIndex} className="space-y-2">
                    <h3 className="text-base font-medium text-primary flex items-center gap-2">
                      <span className="flex items-center justify-center w-6 h-6 rounded-full bg-blue-500/10 text-blue-500 text-xs font-semibold">
                        {itemIndex + 1}
                      </span>
                      {item.title}
                    </h3>
                    <div className="ml-8">{item.content}</div>
                  </div>
                ))}
              </CardContent>
            </Card>
          );
        })}

        {/* Footer */}
        <Card className="bg-blue-500/5 border-blue-500/20">
          <CardContent className="p-4">
            <div className="flex items-start gap-3">
              <ExternalLink className="h-5 w-5 text-blue-500 mt-0.5 flex-shrink-0" />
              <div className="space-y-1">
                <h4 className="text-sm font-medium text-blue-500">{t('guide.needHelp.title')}</h4>
                <p className="text-xs text-muted-foreground">{t('guide.needHelp.description')}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

