import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { useEffect, useState } from 'react';
import { getActionColor, getDisplayName, getSignalColor, getStatusIcon } from './output-tab-utils';
import { ReasoningContent } from './reasoning-content';
import { useTranslation } from 'react-i18next';
import { translateNodeName, translateProgressMessage } from '@/utils/node-translations';

// Progress Section Component
function ProgressSection({ sortedAgents }: { sortedAgents: [string, any][] }) {
  const { t } = useTranslation();
  
  if (sortedAgents.length === 0) return null;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">{t('nodes.output.progress')}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-1">
          {sortedAgents.map(([agentId, data]) => {
            const { icon: StatusIcon, color } = getStatusIcon(data.status);
            const displayName = getDisplayName(agentId);
            
            return (
              <div key={agentId} className="flex items-center gap-2">
                <StatusIcon className={cn("h-4 w-4 flex-shrink-0", color)} />
                <span className="font-medium">{translateNodeName(displayName)}</span>
                {data.ticker && (
                  <span>[{data.ticker}]</span>
                )}
                <span className={cn("flex-1", color)}>
                  {translateProgressMessage(data.message || data.status)}
                </span>
                {data.timestamp && (
                  <span className="text-muted-foreground text-xs">
                    {new Date(data.timestamp).toLocaleTimeString()}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

// Summary Section Component
function SummarySection({ outputData }: { outputData: any }) {
  const { t } = useTranslation();
  
  if (!outputData) return null;

  return (
    <Card className="bg-transparent mb-4">
      <CardHeader>
        <CardTitle className="text-lg">{t('nodes.output.summary')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('nodes.output.ticker')}</TableHead>
              <TableHead>{t('nodes.output.currentPosition')}</TableHead>
              <TableHead>{t('nodes.output.action')}</TableHead>
              <TableHead>{t('nodes.output.quantity')}</TableHead>
              <TableHead>{t('nodes.output.confidence')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {Object.entries(outputData.decisions).map(([ticker, decision]: [string, any]) => {
              const position = outputData.current_positions?.[ticker];
              const longShares = position?.long || 0;
              const shortShares = position?.short || 0;
              const positionDisplay = longShares > 0 
                ? `${longShares} (Long)`
                : shortShares > 0 
                ? `${shortShares} (Short)`
                : '0';
              // For "hold" action, show current position quantity instead of 0
              const quantityDisplay = decision.action?.toLowerCase() === 'hold' 
                ? (longShares > 0 ? longShares : shortShares > 0 ? shortShares : 0)
                : (decision.quantity || 0);
              return (
                <TableRow key={ticker}>
                  <TableCell className="font-medium">{ticker}</TableCell>
                  <TableCell>{positionDisplay}</TableCell>
                  <TableCell>
                    <span className={cn("font-medium", getActionColor(decision.action || ''))}>
                      {decision.action?.toUpperCase() || 'UNKNOWN'}
                    </span>
                  </TableCell>
                  <TableCell>{quantityDisplay}</TableCell>
                  <TableCell>{decision.confidence?.toFixed(1) || 0}%</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

// Analysis Results Section Component
function AnalysisResultsSection({ outputData }: { outputData: any }) {
  const { t } = useTranslation();
  // Always call hooks at the top of the function
  const [selectedTicker, setSelectedTicker] = useState<string>('');
  
  // Calculate tickers (safe to do even if outputData is null)
  const tickers = outputData?.decisions ? Object.keys(outputData.decisions) : [];
  
  // Set default selected ticker
  useEffect(() => {
    if (tickers.length > 0 && !selectedTicker) {
      setSelectedTicker(tickers[0]);
    }
  }, [tickers, selectedTicker]);

  // Early returns after all hooks are called
  if (!outputData) return null;
  if (tickers.length === 0) return null;

  return (
    <Card className="bg-transparent">
      <CardHeader>
        <CardTitle className="text-lg">{t('nodes.output.analysis')}</CardTitle>
      </CardHeader>
      <CardContent>
        <Tabs value={selectedTicker} onValueChange={setSelectedTicker} className="w-full">
          <TabsList className="flex space-x-1 bg-muted p-1 rounded-lg mb-4">
            {tickers.map((ticker) => (
              <TabsTrigger 
                key={ticker} 
                value={ticker} 
                className="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 text-sm font-medium rounded-md transition-colors data-[state=active]:active-bg data-[state=active]:text-blue-500 data-[state=active]:shadow-sm text-primary hover:text-primary hover-bg"
              >
                {ticker}
              </TabsTrigger>
            ))}
          </TabsList>
          
          {tickers.map((ticker) => {
            const decision = outputData.decisions![ticker];
            
            return (
              <TabsContent key={ticker} value={ticker} className="space-y-4">
                {/* Agent Analysis */}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('nodes.output.agent')}</TableHead>
                      <TableHead>{t('nodes.output.signal')}</TableHead>
                      <TableHead>{t('nodes.output.confidence')}</TableHead>
                      <TableHead>{t('nodes.output.reasoning')}</TableHead>
                    </TableRow>
                  </TableHeader>
                                     <TableBody>
                     {Object.entries(outputData.analyst_signals || {})
                       .filter(([agent, signals]: [string, any]) => 
                         ticker in signals && !agent.includes("risk_management")
                       )
                       .sort(([agentA], [agentB]) => agentA.localeCompare(agentB))
                       .map(([agent, signals]: [string, any]) => {
                         const signal = signals[ticker];
                         const signalType = signal.signal?.toUpperCase() || 'UNKNOWN';
                         const signalColor = getSignalColor(signalType);
                        
                        return (
                          <TableRow key={agent}>
                            <TableCell className="font-medium">
                              {translateNodeName(getDisplayName(agent))}
                            </TableCell>
                            <TableCell>
                              <span className={cn("font-medium", signalColor)}>
                                {signalType}
                              </span>
                            </TableCell>
                            <TableCell>{signal.confidence || 0}%</TableCell>
                            <TableCell className="max-w-md">
                              <ReasoningContent content={signal.reasoning} />
                            </TableCell>
                          </TableRow>
                        );
                      })}
                  </TableBody>
                </Table>
                
                {/* Trading Decision */}
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t('nodes.output.property')}</TableHead>
                      <TableHead>{t('nodes.output.value')}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell className="font-medium">{t('nodes.output.action')}</TableCell>
                      <TableCell>
                        <span className={cn("font-medium", getActionColor(decision.action || ''))}>
                          {decision.action?.toUpperCase() || 'UNKNOWN'}
                        </span>
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium">{t('nodes.output.currentPosition')}</TableCell>
                      <TableCell>
                        {(() => {
                          const position = outputData.current_positions?.[ticker];
                          const longShares = position?.long || 0;
                          const shortShares = position?.short || 0;
                          if (longShares > 0) {
                            return `${longShares} (Long)`;
                          } else if (shortShares > 0) {
                            return `${shortShares} (Short)`;
                          }
                          return '0';
                        })()}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium">{t('nodes.output.quantity')}</TableCell>
                      <TableCell>
                        {(() => {
                          const position = outputData.current_positions?.[ticker];
                          const longShares = position?.long || 0;
                          const shortShares = position?.short || 0;
                          // For "hold" action, show current position quantity instead of 0
                          if (decision.action?.toLowerCase() === 'hold') {
                            return longShares > 0 ? longShares : shortShares > 0 ? shortShares : 0;
                          }
                          return decision.quantity || 0;
                        })()}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell className="font-medium">{t('nodes.output.confidence')}</TableCell>
                      <TableCell>{decision.confidence?.toFixed(1) || 0}%</TableCell>
                    </TableRow>
                    {decision.reasoning && (
                      <TableRow>
                        <TableCell className="font-medium">{t('nodes.output.reasoning')}</TableCell>
                        <TableCell className="max-w-md">
                          <ReasoningContent content={decision.reasoning} />
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </TabsContent>
            );
          })}
        </Tabs>
      </CardContent>
    </Card>
  );
}

// Main component for regular output
export function RegularOutput({ 
  sortedAgents, 
  outputData 
}: { 
  sortedAgents: [string, any][]; 
  outputData: any; 
}) {
  return (
    <>
      <ProgressSection sortedAgents={sortedAgents} />
      <SummarySection outputData={outputData} />
      <AnalysisResultsSection outputData={outputData} />
    </>
  );
} 