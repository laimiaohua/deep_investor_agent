import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { PanelBottom, PanelLeft, PanelRight, Settings, HelpCircle } from 'lucide-react';
import { LanguageSwitcher } from '@/components/language-switcher';
import { useTranslation } from 'react-i18next';
import { useTabsContext } from '@/contexts/tabs-context';
import { TabService } from '@/services/tab-service';

interface TopBarProps {
  isLeftCollapsed: boolean;
  isRightCollapsed: boolean;
  isBottomCollapsed: boolean;
  onToggleLeft: () => void;
  onToggleRight: () => void;
  onToggleBottom: () => void;
  onSettingsClick: () => void;
}

export function TopBar({
  isLeftCollapsed,
  isRightCollapsed,
  isBottomCollapsed,
  onToggleLeft,
  onToggleRight,
  onToggleBottom,
  onSettingsClick,
}: TopBarProps) {
  const { t } = useTranslation();
  const { openTab, isTabOpen, getTabByIdentifier, setActiveTab } = useTabsContext();

  const handleGuideClick = () => {
    if (isTabOpen('guide', 'guide')) {
      // Tab already open, just focus it
      const existingTab = getTabByIdentifier('guide', 'guide');
      if (existingTab) {
        setActiveTab(existingTab.id);
      }
      return;
    }
    const tabData = TabService.createGuideTab(t('guide.title'));
    openTab(tabData);
  };

  return (
    <div className="absolute top-0 right-0 z-40 flex items-center gap-0 py-1 px-2 bg-panel/80">
      {/* Left Sidebar Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleLeft}
        className={cn(
          "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
          !isLeftCollapsed && "text-foreground"
        )}
        aria-label={t('topBar.toggleLeftSidebar')}
        title={t('topBar.toggleLeftSidebar')}
      >
        <PanelLeft size={16} />
      </Button>

      {/* Bottom Panel Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleBottom}
        className={cn(
          "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
          !isBottomCollapsed && "text-foreground"
        )}
        aria-label={t('topBar.toggleBottomPanel')}
        title={t('topBar.toggleBottomPanel')}
      >
        <PanelBottom size={16} />
      </Button>

      {/* Right Sidebar Toggle */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onToggleRight}
        className={cn(
          "h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors",
          !isRightCollapsed && "text-foreground"
        )}
        aria-label={t('topBar.toggleRightSidebar')}
        title={t('topBar.toggleRightSidebar')}
      >
        <PanelRight size={16} />
      </Button>

      {/* Divider */}
      <div className="w-px h-5 bg-ramp-grey-700 mx-1" />

      {/* Language Switcher */}
      <LanguageSwitcher />

      {/* Guide */}
      <Button
        variant="ghost"
        size="sm"
        onClick={handleGuideClick}
        className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
        aria-label={t('topBar.openGuide')}
        title={t('topBar.openGuide')}
      >
        <HelpCircle size={16} />
      </Button>

      {/* Settings */}
      <Button
        variant="ghost"
        size="sm"
        onClick={onSettingsClick}
        className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground hover:bg-ramp-grey-700 transition-colors"
        aria-label={t('topBar.openSettings')}
        title={t('topBar.openSettings')}
      >
        <Settings size={16} />
      </Button>
    </div>
  );
} 