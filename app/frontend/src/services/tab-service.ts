import { Settings } from '@/components/settings/settings';
import { FlowTabContent } from '@/components/tabs/flow-tab-content';
import { Guide } from '@/components/guide/guide';
import { Flow } from '@/types/flow';
import { ReactNode, createElement } from 'react';

export interface TabData {
  type: 'flow' | 'settings' | 'guide';
  title: string;
  flow?: Flow;
  metadata?: Record<string, any>;
}

export class TabService {
  static createTabContent(tabData: TabData): ReactNode {
    switch (tabData.type) {
      case 'flow':
        if (!tabData.flow) {
          throw new Error('Flow tab requires flow data');
        }
        return createElement(FlowTabContent, { flow: tabData.flow });
      
      case 'settings':
        return createElement(Settings);
      
      case 'guide':
        return createElement(Guide);
      
      default:
        throw new Error(`Unsupported tab type: ${tabData.type}`);
    }
  }

  static createFlowTab(flow: Flow): TabData & { content: ReactNode } {
    return {
      type: 'flow',
      title: flow.name,
      flow: flow,
      content: TabService.createTabContent({ type: 'flow', title: flow.name, flow }),
    };
  }

  static createSettingsTab(title?: string): TabData & { content: ReactNode } {
    const tabTitle = title || 'Settings';
    return {
      type: 'settings',
      title: tabTitle,
      content: TabService.createTabContent({ type: 'settings', title: tabTitle }),
    };
  }

  static createGuideTab(title?: string): TabData & { content: ReactNode } {
    const tabTitle = title || 'Guide';
    return {
      type: 'guide',
      title: tabTitle,
      content: TabService.createTabContent({ type: 'guide', title: tabTitle }),
    };
  }

  // Restore tab content for persisted tabs (used when loading from localStorage)
  static restoreTabContent(tabData: TabData): ReactNode {
    return TabService.createTabContent(tabData);
  }

  // Helper method to restore a complete tab from saved data
  static restoreTab(savedTab: TabData): TabData & { content: ReactNode } {
    switch (savedTab.type) {
      case 'flow':
        if (!savedTab.flow) {
          throw new Error('Flow tab requires flow data for restoration');
        }
        return TabService.createFlowTab(savedTab.flow);
      
      case 'settings':
        return TabService.createSettingsTab();
      
      case 'guide':
        return TabService.createGuideTab();
      
      default:
        throw new Error(`Cannot restore unsupported tab type: ${savedTab.type}`);
    }
  }
} 