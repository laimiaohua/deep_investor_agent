import { type NodeProps } from '@xyflow/react';
import { Bot } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { translateNodeStatus, translateProgressMessage } from '@/utils/node-translations';

import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { CardContent } from '@/components/ui/card';
import { ModelSelector } from '@/components/ui/llm-selector';
import { useFlowContext } from '@/contexts/flow-context';
import { useNodeContext } from '@/contexts/node-context';
import { getModels, LanguageModel } from '@/data/models';
import { useNodeState } from '@/hooks/use-node-state';
import { cn } from '@/lib/utils';
import { type AgentNode } from '../types';
import { getStatusColor } from '../utils';
import { AgentOutputDialog } from './agent-output-dialog';
import { NodeShell } from './node-shell';

export function AgentNode({
  data,
  selected,
  id,
  isConnectable,
}: NodeProps<AgentNode>) {
  const { t } = useTranslation();
  const { currentFlowId } = useFlowContext();
  const { getAgentNodeDataForFlow, setAgentModel, getAgentModel } = useNodeContext();
  
  // Get agent node data for the current flow
  const agentNodeData = getAgentNodeDataForFlow(currentFlowId?.toString() || null);
  const nodeData = agentNodeData[id] || { 
    status: 'IDLE', 
    ticker: null, 
    message: '', 
    messages: [],
    lastUpdated: 0
  };
  const status = nodeData.status;
  const isInProgress = status === 'IN_PROGRESS';
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  
  // Use persistent state hooks
  const [availableModels, setAvailableModels] = useNodeState<LanguageModel[]>(id, 'availableModels', []);
  const [selectedModel, setSelectedModel] = useNodeState<LanguageModel | null>(id, 'selectedModel', null);

  // Load models on mount
  useEffect(() => {
    const loadModels = async () => {
      try {
        const models = await getModels();
        setAvailableModels(models);
      } catch (error) {
        console.error('Failed to load models:', error);
        // Keep empty array as fallback
      }
    };
    
    loadModels();
  }, [setAvailableModels]);

  // Update the node context when the model changes
  useEffect(() => {
    const flowId = currentFlowId?.toString() || null;
    const currentContextModel = getAgentModel(flowId, id);
    if (selectedModel !== currentContextModel) {
      setAgentModel(flowId, id, selectedModel);
    }
  }, [selectedModel, id, currentFlowId, setAgentModel, getAgentModel]);

  const handleModelChange = (model: LanguageModel | null) => {
    setSelectedModel(model);
  };

  const handleUseGlobalModel = () => {
    setSelectedModel(null);
  };

  return (
    <NodeShell
      id={id}
      selected={selected}
      isConnectable={isConnectable}
      icon={<Bot className="h-5 w-5" />}
      iconColor={getStatusColor(status)}
      name={data.name || "Agent"}
      description={data.description}
      status={status}
    >
      <CardContent className="p-0">
        <div className="border-t border-border p-3">
          <div className="flex flex-col gap-2">
            <div className="text-subtitle text-primary flex items-center gap-1">
              {t('nodes.status')}
            </div>

            <div className={cn(
              "text-foreground text-xs rounded p-2 border border-status",
              isInProgress ? "gradient-animation" : getStatusColor(status)
            )}>
              <span>{translateNodeStatus(status)}</span>
            </div>
            
            {nodeData.message && (
              <div className="text-foreground text-subtitle">
                {nodeData.message !== "Done" && translateProgressMessage(nodeData.message)}
                {nodeData.ticker && <span className="ml-1">({nodeData.ticker})</span>}
              </div>
            )}
            
            {/* Display streaming content if available */}
            {(nodeData as any).streamingContent && (
              <div className="text-foreground text-xs mt-2 p-2 bg-muted/30 rounded border border-border max-h-32 overflow-y-auto">
                <div className="whitespace-pre-wrap">
                  {(nodeData as any).streamingContent}
                </div>
              </div>
            )}
            <Accordion type="single" collapsible>
              <AccordionItem value="advanced" className="border-none">
                <AccordionTrigger className="!text-subtitle text-primary">
                  {t('nodes.advanced')}
                </AccordionTrigger>
                <AccordionContent className="pt-2">
                  <div className="flex flex-col gap-2">
                    <div className="text-subtitle text-primary flex items-center gap-1">
                      {t('nodes.model')}
                    </div>
                    <ModelSelector
                      models={availableModels}
                      value={selectedModel?.model_name || ""}
                      onChange={handleModelChange}
                      placeholder={t('nodes.auto')}
                    />
                    {selectedModel && (
                      <button
                        onClick={handleUseGlobalModel}
                        className="text-subtitle text-primary hover:text-foreground transition-colors text-left"
                      >
                        {t('nodes.resetToAuto')}
                      </button>
                    )}
                  </div>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </div>
        </div>
        <AgentOutputDialog
          isOpen={isDialogOpen}
          onOpenChange={setIsDialogOpen}
          name={data.name || "Agent"}
          nodeId={id}
          flowId={currentFlowId?.toString() || null}
        />
      </CardContent>
    </NodeShell>
  );
}
