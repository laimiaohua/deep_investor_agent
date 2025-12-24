import i18n from '@/i18n/config';

/**
 * Translate node name based on node type and name
 */
export function translateNodeName(name: string, nodeType?: string): string {
  const t = i18n.t;
  
  // Map node names to translation keys (base nodes)
  const nameMap: Record<string, string> = {
    'Portfolio Input': t('nodes.portfolioInput.name'),
    'Stock Input': t('nodes.stockInput.name'),
    'Portfolio Manager': t('nodes.portfolioManager.name'),
  };
  
  // If it's a base node, return translated version
  if (nameMap[name]) {
    return nameMap[name];
  }
  
  // Map agent names to translation keys
  const agentNameMap: Record<string, string> = {
    'Warren Buffett': t('nodes.agents.warrenBuffettName'),
    'Ben Graham': t('nodes.agents.benGrahamName'),
    'Bill Ackman': t('nodes.agents.billAckmanName'),
    'Cathie Wood': t('nodes.agents.cathieWoodName'),
    'Charlie Munger': t('nodes.agents.charlieMungerName'),
    'Michael Burry': t('nodes.agents.michaelBurryName'),
    'Mohnish Pabrai': t('nodes.agents.mohnishPabraiName'),
    'Peter Lynch': t('nodes.agents.peterLynchName'),
    'Phil Fisher': t('nodes.agents.philFisherName'),
    'Rakesh Jhunjhunwala': t('nodes.agents.rakeshJhunjhunwalaName'),
    'Stanley Druckenmiller': t('nodes.agents.stanleyDruckenmillerName'),
    'Aswath Damodaran': t('nodes.agents.aswathDamodaranName'),
    'Technical Analyst': t('nodes.agents.technicalAnalystName'),
    'Fundamentals Analyst': t('nodes.agents.fundamentalsAnalystName'),
    'Growth Analyst': t('nodes.agents.growthAnalystName'),
    'News Sentiment Analyst': t('nodes.agents.newsSentimentAnalystName'),
    'Sentiment Analyst': t('nodes.agents.sentimentAnalystName'),
    'Valuation Analyst': t('nodes.agents.valuationAnalystName'),
    'Duan Yongping': t('nodes.agents.duanYongpingName'),
    'Zhang Lei': t('nodes.agents.zhangLeiName'),
    'Qiu Guolu': t('nodes.agents.qiuGuoluName'),
    'Feng Liu': t('nodes.agents.fengLiuName'),
    'Dan Bin': t('nodes.agents.danBinName'),
  };
  
  // Map swarm group names to translation keys
  const swarmNameMap: Record<string, string> = {
    'Data Wizards': t('nodes.swarms.dataWizards'),
    'Market Mavericks': t('nodes.swarms.marketMavericks'),
    'Value Investors': t('nodes.swarms.valueInvestors'),
  };
  
  // If it's an agent name, return translated version
  if (agentNameMap[name]) {
    return agentNameMap[name];
  }
  
  // If it's a swarm group name, return translated version
  if (swarmNameMap[name]) {
    return swarmNameMap[name];
  }
  
  // Fallback: return original name
  return name;
}

/**
 * Translate node description based on node type and name
 */
