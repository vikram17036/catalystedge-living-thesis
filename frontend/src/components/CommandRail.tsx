import { useState } from 'react';
import {
  LayoutDashboard,
  History,
  BookOpen,
  Bell,
  Box,
  User,
  ChevronRight,
  FlaskConical,
  LineChart,
  GitCompare,
  AlertTriangle,
  Network,
  Bot,
} from 'lucide-react';
import AuthModal from './AuthModal';
import { cn } from '../utils/cn';

type ViewType =
  | 'dashboard'
  | 'history'
  | 'research'
  | 'lab'
  | 'analogs'
  | 'scenarios'
  | 'agent'
  | 'graph'
  | 'theses'
  | 'alerts';

interface CommandRailProps {
  currentView: ViewType;
  onNavigate: (view: ViewType) => void;
}

const primaryItems = [
  { icon: LayoutDashboard, label: 'Analysis', viewId: 'dashboard' as ViewType },
  { icon: History, label: 'History', viewId: 'history' as ViewType },
  { icon: FlaskConical, label: 'Research', viewId: 'research' as ViewType },
  { icon: LineChart, label: 'Strategy Lab', viewId: 'lab' as ViewType },
  { icon: GitCompare, label: 'Analogs', viewId: 'analogs' as ViewType },
  { icon: AlertTriangle, label: 'Scenarios', viewId: 'scenarios' as ViewType },
  { icon: Bot, label: 'Agent', viewId: 'agent' as ViewType },
];

const advancedItems = [
  { icon: BookOpen, label: 'Theses', viewId: 'theses' as ViewType },
  { icon: Network, label: 'Graph', viewId: 'graph' as ViewType },
  { icon: Bell, label: 'Alerts', viewId: 'alerts' as ViewType },
];

export default function CommandRail({
  currentView,
  onNavigate,
}: CommandRailProps) {
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [showAuthModal, setShowAuthModal] = useState(false);

  const renderNavigationButton = (
    item: (typeof primaryItems)[number] | (typeof advancedItems)[number]
  ) => {
    const isActive = currentView === item.viewId;

    return (
      <button
        key={item.label}
        type="button"
        onClick={() => {
          onNavigate(item.viewId);
          setAdvancedOpen(false);
        }}
        className={cn(
          'group relative flex h-11 w-full cursor-pointer items-center justify-center border-l-2 transition-colors outline-none',
          isActive
            ? 'border-accent bg-surface-3 text-accent'
            : 'border-transparent text-txt-muted hover:bg-surface-3/80 hover:text-txt-secondary'
        )}
        aria-label={item.label}
        title={item.label}
      >
        <item.icon className="h-4 w-4 shrink-0" strokeWidth={isActive ? 2 : 1.5} />
        <div
          role="tooltip"
          className="pointer-events-none absolute left-16 z-50 whitespace-nowrap rounded-md border border-border-base bg-surface-2 px-3 py-2 text-sm font-medium tracking-tight text-txt-primary opacity-0 shadow-lg transition-opacity delay-200 duration-150 group-hover:opacity-100 group-focus-visible:opacity-100"
        >
          {item.label}
        </div>
      </button>
    );
  };

  return (
    <>
      <aside className="fixed left-0 top-0 z-40 flex h-screen w-14 flex-col items-center border-r border-border-base bg-surface-1">
        <div className="relative flex h-14 w-full items-center justify-center border-b border-border-base text-txt-tertiary">
          <Box className="h-4 w-4" strokeWidth={1.75} />
        </div>

        <nav className="mt-2 flex w-full flex-1 flex-col items-center">
          {primaryItems.map(renderNavigationButton)}

          <button
            type="button"
            onClick={() => setAdvancedOpen((open) => !open)}
            className={cn(
              'group relative mt-1 flex h-11 w-full cursor-pointer items-center justify-center border-l-2 transition-colors outline-none',
              advancedOpen ||
                currentView === 'theses' ||
                currentView === 'graph' ||
                currentView === 'alerts'
                ? 'border-accent bg-surface-3 text-accent'
                : 'border-transparent text-txt-muted hover:bg-surface-3/80 hover:text-txt-secondary'
            )}
            aria-label="More"
            aria-expanded={advancedOpen}
            title="More"
          >
            <ChevronRight
              className={cn(
                'h-4 w-4 transition-transform',
                advancedOpen && 'rotate-90'
              )}
            />
            <div
              role="tooltip"
              className="pointer-events-none absolute left-16 z-50 whitespace-nowrap rounded-md border border-border-base bg-surface-2 px-3 py-2 text-sm font-medium tracking-tight text-txt-primary opacity-0 shadow-lg transition-opacity delay-200 duration-150 group-hover:opacity-100 group-focus-visible:opacity-100"
            >
              More
            </div>
          </button>
        </nav>

        <button
          type="button"
          onClick={() => setShowAuthModal(true)}
          className="mb-3 flex h-10 w-10 cursor-pointer items-center justify-center rounded-md text-txt-muted transition-colors hover:bg-surface-2 hover:text-txt-secondary"
          title="Account"
        >
          <User className="h-4 w-4" strokeWidth={1.5} />
        </button>
      </aside>

      {advancedOpen && (
        <>
          <button
            type="button"
            aria-label="Close menu"
            className="fixed inset-0 z-30 cursor-default bg-black/20"
            onClick={() => setAdvancedOpen(false)}
          />

          <div className="fixed left-14 top-16 z-50 w-48 rounded-md border border-border-base bg-surface-2 p-1.5 shadow-xl">
            <p className="ui-label px-2.5 py-2">Workspace</p>
            {advancedItems.map((item) => (
              <button
                key={item.label}
                type="button"
                onClick={() => {
                  onNavigate(item.viewId);
                  setAdvancedOpen(false);
                }}
                className={cn(
                  'flex w-full cursor-pointer items-center gap-2.5 rounded-md px-2.5 py-2 font-mono text-micro tracking-wide transition-colors',
                  currentView === item.viewId
                    ? 'bg-surface-3 text-accent'
                    : 'text-txt-secondary hover:bg-surface-3 hover:text-txt-primary'
                )}
              >
                <item.icon className="h-3.5 w-3.5" strokeWidth={1.5} />
                {item.label}
              </button>
            ))}
          </div>
        </>
      )}

      <AuthModal
        isOpen={showAuthModal}
        onClose={() => setShowAuthModal(false)}
      />
    </>
  );
}
