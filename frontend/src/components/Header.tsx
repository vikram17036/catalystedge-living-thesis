import { useState } from 'react';
import UserMenu from './UserMenu';
import AuthModal from './AuthModal';

const Header = () => {
  const [showAuth, setShowAuth] = useState(false);

  return (
    <>
      <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-border-base bg-canvas px-6 md:px-8">
        <span className="font-mono text-sm font-bold tracking-widest text-txt-primary">
          CATALYSTEDGE_AI
        </span>
        <UserMenu onOpenAuth={() => setShowAuth(true)} />
      </header>
      <AuthModal isOpen={showAuth} onClose={() => setShowAuth(false)} />
    </>
  );
};

export default Header;
