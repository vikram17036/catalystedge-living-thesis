import { useState, useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Header from './components/Header';
import CommandRail from './components/CommandRail';
import TickerInput, { TickerInputRef } from './components/TickerInput';
import QuickSelect from './components/QuickSelect';
import AnalysisHistory from './components/AnalysisHistory';
import ResultsTabs from './components/ResultsTabs';
import StreamingAnalysisProgress from './components/StreamingAnalysisProgress';
import KillAlertBanner from './components/KillAlertBanner';
import AlertsCenter from './components/AlertsCenter';
import EmptyState from './components/EmptyState';
import ErrorBoundary from './components/ErrorBoundary';
import ThesesPage from './pages/ThesesPage';
import ResearchPage from './pages/ResearchPage';
import LabPage from './pages/LabPage';
import AnalogsPage from './pages/AnalogsPage';
import ScenarioPage from './pages/ScenarioPage';
import AgentPage from './pages/AgentPage';
import ThesisGraphPage from './pages/ThesisGraphPage';
import { ThemeProvider } from './context/ThemeContext';
import { ToastProvider, useToast } from './components/ui/toast';
import { useAppKeyboardShortcuts } from './hooks/useKeyboardShortcuts';
import { useHealthCheck, useAnalysisResults } from './api/hooks';
import { useStreamingAnalysis } from './hooks/useStreamingAnalysis';
import { fetchKillAlerts, updateKillAlertStatus } from './api/alerts';
import { useAuth } from './context/AuthContext';
import type { AnalysisData, KillAlert } from './types/api';
import { AlertCircle } from 'lucide-react';

function AppContent() {
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<'dashboard' | 'history' | 'research' | 'lab' | 'analogs' | 'scenarios' | 'agent' | 'graph' | 'theses' | 'alerts'>('dashboard');
  const { addToast } = useToast();
  const { user } = useAuth();
  const tickerInputRef = useRef<TickerInputRef>(null);
  
  // Keyboard shortcuts (Cmd/Ctrl+K to focus search)
  useAppKeyboardShortcuts({
    onFocusSearch: () => tickerInputRef.current?.focus(),
  });
  
  // Health check
  const { data: health, isError: isHealthError } = useHealthCheck();
  const backendStatus = health?.status === 'ok' || health?.status === 'degraded' 
    ? 'online' 
    : isHealthError 
      ? 'offline' 
      : 'unknown';
  
  // Streaming Analysis (Stage 4)
  const streaming = useStreamingAnalysis();
  const [killAlerts, setKillAlerts] = useState<KillAlert[]>([]);
  
  // Fetch cached results when ticker changes
  const { data: resultsData, refetch: refetchResults } = useAnalysisResults(selectedTicker);
  
  // Use streaming final data or cached results
  const analysisData: AnalysisData | null = 
    streaming.finalData || resultsData?.data || null;

  const refreshKillAlerts = useCallback(async () => {
    if (!user) {
      setKillAlerts([]);
      return;
    }
    try {
      const alerts = await fetchKillAlerts(selectedTicker || undefined);
      setKillAlerts(alerts);
    } catch {
      /* non-fatal */
    }
  }, [user, selectedTicker]);

  useEffect(() => {
    refreshKillAlerts();
  }, [refreshKillAlerts]);

  const handleAnalyze = (ticker: string, _force: boolean = false) => {
    setSelectedTicker(ticker);
    streaming.startAnalysis(ticker);
  };

  const handleRefresh = () => {
    if (selectedTicker) {
      handleAnalyze(selectedTicker, true);
    }
  };

  const handleSelectHistory = (ticker: string) => {
    setSelectedTicker(ticker);
    streaming.reset();
    setCurrentView('dashboard');
  };

  const handleCancel = () => {
    streaming.stopAnalysis();
    setSelectedTicker(null);
    addToast({
      type: 'info',
      title: 'Analysis Cancelled',
      message: 'The analysis request has been cancelled.',
    });
  };

  // Refetch cached results when streaming completes
  useEffect(() => {
    if (streaming.finalData && selectedTicker) {
      refetchResults();
    }
  }, [streaming.finalData, selectedTicker, refetchResults]);

  const isLoading = streaming.isStreaming;
  const error = streaming.error;

  // Show toast notification for errors
  useEffect(() => {
    if (error) {
      addToast({
        type: 'error',
        title: 'Analysis Failed',
        message: error,
        duration: 8000,
      });
    }
  }, [error, addToast]);

  // Show toast for successful streaming analysis
  useEffect(() => {
    if (streaming.finalData?.ticker) {
      addToast({
        type: 'success',
        title: 'Analysis Complete',
        message: `Successfully analyzed ${streaming.finalData.ticker}`,
      });
    }
  }, [streaming.finalData, addToast]);

  // Show toast when health check fails
  useEffect(() => {
    if (isHealthError) {
      addToast({
        type: 'warning',
        title: 'Connection Issue',
        message: 'Unable to connect to the backend server.',
        duration: 10000,
      });
    }
  }, [isHealthError, addToast]);

  // Render standalone analysis history
  if (currentView === 'history') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <div className="p-4 md:p-6 lg:p-8">
            <div className="mb-6">
              <p className="ui-label text-accent">History</p>
              <h1 className="mt-2 text-2xl font-semibold tracking-tight text-txt-primary">
                Recent market research
              </h1>
              <p className="mt-2 max-w-2xl text-sm text-txt-secondary">
                Open a previously cached analysis without running the AI workflow again.
              </p>
            </div>
            <div className="max-w-3xl">
              <AnalysisHistory
                variant="page"
                onSelectHistory={handleSelectHistory}
              />
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Render Research (Event Study) view
  if (currentView === 'research') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <ResearchPage />
        </main>
      </div>
    );
  }

  // Render Strategy Lab view
  if (currentView === 'lab') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <LabPage />
        </main>
      </div>
    );
  }

  // Render Historical Analog Search view
  if (currentView === 'analogs') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <AnalogsPage />
        </main>
      </div>
    );
  }

  if (currentView === 'scenarios') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <ScenarioPage />
        </main>
      </div>
    );
  }

  if (currentView === 'agent') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <AgentPage />
        </main>
      </div>
    );
  }

  if (currentView === 'graph') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <ThesisGraphPage />
        </main>
      </div>
    );
  }

  // Render ThesesPage if in theses view
  if (currentView === 'theses') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 relative z-10">
          <Header backendStatus={backendStatus} />
          <ThesesPage onBack={() => setCurrentView('dashboard')} />
        </main>
      </div>
    );
  }

  // Render AlertsCenter if in alerts view
  if (currentView === 'alerts') {
    return (
      <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
        <CommandRail onNavigate={setCurrentView} currentView={currentView} />
        <main className="flex flex-1 flex-col ml-14 p-6 relative z-10">
          <Header backendStatus={backendStatus} />
          <div className="flex-1 mt-6">
             <AlertsCenter />
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-canvas font-mono text-txt-primary selection:bg-accent selection:text-canvas antialiased relative">
      {/* 48px Command Rail (Sidebar Replacement) */}
      <CommandRail onNavigate={setCurrentView} currentView={currentView} />

      {/* Main Content Area */}
      <main className="flex flex-1 flex-col ml-14 relative z-10">
        {/* Top Bar */}
        <Header backendStatus={backendStatus} />

        {/* Dashboard Content Padded Area */}
        <div className="p-4 md:p-6 lg:p-8">
          
          {/* Control Bar (Input & Quick Select) */}
          <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-6">
            <div className="lg:col-span-8">
              <TickerInput ref={tickerInputRef} onAnalyze={handleAnalyze} disabled={isLoading} />
            </div>
            <div className="lg:col-span-4">
               <QuickSelect
                 onSelect={handleAnalyze}
                 disabled={isLoading}
                 activeTicker={selectedTicker}
               />
            </div>
          </div>

          {/* Main Display Area */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0 }}
                className="mb-6 rounded-sm border border-bear/50 bg-bear/10 p-4 text-bear"
              >
                <div className="flex items-center gap-2">
                  <AlertCircle className="h-4 w-4" />
                  <span className="text-sm font-semibold tracking-wide">Analysis failed</span>
                </div>
                <p className="mt-2 text-micro font-mono tracking-wider">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>
          
          <AnimatePresence mode="wait">
            {isLoading && selectedTicker ? (
              <motion.div
                key="loading"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15, ease: "linear" }}
              >
                <StreamingAnalysisProgress 
                  ticker={selectedTicker}
                  isStreaming={streaming.isStreaming}
                  progress={streaming.progress}
                  currentTool={streaming.currentTool}
                  events={streaming.events}
                  partialData={streaming.partialData}
                  error={streaming.error}
                  onCancel={handleCancel}
                />
              </motion.div>
            ) : !isLoading && analysisData ? (
              <motion.div
                key="results"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15, ease: "linear" }}
                className="space-y-4"
              >
                {/* Kill Alerts Banner */}
                {killAlerts.length > 0 && (
                  <KillAlertBanner
                    alerts={killAlerts}
                    onDismiss={async (id) => {
                      try {
                        await updateKillAlertStatus(id, 'dismissed');
                      } catch { /* ignore */ }
                      setKillAlerts(prev => prev.filter(a => a.id !== id));
                    }}
                    onAcknowledge={async (id) => {
                      try {
                        await updateKillAlertStatus(id, 'acknowledged');
                      } catch { /* ignore */ }
                      setKillAlerts(prev => prev.filter(a => a.id !== id));
                      addToast({ type: 'info', title: 'Alert Acknowledged', message: 'Review your thesis to take action.' });
                    }}
                    onViewThesis={() => setCurrentView('theses')}
                  />
                )}
                
                <ResultsTabs 
                  result={analysisData} 
                  onRefresh={handleRefresh}
                  isRefreshing={isLoading}
                  onAlertCreated={refreshKillAlerts}
                />
              </motion.div>
            ) : !isLoading && !error ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
              >
                <div className="grid grid-cols-1 gap-4 lg:grid-cols-12 lg:gap-6">
                  <div className="lg:col-span-8">
                     <EmptyState
                       type="welcome"
                       onNavigate={(view) => setCurrentView(view)}
                       onFocusSearch={() => tickerInputRef.current?.focus()}
                     />
                  </div>
                  <div className="lg:col-span-4">
                     <AnalysisHistory onSelectHistory={handleSelectHistory} />
                  </div>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider>
        <ToastProvider>
          <AppContent />
        </ToastProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;

