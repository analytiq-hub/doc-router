import React, { useState, useRef, useEffect } from 'react';
import { Tag } from '@docrouter/sdk';
import { isColorLight } from '@/utils/colors';

interface SingleTagSelectorProps {
  availableTags: Tag[];
  selectedTag: Tag | null;
  onChange: (tag: Tag | null) => void;
  disabled?: boolean;
  placeholder?: string;
  label?: string;
}

const SingleTagSelector: React.FC<SingleTagSelectorProps> = ({
  availableTags,
  selectedTag,
  onChange,
  disabled = false,
  placeholder = 'Select a tag...',
  label
}) => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [search, setSearch] = useState('');
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setDropdownOpen(false);
      }
    }
    if (dropdownOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [dropdownOpen]);

  return (
    <div>
      {/* Label */}
      {label && (
        <label className="block text-sm font-medium text-gray-700 mb-2">
          {label}
        </label>
      )}

      {/* Selected tag as pill (similar to TagSelector) */}
      <div className="flex flex-wrap gap-2 mb-2">
        {selectedTag && (
          <span
            className={`flex items-center px-2 py-1 rounded text-sm mr-1 mb-1 ${
              isColorLight(selectedTag.color) ? 'text-gray-800' : 'text-white'
            }`}
            style={{ backgroundColor: selectedTag.color }}
          >
            {selectedTag.name}
            <button
              type="button"
              className={`ml-1 text-xs font-bold hover:opacity-80 transition-opacity ${
                isColorLight(selectedTag.color) ? 'text-gray-700 hover:text-red-600' : 'text-white/90 hover:text-red-200'
              }`}
              onClick={() => onChange(null)}
              disabled={disabled}
            >
              ×
            </button>
          </span>
        )}
      </div>

      {/* Dropdown input (exact match to TagSelector) */}
      <div className="relative" ref={dropdownRef}>
        <button
          type="button"
          className="w-full border border-gray-300 rounded-md px-3 py-2 text-left bg-white focus:outline-none focus:ring-2 focus:ring-primary-500"
          onClick={() => setDropdownOpen(open => !open)}
          disabled={disabled}
        >
          {selectedTag ? 'Change tag' : placeholder}
        </button>
        {dropdownOpen && (
          <div className="absolute z-10 mt-1 w-full bg-white border border-gray-300 rounded-md shadow-lg max-h-60 overflow-y-auto">
            <input
              type="text"
              className="w-full px-2 py-1 border-b border-gray-200 focus:outline-none"
              placeholder="Search tags..."
              value={search}
              onChange={e => setSearch(e.target.value)}
              autoFocus
              disabled={disabled}
            />
            <div className="p-2 flex flex-wrap gap-2">
              {availableTags
                .filter(tag =>
                  tag.name.toLowerCase().includes(search.toLowerCase()) &&
                  selectedTag?.id !== tag.id
                )
                .map(tag => (
                  <button
                    key={tag.id}
                    type="button"
                    className={`flex items-center px-2 py-1 rounded text-sm shadow-sm transition-all ${
                      isColorLight(tag.color) ? 'text-gray-800' : 'text-white'
                    } hover:scale-105`}
                    style={{ backgroundColor: tag.color }}
                    onClick={() => {
                      onChange(tag);
                      setSearch('');
                      setDropdownOpen(false);
                    }}
                    disabled={disabled}
                  >
                    {tag.name}
                    <svg className="h-4 w-4 ml-1 text-white/70" viewBox="0 0 20 20" fill="currentColor">
                      <path fillRule="evenodd" d="M10 5a1 1 0 01.993.883L11 6v4h4a1 1 0 01.117 1.993L15 12h-4v4a1 1 0 01-1.993.117L9 16v-4H5a1 1 0 01-.117-1.993L5 10h4V6a1 1 0 01.883-.993L10 5z" clipRule="evenodd" />
                    </svg>
                  </button>
                ))}
              {availableTags.filter(tag =>
                tag.name.toLowerCase().includes(search.toLowerCase()) &&
                selectedTag?.id !== tag.id
              ).length === 0 && (
                <div className="px-3 py-2 text-gray-400">No tags found</div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default SingleTagSelector;