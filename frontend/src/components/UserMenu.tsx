/**
 * User Menu - Dropdown with user actions
 * Stage 3: User Belief System
 * Styled for Obsidian Terminal aesthetic (sharp, mono, dense)
 */

import { useState } from 'react';
import { User, LogOut, Settings, BookOpen, ChevronDown } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { cn } from '../utils/cn';

interface UserMenuProps {
  onOpenAuth: () => void;
}

export default function UserMenu({ onOpenAuth }: UserMenuProps) {
  const { user, loading, signOut } = useAuth();
  const [isOpen, setIsOpen] = useState(false);

  if (loading) {
    return (
      <div className="h-8 w-8 bg-surface-2 border border-border-base animate-pulse rounded-sm" />
    );
  }

  if (!user) {
    return (
      <button
        onClick={onOpenAuth}
        className="flex cursor-pointer items-center gap-2 rounded-md border border-border-base bg-surface-1 px-3 py-1.5 font-mono text-micro tracking-wide text-txt-secondary transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-txt-primary"
      >
        <User className="h-3.5 w-3.5" />
        Sign in
      </button>
    );
  }

  const displayName = user.user_metadata?.full_name || user.email?.split('@')[0] || 'USR_01';
  const avatarUrl = user.user_metadata?.avatar_url;

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 p-1 border border-transparent hover:border-border-base bg-transparent hover:bg-surface-1 transition-colors rounded-sm outline-none"
      >
        {avatarUrl ? (
          <img 
            src={avatarUrl} 
            alt={displayName}
            className="h-6 w-6 object-cover border border-border-base/50 rounded-sm grayscale hover:grayscale-0 transition-all"
          />
        ) : (
          <div className="h-6 w-6 border border-border-base bg-surface-2 flex items-center justify-center rounded-sm">
            <User className="h-3 w-3 text-txt-muted" />
          </div>
        )}
        <span className="text-micro font-mono text-txt-primary uppercase tracking-widest hidden sm:block max-w-[100px] truncate">
          {displayName}
        </span>
        <ChevronDown className={cn(
          "h-3 w-3 text-txt-muted transition-transform",
          isOpen && "rotate-180"
        )} />
      </button>

      {isOpen && (
        <>
          {/* Backdrop */}
          <div 
            className="fixed inset-0 z-40 cursor-default" 
            onClick={() => setIsOpen(false)} 
          />
          
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-2 z-50 w-48 border border-border-base bg-surface-1 shadow-none py-1 rounded-sm">
            <div className="px-3 py-2 border-b border-border-base/50 bg-surface-2/30">
              <p className="text-micro font-mono text-txt-primary uppercase tracking-widest truncate">{displayName}</p>
              <p className="text-micro font-mono text-txt-muted truncate mt-0.5">{user.email}</p>
            </div>

            <div className="py-1">
              <button className="flex w-full items-center gap-3 px-3 py-2 text-micro text-txt-secondary transition-colors hover:bg-surface-2 hover:text-txt-primary">
                <BookOpen className="h-3 w-3 text-txt-muted" />
                My theses
              </button>
              <button className="flex w-full items-center gap-3 px-3 py-2 text-micro text-txt-secondary transition-colors hover:bg-surface-2 hover:text-txt-primary">
                <Settings className="h-3 w-3 text-txt-muted" />
                Settings
              </button>
            </div>

            <div className="border-t border-border-base/50 py-1">
              <button 
                onClick={() => {
                  signOut();
                  setIsOpen(false);
                }}
                className="flex w-full items-center gap-3 px-3 py-2 text-micro text-kill transition-colors hover:bg-kill/10"
              >
                <LogOut className="h-3 w-3" />
                Sign out
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
