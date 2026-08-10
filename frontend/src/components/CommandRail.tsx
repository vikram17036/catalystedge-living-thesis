import { useState } from 'react';
import {
  LayoutDashboard,
  History,
  BookOpen,
  Bell,
  Box,
  User,
  ChevronRight,
} from 'lucide-react';
import AuthModal from './AuthModal';
import { cn } from '../utils/cn';

type ViewType = 'dashboard' | 'history' | 'theses' | 'alerts';

interface CommandRailProps {
  currentView: ViewType;
  onNavigate: (view: ViewType) => void;
}

const primaryItems = [
  { icon: LayoutDashboard, label: 'ANALYSIS', viewId: 'dashboard' as ViewType },
  { icon: History, label: 'HISTORY', viewId: 'history' as ViewType },
];

const advancedItems = [
  { icon: BookOpen, label: 'THESES', viewId: 'theses' as ViewType },
  { icon: Bell, label: 'SYS_ALERTS', viewId: 'alerts' as ViewType },
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
        onClick={() => {
          onNavigate(item.viewId);
          setAdvancedOpen(false);
        }}
        className={cn(
          'group relative flex h-12 w-full items-center justify-center border-l-[3px] transition-colors outline-none',
          isActive
            ? 'border-accent bg-surface-2 text-accent'
            : 'border-transparent text-txt-muted hover:border-border-strong hover:bg-surface-2 hover:text-txt-primary'
        )}
        aria-label={item.label}
      >
        <item.icon className="h-4 w-4 shrink-0" />

        <div className="absolute left-14 z-50 hidden whitespace-nowrap rounded-sm border border-border-base bg-surface-1 px-3 py-1.5 font-mono text-micro font-bold uppercase tracking-widest text-txt-primary group-hover:flex">
          {item.label}
        </div>
      </button>
    );
  };

  return (
    <>
      <aside className="fixed left-0 top-0 z-40 flex h-screen w-14 flex-col items-center border-r border-border-base bg-surface-1">
        <div className="relative flex h-14 w-full items-center justify-center border-b border-border-base bg-surface-2/30 text-txt-primary">
          <Box className="h-5 w-5" />
          <div className="absolute bottom-0 h-px w-full bg-accent/20" />
        </div>

        <nav className="mt-4 flex w-full flex-1 flex-col items-center gap-1">
          {primaryItems.map(renderNavigationButton)}

          <button
            onClick={() => setAdvancedOpen((open) => !open)}
            className={cn(
              'group relative flex h-12 w-full items-center justify-center border-l-[3px] transition-colors outline-none',
              advancedOpen ||
                currentView === 'theses' ||
                currentView === 'alerts'
                ? 'border-accent bg-surface-2 text-accent'
                : 'border-transparent text-txt-muted hover:border-border-strong hover:bg-surface-2 hover:text-txt-primary'
            )}
            aria-label="ADVANCED"
            aria-expanded={advancedOpen}
          >
            <ChevronRight
              className={cn(
                'h-4 w-4 transition-transform',
                advancedOpen && 'rotate-180'
              )}
            />

            <div className="absolute left-14 z-50 hidden whitespace-nowrap rounded-sm border border-border-base bg-surface-1 px-3 py-1.5 font-mono text-micro font-bold uppercase tracking-widest text-txt-primary group-hover:flex">
              ADVANCED
            </div>
          </button>
        </nav>

        <div className="mt-auto flex h-14 w-full items-center justify-center border-t border-border-base bg-surface-2/10 font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
          ADV
        </div>
      </aside>

      {advancedOpen && (
        <>
          <button
            type="button"
            aria-label="Close advanced menu"
            className="fixed inset-0 z-30 cursor-default"
            onClick={() => setAdvancedOpen(false)}
          />

          <div className="fixed left-14 top-[164px] z-50 w-52 rounded-sm border border-border-base bg-surface-1 p-2 shadow-xl">
            <div className="mb-2 border-b border-border-base px-2 pb-2 font-mono text-micro font-bold uppercase tracking-widest text-txt-muted">
              ADVANCED_TOOLS
            </div>

            <button
              onClick={() => {
                setShowAuthModal(true);
                setAdvancedOpen(false);
              }}
              className="flex w-full items-center gap-3 rounded-sm px-3 py-2 font-mono text-micro font-bold uppercase tracking-widest text-txt-secondary transition-colors hover:bg-surface-2 hover:text-txt-primary"
            >
              <User className="h-4 w-4 text-accent" />
              AUTH_SYS
            </button>

            {advancedItems.map((item) => (
              <button
                key={item.label}
                onClick={() => {
                  onNavigate(item.viewId);
                  setAdvancedOpen(false);
                }}
                className={cn(
                  'flex w-full items-center gap-3 rounded-sm px-3 py-2 font-mono text-micro font-bold uppercase tracking-widest transition-colors hover:bg-surface-2',
                  currentView === item.viewId
                    ? 'bg-surface-2 text-accent'
                    : 'text-txt-secondary hover:text-txt-primary'
                )}
              >
                <item.icon className="h-4 w-4" />
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