export function translateNodeDescription(description: string, nodeName?: string): string {
  const t = i18n.t;
  
  // Map node descriptions to translation keys (base nodes)
  const descriptionMap: Record<string, string> = {
    'Enter your portfolio including tickers, shares, and prices. Connect this node to Analysts to generate insights.': 
      t('nodes.portfolioInput.description'),
    'Enter individual stocks and connect this node to Analysts to generate insights.': 
      t('nodes.stockInput.description'),
    'Generates investment decisions based on input from Analysts.': 
      t('nodes.portfolioManager.description'),
  };
  
  // If it's a base node description, return translated version
  if (descriptionMap[description]) {
    return descriptionMap[description];
  }
  
  // Map agent investing styles to translation keys
  const agentDescriptionMap: Record<string, string> = {
    'Seeks companies with strong fundamentals and competitive advantages through value investing and long-term ownership.': 
      t('nodes.agents.warrenBuffett'),
    'Emphasizes a margin of safety and invests in undervalued companies with strong fundamentals through systematic value analysis.': 
      t('nodes.agents.benGraham'),
    'Seeks to influence management and unlock value through strategic activism and contrarian investment positions.': 
      t('nodes.agents.billAckman'),
    'Focuses on disruptive innovation and growth, investing in companies that are leading technological advancements and market disruption.': 
      t('nodes.agents.cathieWood'),
    'Advocates for value investing with a focus on quality businesses and long-term growth through rational decision-making.': 
      t('nodes.agents.charlieMunger'),
    'Makes contrarian bets, often shorting overvalued markets and investing in undervalued assets through deep fundamental analysis.': 
      t('nodes.agents.michaelBurry'),
    'Focuses on value investing and long-term growth through fundamental analysis and a margin of safety.': 
      t('nodes.agents.mohnishPabrai'),
    'Invests in companies with understandable business models and strong growth potential using the \'buy what you know\' strategy.': 
      t('nodes.agents.peterLynch'),
    'Emphasizes investing in companies with strong management and innovative products, focusing on long-term growth through scuttlebutt research.': 
      t('nodes.agents.philFisher'),
    'Leverages macroeconomic insights to invest in high-growth sectors, particularly within emerging markets and domestic opportunities.': 
      t('nodes.agents.rakeshJhunjhunwala'),
    'Focuses on macroeconomic trends, making large bets on currencies, commodities, and interest rates through top-down analysis.': 
      t('nodes.agents.stanleyDruckenmiller'),
    'Focuses on intrinsic value and financial metrics to assess investment opportunities through rigorous valuation analysis.': 
      t('nodes.agents.aswathDamodaran'),
    'Focuses on chart patterns and market trends to make investment decisions, often using technical indicators and price action analysis.': 
      t('nodes.agents.technicalAnalyst'),
    'Delves into financial statements and economic indicators to assess the intrinsic value of companies through fundamental analysis.': 
      t('nodes.agents.fundamentalsAnalyst'),
    'Analyzes growth trends and valuation to identify growth opportunities through growth analysis.': 
      t('nodes.agents.growthAnalyst'),
    'Analyzes news sentiment to predict market movements and identify opportunities through news analysis.': 
      t('nodes.agents.newsSentimentAnalyst'),
    'Gauges market sentiment and investor behavior to predict market movements and identify opportunities through behavioral analysis.': 
      t('nodes.agents.sentimentAnalyst'),
    'Specializes in determining the fair value of companies, using various valuation models and financial metrics for investment decisions.': 
      t('nodes.agents.valuationAnalyst'),
    'Focuses on high-quality consumer and internet companies, emphasizing simple business models, stable cash flows, and reliable management. Prefers to hold fewer but excellent companies for the long term.': 
      t('nodes.agents.duanYongping'),
    'Known as \'friend of time\', emphasizes good companies + good price + long time. Prefers companies with global vision and compounding capabilities.': 
      t('nodes.agents.zhangLei'),
    'Combines macro and industry cycle analysis, building positions during pessimism and reducing during optimism. Values valuation safety margin and risk-reward ratio.': 
      t('nodes.agents.qiuGuolu'),
    'Builds positions gradually during extreme sentiment and market misunderstandings. Focuses on expectation gaps and intrinsic improvements, willing to endure volatility for the long term.': 
      t('nodes.agents.fengLiu'),
    'Emphasizes being \'friends of time\' with excellent companies. Prefers brand consumer, healthcare, and blue-chip leaders with long-term growth potential.': 
      t('nodes.agents.danBin'),
  };
  
  // If it's an agent investing style, return translated version
  if (agentDescriptionMap[description]) {
    return agentDescriptionMap[description];
  }
  
  // Fallback: return original description
  return description;
}

/**
 * Translate node status
 */
