import React, { useState, useRef, useEffect, useCallback } from 'react';
import { createPortal } from 'react-dom';
import { Tag } from '@docrouter/sdk';
import { isColorLight } from '@/utils/colors';

interface TagSelectorProps {
  availableTags: Tag[];
  selectedTagIds: string[];
  onChange: (tagIds: string[]) => void;
  disabled?: boolean;
  placeholder?: string;
}

const DROPDOWN_Z_INDEX = 300;
const VIEWPORT_PAD_PX = 8;

const TagSelector: React.FC<TagSelectorProps> = ({
  availableTags,
  selectedTagIds,
  onChange,
  disabled = false,
  placeholder = 'Select tags...',
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [search, setSearch] = useState('');
  const [menuStyle, setMenuStyle] = useState<React.CSSProperties>({ visibility: 'hidden' });
  const anchorRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  const updateMenuPosition = useCallback(() => {
    const anchor = anchorRef.current;
    if (!anchor || typeof window === 'undefined') return;
    const rect = anchor.getBoundingClientRect();
    const width = rect.width;
    let left = rect.left;
    left = Math.max(VIEWPORT_PAD_PX, Math.min(left, window.innerWidth - width - VIEWPORT_PAD_PX));
    const spaceBelow = window.innerHeight - rect.bottom - VIEWPORT_PAD_PX;
    const maxHeight = Math.min(240, Math.max(120, spaceBelow));
    setMenuStyle({
      position: 'fixed',
      top: rect.bottom + 4,
      left,
      width,
      maxHeight,
      zIndex: DROPDOWN_Z_INDEX,
      visibility: 'visible',
    });
  }, []);

  useEffect(() => {
    if (!dropdownOpen) return;
    updateMenuPosition();
    window.addEventListener('scroll', updateMenuPosition, true);
    window.addEventListener('resize', updateMenuPosition);
    return () => {
      window.removeEventListener('scroll', updateMenuPosition, true);
      window.removeEventListener('resize', updateMenuPosition);
    };
  }, [dropdownOpen, updateMenuPosition]);

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      const target = event.target as Node;
      if (anchorRef.current?.contains(target)) return;
      if (menuRef.current?.contains(target)) return;
      setDropdownOpen(false);
    }
    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownOpen]);

  const filteredTags = availableTags.filter(
    (tag) =>
      tag.name.toLowerCase().includes(search.toLowerCase()) && !selectedTagIds.includes(tag.id)
  );

  const menu =
    dropdownOpen && typeof document !== 'undefined'
      ? createPortal(
          <div
            ref={menuRef}
            style={menuStyle}
            className="flex flex-col bg-white border border-gray-300 rounded-md shadow-lg overflow-hidden"
          >
            <input
              type="text"
              className="w-full px-2 py-1 border-b border-gray-200 focus:outline-none shrink-0"
              placeholder="Search tags..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              autoFocus
              disabled={disabled}
            />
            <div className="p-2 flex flex-wrap gap-2 overflow-y-auto min-h-0 flex-1">
              {filteredTags.map((tag) => (
                <button
                  key={tag.id}
                  type="button"
                  className={`flex items-center px-2 py-1 rounded text-sm shadow-sm transition-all ${
                    isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                  } hover:scale-105`}
                  style={{ backgroundColor: tag.color }}
                  onClick={() => {
                    onChange([...selectedTagIds, tag.id]);
                    setSearch('');
                  }}
                  disabled={disabled}
                >
                  {tag.name}
                  <svg className="h-4 w-4 ml-1 text-white/70" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M10 5a1 1 0 01.993.883L11 6v4h4a1 1 0 01.117 1.993L15 12h-4v4a1 1 0 01-1.993.117L9 16v-4H5a1 1 0 01-.117-1.993L5 10h4V6a1 1 0 01.883-.993L10 5z"
                      clipRule="evenodd"
                    />
                  </svg>
                </button>
              ))}
              {filteredTags.length === 0 && (
                <div className="px-3 py-2 text-gray-400">
                  {availableTags.length === 0 ? 'No tags in this organization' : 'No tags found'}
                </div>
              )}
            </div>
          </div>,
          document.body
        )
      : null;

  return (
    <div>
      <div className="flex flex-wrap gap-2 mb-2">
        {selectedTagIds.map((tagId) => {
          const tag = availableTags.find((t) => t.id === tagId);
          if (!tag) return null;
          return (
            <span
              key={tag.id}
              className={`flex items-center px-2 py-1 rounded text-sm mr-1 mb-1 ${
                isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
              }`}
              style={{ backgroundColor: tag.color }}
            >
              {tag.name}
              <button
                type="button"
                className={`ml-1 text-xs font-bold hover:opacity-80 transition-opacity ${
                  isColorLight(tag.color) ? 'text-gray-700 hover:text-red-600' : 'text-white/90 hover:text-red-200'
                }`}
                onClick={() => onChange(selectedTagIds.filter((id) => id !== tag.id))}
                disabled={disabled}
              >
                ×
              </button>
            </span>
          );
        })}
      </div>
      <button
        ref={anchorRef}
        type="button"
        className="w-full border border-gray-300 rounded-md px-3 py-2 text-left bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
        onClick={() => setDropdownOpen((open) => !open)}
        disabled={disabled}
      >
        {selectedTagIds.length === 0 ? placeholder : 'Add more tags'}
      </button>
      {menu}
    </div>
  );
};

export default TagSelector;
