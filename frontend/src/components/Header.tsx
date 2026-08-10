import { useState } from 'react';
import UserMenu from './UserMenu';
import AuthModal from './AuthModal';
import { Separator } from './ui/separator';
import { cn } from '../utils/cn';

interface HeaderProps {
  backendStatus?: 'online' | 'offline' | 'unknown';
}

const Header = ({ backendStatus = 'unknown' }: HeaderProps) => {
  const [showAuth, setShowAuth] = useState(false);
  const online = backendStatus === 'online';
  const offline = backendStatus === 'offline';

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border-base bg-canvas/90 px-5 backdrop-blur-md md:px-8">
        <div className="flex items-center gap-3">
          <span className="font-mono text-sm font-semibold tracking-[0.12em] text-txt-primary">
            CatalystEdge
          </span>
          <Separator orientation="vertical" className="hidden h-4 sm:block" />
          <span className="ui-label hidden sm:inline">Living thesis intelligence</span>
        </div>
        <div className="flex items-center gap-3">
          <div
            className="flex items-center gap-1.5"
            title={online ? 'API online' : offline ? 'API offline' : 'Checking API…'}
          >
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full',
                online && 'bg-bull',
                offline && 'animate-pulse bg-bear',
                !online && !offline && 'bg-txt-muted'
              )}
            />
            <span className="hidden font-mono text-micro text-txt-muted sm:inline">
              {online ? 'Online' : offline ? 'Offline' : '…'}
            </span>
          </div>
          <UserMenu onOpenAuth={() => setShowAuth(true)} />
        </div>
      </header>
      <AuthModal isOpen={showAuth} onClose={() => setShowAuth(false)} />
    </>
  );
};

export default Header;
