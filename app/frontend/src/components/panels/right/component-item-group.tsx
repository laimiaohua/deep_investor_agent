import ComponentItem from '@/components/panels/right/component-item';
import { AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { useFlowContext } from '@/contexts/flow-context';
import { ComponentGroup } from '@/data/sidebar-components';
import { useTranslation } from 'react-i18next';
import { translateNodeName } from '@/utils/node-translations';

interface ComponentItemGroupProps {
  group: ComponentGroup;
  activeItem: string | null;
}

export function ComponentItemGroup({ 
  group, 
  activeItem
}: ComponentItemGroupProps) {
  const { name, icon: Icon, iconColor, items } = group;
  const { addComponentToFlow } = useFlowContext();
  const { t } = useTranslation();

  // Map component group names to translation keys
  const getGroupName = (groupName: string): string => {
    const nameMap: Record<string, string> = {
      'Start Nodes': t('sidebar.right.startNodes'),
      'Analysts': t('sidebar.right.analysts'),
      'Swarms': t('sidebar.right.swarms'),
      'End Nodes': t('sidebar.right.endNodes'),
    };
    return nameMap[groupName] || groupName;
  };

  const handleItemClick = async (componentName: string) => {
    try {
      await addComponentToFlow(componentName);
    } catch (error) {
      console.error('Failed to add component to flow:', error);
    }
  };
  
  return (
    <AccordionItem key={name} value={name} className="border-none">
      <AccordionTrigger className="px-4 py-2 text-sm hover-bg hover:no-underline">
        <div className="flex items-center gap-2">
          <Icon size={16} className={iconColor} />
          <span className="capitalize">{getGroupName(name)}</span>
        </div>
      </AccordionTrigger>
      <AccordionContent className="px-4">
        <div className="space-y-1">
          {items.map((item) => (
            <ComponentItem 
              key={item.name}
              icon={item.icon} 
              label={translateNodeName(item.name)} 
              isActive={activeItem === item.name}
              onClick={() => handleItemClick(item.name)}
            />
          ))}
        </div>
      </AccordionContent>
    </AccordionItem>
  );
} 