export function translateNodeStatus(status: string): string {
  const t = i18n.t;
  
  const statusMap: Record<string, string> = {
    'IDLE': t('nodes.statusIdle'),
    'IN_PROGRESS': t('nodes.statusInProgress'),
    'COMPLETE': t('nodes.statusComplete'),
    'ERROR': t('nodes.statusError'),
    'idle': t('nodes.statusIdle'),
    'in_progress': t('nodes.statusInProgress'),
    'complete': t('nodes.statusComplete'),
    'error': t('nodes.statusError'),
    'Idle': t('nodes.statusIdle'),
    'In Progress': t('nodes.statusInProgress'),
    'Complete': t('nodes.statusComplete'),
    'Error': t('nodes.statusError'),
  };
  
  // Try exact match first
  if (statusMap[status]) {
    return statusMap[status];
  }
  
  // Try case-insensitive match
  const lowerStatus = status.toLowerCase().replace(/_/g, ' ');
  if (statusMap[lowerStatus]) {
    return statusMap[lowerStatus];
  }
  
  // Fallback: capitalize the status
  return status.charAt(0).toUpperCase() + status.slice(1).toLowerCase();
}

/**
 * Translate progress message from backend
 * These are the status messages sent by agents during analysis
 */
export function translateProgressMessage(message: string): string {
  const t = i18n.t;
  
  // Map backend progress messages to translation keys
  const messageMap: Record<string, string> = {
    // Common statuses
    'Done': t('progress.done'),
    
    // Data fetching
    'Fetching financial metrics': t('progress.fetchingFinancialMetrics'),
    'Fetching financial data': t('progress.fetchingFinancialData'),
    'Fetching line items': t('progress.fetchingLineItems'),
    'Fetching financial line items': t('progress.fetchingFinancialLineItems'),
    'Gathering financial line items': t('progress.gatheringFinancialLineItems'),
    'Fetching insider trades': t('progress.fetchingInsiderTrades'),
    'Fetching company news': t('progress.fetchingCompanyNews'),
    'Fetching market cap': t('progress.fetchingMarketCap'),
    'Getting market cap': t('progress.gettingMarketCap'),
    'Fetching price data': t('progress.fetchingPriceData'),
    'Fetching recent price data for momentum': t('progress.fetchingRecentPriceData'),
    'Gathering comprehensive line items': t('progress.gatheringLineItems'),
    'Fetching CN/HK balance sheet (DeepAlpha)': t('progress.fetchingCNBalanceSheet'),
    
    // Analysis stages
    'Analyzing': t('progress.analyzing'),
    'Analyzing fundamentals': t('progress.analyzingFundamentals'),
    'Analyzing consistency': t('progress.analyzingConsistency'),
    'Analyzing competitive moat': t('progress.analyzingCompetitiveMoat'),
    'Analyzing moat strength': t('progress.analyzingMoatStrength'),
    'Analyzing pricing power': t('progress.analyzingPricingPower'),
    'Analyzing book value growth': t('progress.analyzingBookValueGrowth'),
    'Analyzing management quality': t('progress.analyzingManagementQuality'),
    'Analyzing business predictability': t('progress.analyzingBusinessPredictability'),
    'Analyzing growth & momentum': t('progress.analyzingGrowthMomentum'),
    'Analyzing growth': t('progress.analyzingGrowth'),
    'Analyzing profitability': t('progress.analyzingProfitability'),
    'Analyzing value': t('progress.analyzingValue'),
    'Analyzing balance sheet': t('progress.analyzingBalanceSheet'),
    'Analyzing insider activity': t('progress.analyzingInsiderActivity'),
    'Analyzing contrarian sentiment': t('progress.analyzingContrarianSentiment'),
    'Analyzing growth and reinvestment': t('progress.analyzingGrowthReinvestment'),
    'Analyzing risk profile': t('progress.analyzingRiskProfile'),
    'Analyzing sentiment': t('progress.analyzingSentiment'),
    'Analyzing trading patterns': t('progress.analyzingTradingPatterns'),
    'Analyzing price data': t('progress.analyzingPriceData'),
    'Analyzing volatility': t('progress.analyzingVolatility'),
    'Analyzing risk-reward': t('progress.analyzingRiskReward'),
    'Calculating intrinsic value': t('progress.calculatingIntrinsicValue'),
    'Calculating intrinsic value (DCF)': t('progress.calculatingDCF'),
    'Calculating Munger-style valuation': t('progress.calculatingMungerValuation'),
    'Calculating WACC and enhanced DCF': t('progress.calculatingWACCDCF'),
    'Calculating trend signals': t('progress.calculatingTrendSignals'),
    'Calculating mean reversion': t('progress.calculatingMeanReversion'),
    'Calculating momentum': t('progress.calculatingMomentum'),
    'Performing Druckenmiller-style valuation': t('progress.performingDruckenmillerValuation'),
    'Assessing relative valuation': t('progress.assessingRelativeValuation'),
    'Analyzing balance sheet and capital structure': t('progress.analyzingCapitalStructure'),
    'Analyzing activism potential': t('progress.analyzingActivismPotential'),
    'Calculating intrinsic value & margin of safety': t('progress.calculatingIntrinsicValue'),
    'Analyzing downside protection': t('progress.analyzingDownsideProtection'),
    'Analyzing cash yield and valuation': t('progress.analyzingCashYield'),
    'Assessing potential to double': t('progress.assessingDoublePotenial'),
    'Analyzing earnings stability': t('progress.analyzingEarningsStability'),
    'Analyzing financial strength': t('progress.analyzingFinancialStrength'),
    'Analyzing Graham valuation': t('progress.analyzingGrahamValuation'),
    
    // Generation stages
    'Generating LLM output': t('progress.generatingLLMOutput'),
    'Generating analysis': t('progress.generatingAnalysis'),
    'Generating Warren Buffett analysis': t('progress.generatingWarrenBuffettAnalysis'),
    'Generating Charlie Munger analysis': t('progress.generatingCharlieMungerAnalysis'),
    'Generating Ben Graham analysis': t('progress.generatingBenGrahamAnalysis'),
    'Generating Peter Lynch analysis': t('progress.generatingPeterLynchAnalysis'),
    'Generating Phil Fisher-style analysis': t('progress.generatingPhilFisherAnalysis'),
    'Generating Cathie Wood analysis': t('progress.generatingCathieWoodAnalysis'),
    'Generating Stanley Druckenmiller analysis': t('progress.generatingStanleyDruckenmillerAnalysis'),
    'Generating Damodaran analysis': t('progress.generatingDamodaranAnalysis'),
    'Generating Jhunjhunwala analysis': t('progress.generatingJhunjhunwalaAnalysis'),
    'Generating Duan Yongping analysis': t('progress.generatingDuanYongpingAnalysis'),
    'Generating Zhang Lei analysis': t('progress.generatingZhangLeiAnalysis'),
    'Generating Qiu Guolu analysis': t('progress.generatingQiuGuoluAnalysis'),
    'Generating Feng Liu analysis': t('progress.generatingFengLiuAnalysis'),
    'Generating Dan Bin analysis': t('progress.generatingDanBinAnalysis'),
    'Generating Bill Ackman analysis': t('progress.generatingBillAckmanAnalysis'),
    'Generating Pabrai analysis': t('progress.generatingPabraiAnalysis'),
    'Generating trading decisions': t('progress.generatingTradingDecisions'),
    
    // Processing stages
    'Processing analyst signals': t('progress.processingAnalystSignals'),
    'Calculating technical indicators': t('progress.calculatingTechnicalIndicators'),
    
    // Error messages
    'Failed: No financial metrics found': t('progress.failedNoMetrics'),
    'Failed: Not enough financial metrics': t('progress.failedNotEnoughMetrics'),
    'Failed: No financial metrics': t('progress.failedNoMetrics'),
    'Failed: Insufficient financial line items': t('progress.failedInsufficientLineItems'),
  };
  
  // Try exact match first
  if (messageMap[message]) {
    return messageMap[message];
  }
  
  // Try pattern matching for dynamic messages
  if (message.startsWith('Failed:')) {
    // Check if we have a translation key with this pattern
    const failedKey = `progress.${message.replace(/[^a-zA-Z]/g, '')}`;
    const translated = t(failedKey);
    if (translated !== failedKey) {
      return translated;
    }
    // Generic failed message
    return t('progress.failed') + ': ' + message.replace('Failed:', '').trim();
  }
  
  // Fallback: return original message
  return message;
}

