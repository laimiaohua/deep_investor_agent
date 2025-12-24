import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { useNodeContext } from '@/contexts/node-context';
import { formatTimeFromTimestamp } from '@/utils/date-utils';
import { formatContent } from '@/utils/text-utils';
import { translateProgressMessage, translateNodeName } from '@/utils/node-translations';
import { AlignJustify, Copy, Loader2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';

interface AgentOutputDialogProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  name: string;
  nodeId: string;
  flowId: string | null;
}

export function AgentOutputDialog({ 
  isOpen, 
  onOpenChange, 
  name, 
  nodeId,
  flowId
}: AgentOutputDialogProps) {
  const { t } = useTranslation();
  const { getAgentNodeDataForFlow } = useNodeContext();
  
  // Use the passed flowId instead of getting it from flow context
  const agentNodeData = getAgentNodeDataForFlow(flowId);
  const nodeData = agentNodeData[nodeId] || { 
    status: 'IDLE', 
    ticker: null, 
    message: '', 
    messages: [],
    lastUpdated: 0
  };

  const messages = nodeData.messages || [];
  const nodeStatus = nodeData.status;
  
  const [copySuccess, setCopySuccess] = useState(false);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const initialFocusRef = useRef<HTMLDivElement>(null);

  // Collect all analysis from all messages into a single analysis dictionary
  const allAnalysis = messages
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()) // Sort by timestamp
    .reduce<Record<string, string>>((acc, msg) => {
      // Add analysis from this message to our accumulated analysis
      if (msg.analysis && Object.keys(msg.analysis).length > 0) {
        // Filter out null values before adding to our accumulated decisions
        const validDecisions = Object.entries(msg.analysis)
          .filter(([_, value]) => value !== null && value !== undefined)
          .reduce((obj, [key, value]) => {
            obj[key] = value;
            return obj;
          }, {} as Record<string, string>);
        
        if (Object.keys(validDecisions).length > 0) {
          // Combine with accumulated decisions, newer messages overwrite older ones for the same ticker
          return { ...acc, ...validDecisions };
        }
      }
      return acc;
    }, {});

  // Get all unique tickers that have decisions
  const tickersWithDecisions = Object.keys(allAnalysis);

  // Reset selected ticker when node changes
  useEffect(() => {
    setSelectedTicker(null);
  }, [nodeId]);

  // If no ticker is selected but we have decisions, select the first one
  useEffect(() => {
    if (tickersWithDecisions.length > 0 && (!selectedTicker || !tickersWithDecisions.includes(selectedTicker))) {
      setSelectedTicker(tickersWithDecisions[0]);
    }
  }, [tickersWithDecisions, selectedTicker]);

  // Get the selected decision text
  const selectedDecision = selectedTicker && allAnalysis[selectedTicker] ? allAnalysis[selectedTicker] : null;

  const copyToClipboard = () => {
    if (selectedDecision) {
      navigator.clipboard.writeText(selectedDecision)
        .then(() => {
          setCopySuccess(true);
          setTimeout(() => setCopySuccess(false), 2000);
        })
        .catch(err => {
          console.error('Failed to copy text: ', err);
        });
    }
  };

  return (
    <Dialog 
      open={isOpen} 
      onOpenChange={onOpenChange}
      defaultOpen={false}
      modal={true}
    >
      <DialogTrigger asChild>
        <div className="border-t border-border p-3 flex justify-end items-center cursor-pointer hover:bg-accent/50" onClick={() => onOpenChange(true)}>
          <div className="flex items-center gap-1">
            <div className="text-subtitle text-muted-foreground">{t('bottomPanel.output')}</div>
            <AlignJustify className="h-3.5 w-3.5 text-muted-foreground" />
          </div>
        </div>
      </DialogTrigger>
      <DialogContent 
        className="sm:max-w-[900px]" 
        autoFocus={false} 
        onOpenAutoFocus={(e) => e.preventDefault()}
      >
        <DialogHeader>
          <DialogTitle>{translateNodeName(name)}</DialogTitle>
        </DialogHeader>
        
        <div className="grid grid-cols-2 gap-6 pt-4" ref={initialFocusRef} tabIndex={-1}>
          {/* Activity Log Section */}
          <div>
            <h3 className="font-medium mb-3 text-primary">{t('agentDialog.log')}</h3>
            <div className="h-[400px] overflow-y-auto border border-border rounded-lg p-3">
              {messages.length > 0 ? (
                <div className="p-3 space-y-3">
                  {messages
                    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()) // Sort newest first for log
                    .map((msg, idx) => (
                    <div key={idx} className="border-l-2 border-primary pl-3 text-sm">
                      <div className="text-foreground">
                        {msg.ticker && <span>[{msg.ticker}] </span>}
                        {translateProgressMessage(msg.message)}
                      </div>
                      <div className="text-muted-foreground">
                        {formatTimeFromTimestamp(msg.timestamp)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  {t('agentDialog.noActivityAvailable')}
                </div>
              )}
            </div>
          </div>
          
          {/* Analysis Section */}
          <div>
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-medium text-primary">{t('nodes.output.analysis')}</h3>
              <div className="flex items-center gap-2">
                {/* Ticker selector */}
                {tickersWithDecisions.length > 0 && (
                  <div className="flex items-center gap-1">
                    <span className="text-xs text-muted-foreground font-medium">{t('nodes.output.ticker')}:</span>
                    <select 
                      className="text-xs p-1 rounded bg-background border border-border cursor-pointer"
                      value={selectedTicker || ''}
                      onChange={(e) => setSelectedTicker(e.target.value)}
                      autoFocus={false}
                    >
                      {tickersWithDecisions.map((ticker) => (
                        <option key={ticker} value={ticker}>
                          {ticker}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </div>
            </div>
            <div className="h-[400px] overflow-y-auto border border-border rounded-lg p-3">
              {/* Display streaming content if available */}
              {(nodeData as any).streamingContent && (
                <div className="mb-3 p-3 bg-muted/20 rounded border border-primary/30">
                  <h4 className="text-xs font-medium text-primary mb-2 flex items-center gap-2">
                    <span className="inline-block w-2 h-2 bg-primary rounded-full animate-pulse"></span>
                    实时生成中...
                  </h4>
                  <div className="text-sm whitespace-pre-wrap max-h-[250px] overflow-y-auto text-foreground/90">
                    {(nodeData as any).streamingContent}
                  </div>
                </div>
              )}
              
              {tickersWithDecisions.length > 0 ? (
                <div className="p-3 rounded-lg text-sm leading-relaxed">
                  {selectedTicker && (
                    <div className="mb-3 flex justify-between items-center">
                      <div className=" text-muted-foreground font-medium">{t('agentDialog.summaryFor', { ticker: selectedTicker })}</div>
                      {selectedDecision && (
                        <button 
                          onClick={copyToClipboard}
                          className="flex items-center gap-1.5 text-xs p-1.5 rounded hover:bg-accent transition-colors text-muted-foreground"
                          title={t('nodes.output.copyToClipboard')}
                        >
                          <Copy className="h-3.5 w-3.5 " />
                          <span className="font-medium">{copySuccess ? t('nodes.output.copied') : t('nodes.output.copy')}</span>
                        </button>
                      )}
                    </div>
                  )}
                  {selectedDecision ? (
                    (() => {
                      const { isJson, formattedContent } = formatContent(selectedDecision);
                      
                      if (isJson) {
                        // Use react-syntax-highlighter for better JSON rendering
                        return (
                          <div className="overflow-auto rounded-md text-xs">
                            <SyntaxHighlighter
                              language="json"
                              style={vscDarkPlus}
                              customStyle={{
                                margin: 0,
                                padding: '0.75rem',
                                fontSize: '0.875rem',
                                lineHeight: 1.5,
                                whiteSpace: 'pre-wrap',
                                wordWrap: 'break-word',
                                overflowWrap: 'break-word',
                              }}
                              showLineNumbers={false}
                              wrapLines={true}
                              wrapLongLines={true}
                            >
                              {formattedContent as string}
                            </SyntaxHighlighter>
                          </div>
                        );
                      } else {
                        // Display as regular text paragraphs
                        // If formattedContent is an array, map it; otherwise display as single text
                        const paragraphs = Array.isArray(formattedContent) 
                          ? formattedContent 
                          : [formattedContent as string];
                        
                        return (
                          <div className="space-y-3">
                            {paragraphs.map((paragraph, idx) => (
                              <p key={idx} className="text-sm leading-relaxed whitespace-pre-wrap break-words">
                                {paragraph}
                              </p>
                            ))}
                          </div>
                        );
                      }
                    })()
                  ) : nodeStatus === 'IN_PROGRESS' ? (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      <Loader2 className="h-5 w-5 animate-spin mr-2" />
                      {t('nodes.output.analysisInProgress')}
                    </div>
                  ) : (
                    <div className="flex items-center justify-center h-full text-muted-foreground">
                      {t('nodes.output.noAnalysisAvailable', { ticker: selectedTicker })}
                    </div>
                  )}
                </div>
              ) : nodeStatus === 'IN_PROGRESS' ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  <Loader2 className="h-5 w-5 animate-spin mr-2" />
                  {t('nodes.output.analysisInProgress')}
                </div>
              ) : nodeStatus === 'COMPLETE' ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  {t('nodes.output.analysisCompleted')}
                </div>
              ) : nodeStatus === 'ERROR' ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  {t('nodes.output.analysisFailed')}
                </div>
              ) : (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  {t('agentDialog.noAnalysisAvailable')}
                </div>
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
} 